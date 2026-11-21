# Load test – exam-week peak

**Goal:** prove the platform handles **3,000 students starting one exam within 5 minutes and autosaving every 30 s** (about 10 starts/s, then 100 autosaves/s). Find the first bottleneck with CloudWatch, fix it, and re-test.

**SLO (pass criteria, enforced as k6 thresholds):** errors < 1 %, autosave p95 < 1 s, exam start p95 < 2 s.

## Tools

| File | Purpose |
|---|---|
| `scripts/loadtest/setup.sh` | Creates 6 load-test exams and 500 students, and writes their tokens (500 × 6 = 3,000 unique attempts) |
| `scripts/loadtest/exam-peak.js` | k6 script: ramp students over `START_WINDOW`, autosave every `SAVE_INTERVAL`, submit |
| `scripts/loadtest/collect-metrics.sh` | Pulls the CloudWatch evidence for a time window into `evidence/loadtest-<label>-metrics.json` |
| CloudWatch dashboard `exam-platform` | Screenshot this for each run (the `dashboard_url` output) |

If a laptop cannot run 3,000 virtual users, `STUDENTS=1000 SAVE_INTERVAL=10` generates the **same 100 autosaves/s**.

## Procedure

| Run | Config | Load | Command |
|---|---|---|---|
| **R1 baseline** | `exam_mode = false` (t4g.medium, no provisioned concurrency) | Brief profile, then a herd: 3,000 starts in **60 s** | `k6 run ... -e START_WINDOW=60 exam-peak.js` |
| **R2 step-up** (if R1 passes) | same | 2× and 4× the autosave rate to find the knee | `-e SAVE_INTERVAL=15`, then `-e SAVE_INTERVAL=7` |
| **R3 after fix** | `exam_mode = true` (t4g.large + 100 provisioned concurrency), quota raised if needed | Same load as the run that failed | same command |

After each run: `./scripts/loadtest/collect-metrics.sh R1 <start> <end>`, save the k6 summary (`--summary-export evidence/loadtest-R1-k6.json`), and screenshot the dashboard.

## How to read the evidence (which metric proves which bottleneck)

| Symptom in k6 | CloudWatch proof | Bottleneck | Fix |
|---|---|---|---|
| 429/503 or 5xx spike in the **first minute**, start p95 high | `Throttles` > 0, `ConcurrentExecutions` flat at the account limit (`aws lambda get-account-settings`), `ClaimedAccountConcurrency` = limit, `Duration` max high (cold starts) | **B1: Lambda concurrency and cold-start burst** at exam start | `exam_mode = true` → 100 provisioned concurrency on alias `live`; request a concurrency quota increase (new accounts start at 10) |
| Latency rises steadily during the hold phase, few errors | `CPUUtilization` → 90–100 %, `CPUCreditBalance` falling to 0, Proxy `DatabaseConnectionsBorrowLatency` rising, Lambda `Duration` p95 rising | **B2: database CPU** (burstable t4g runs out of credits) | `exam_mode = true` → db.t4g.large (or a non-burstable m7g) during exam months |
| 5xx with `connection` errors | Proxy `ClientConnections` ≫ `DatabaseConnections`, borrow latency in seconds | Connection pool | raise `max_connections_percent`, larger DB class |

## Results (fill in from your runs)

| Run | Students / start window | Autosaves/s | Errors % | Autosave p95 (ms) | Start p95 (ms) | Lambda throttles | Max concurrency | DB CPU max % | Pass? |
|---|---|---|---|---|---|---|---|---|---|
| R1 baseline | 3,000 / 60 s | 100 | | | | | | | |
| R2 step-up | 3,000 / 60 s | 200 / 400 | | | | | | | |
| R3 after fix | same as failing run | | | | | | | | |

**Bottleneck found:** _name it, quote the metric values from `evidence/loadtest-R1-metrics.json` and add the dashboard screenshot._
**Fix applied:** _commit hash of the `exam_mode` change._
**Re-test result:** _R3 numbers; SLO met?_

> The hypothesis before testing is **B1**. On a new account (concurrency limit 10) the 60-second herd needs far more than 10 concurrent cold-starting VPC Lambdas, so throttling is near-certain. On an account with a 1,000 limit, R1 may pass; then R2's step-up shows **B2** (t4g CPU) as the knee. Either way, the evidence decides which one you report. Don't write up the hypothesis as the result.

## Two more bottlenecks (reasoned)

**B3 – SES sending rate when results are released.** Releasing one exam fans out about 3,000 result emails within seconds. SES limits each account to a sending rate (sandbox: 1 email/s; production accounts start low and are raised on request). Without control, the mailer gets `Throttling` errors and retries pile up. **Handled by:** every email goes through the `email` queue; the mailer's event-source `maximum_concurrency = 5` caps the send rate; failures retry and then land in a DLQ with an alarm. **Action:** request SES production access and a rate above about 10/s before go-live; 3,000 emails then take about 5 min.

**B4 – Cognito sign-in rate at 9:00.** 3,000 sign-ins in a few minutes hit the user-pool authentication API (Cognito has per-category request-rate quotas, e.g. user authentication). 3,000 in 5 min is about 10/s, which is well within the default. A herd into 60 s (about 50/s) is closer. **Handled by:** ID tokens last 60 min and refresh tokens 12 h, so students who sign in before the exam don't re-authenticate at 9:00. **Action:** ask students to sign in 10 minutes early, and check the quota in Service Quotas.
