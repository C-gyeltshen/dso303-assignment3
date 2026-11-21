# Cost and service report – Asia Pacific (Singapore) ap-southeast-1

**Prices checked:** 2026-11-21, in USD. **Calculator estimates:** see [Calculator evidence](#8-calculator-evidence).
**Budget:** USD 1,000 per month averaged over the year (= USD 12,000 per year).

All figures come from [`cost-model.py`](cost-model.py), which lists every unit price with its source. Prices marked **verify** in §9 are the best figure found and must be confirmed in the AWS Pricing Calculator. If the Calculator differs, edit the price in the model and regenerate (`python3 docs/build-cost-report.py`).

## 1. Load profiles and assumptions

| Driver | Normal month (×10) | Exam month (×2) | Basis |
|---|---|---|---|
| Users | 8,000 students + 400 staff = 8,400 MAU | same | Brief |
| Concurrent users | 400 average, 12 h/day | + exam sessions | Brief: 300–500 |
| API calls | 25.9 M (1 call / 20 s per active user) | 37.6 M (+ 8,000 students × 6 exams × 2 h × 120 autosaves) | Autosave every 30 s (brief) |
| Peak rate | ~20 req/s | 100 autosaves/s + ~10 starts/s (3,000 in 5 min) | Brief |
| Lambda | 60 ms average at 512 MB (arm64) | same + 100 provisioned concurrency for 60 h | Assumption, to confirm by load test |
| Assignment uploads | 24,000 files, 192 GB (3 per student, 8 MB average) | 12,000 files, 96 GB | Assumption |
| Tutor downloads | = uploads | = uploads | Each file opened once |
| Emails | 24,000 (tutor notices) | 60,000 (+ 48,000 result emails) | |
| Database | 50 GB gp3, Multi-AZ | same, larger class | |
| Log volume | about 0.65 KB per API call (A2) → 0.27 KB (A3) | | Lambda platform lines + access log |

## 2. Monthly cost per service, annual total, cost per student

{{MODEL}}

### Hidden costs (A3 vs A2, per month normal / exam)

| Hidden cost | Assignment 2 design | Revised design | Why it matters |
|---|---|---|---|
| Data transfer out | S3 → internet tutor downloads **$11.04** / $0.00 (first 100 GB free) | **$0** – downloads go through CloudFront, 1 TB/month free | APAC egress is $0.12/GB, a third more than us-east-1 |
| NAT gateway processing | $0.29 / $0.29 (+ **$86.14** fixed hours) | **$0** (no NAT); endpoint processing $0.04 | The hourly charge dwarfs the per-GB charge at this traffic level. Routing S3 through NAT instead of the gateway endpoint would have added $0.059/GB |
| CloudWatch Logs | **$10.30** / $15.71 (+ X-Ray $12.16 / $15.07) | **$2.66** / $3.70 | Lambda START/END/REPORT lines and INFO logs scale with every request |
| KMS requests | $0.90 / $0.90 | $0.30 / $0.30 | Fewer Secrets Manager decrypts with IAM auth; S3 bucket keys |
| Backups | $4.51 / $4.51 | $1.90 / $1.90 | A2 duplicated RDS PITR with daily AWS Backup copies |
| Cross-AZ traffic | $1.00 / $1.40 | $1.00 / $1.40 | Lambda in AZ-b talking to the proxy/DB in AZ-a |
| SQS empty receives | $0.44 / $0.52 | $0.70 / $0.78 | Lambda pollers long-poll each queue continuously (≈ 650k requests/queue/month), even when idle |
| RDS CPU credits | – / $2.70 | – (t4g.large in exam months) | t4g bills surplus credits at $0.075/vCPU-h when CPU stays above baseline |

## 3. The three most expensive components (revised design)

1. **RDS PostgreSQL Multi-AZ – $1,758/yr (43 %).** Multi-AZ doubles the instance (primary plus synchronous standby), which is the price of surviving an AZ loss with RPO 0. Exam months need t4g.large because the load test showed burstable CPU credits are the limit at peak. Already reduced by a 1-year Reserved Instance (−27 %).
2. **VPC interface endpoints – $456/yr.** Two endpoints (SQS, Secrets Manager) × two AZs × 730 h. A fixed cost that doesn't scale with users. It is still $581/yr cheaper than two NAT gateways, and it removes the NAT single point of failure. If tests confirm RDS Proxy doesn't need the Secrets Manager endpoint, removing it saves another $228/yr.
3. **API Gateway HTTP API – $401/yr.** About 26–38 M requests a month at $1.20/M. Autosave every 30 s is the main driver. Lengthening autosave to 60 s would halve the exam-month share, but it would also double the worst-case answer loss on the client, so 30 s is kept.

(Close behind: AWS WAF $328/yr and RDS Proxy $315/yr.)

## 4. Service choices compared with an alternative

### 4.1 Backend compute: Lambda vs ECS Fargate vs EC2 Auto Scaling

| | **Lambda (chosen)** | ECS Fargate + ALB | EC2 Auto Scaling + ALB |
|---|---|---|---|
| Cost / month (normal) | **≈ $10** (requests + GB-s) | ≈ $65–75: 2 tasks × 0.5 vCPU/1 GB 24×7 + ALB (verify) | ≈ $50–60: 2 × t4g.small + ALB (verify) |
| Cost in exam month | ≈ $53 incl. provisioned concurrency | scale to ~8 tasks → ≈ $120 | scale to ~6 instances → ≈ $90 |
| Peak behaviour | Scales per request in seconds; cold starts handled by provisioned concurrency | Task start 30–60 s; must pre-scale before 9:00 | Instance start 1–3 min; must pre-scale |
| Resilience | Multi-AZ by default, no servers | Multi-AZ if tasks spread | Multi-AZ if ASG spans AZs; you patch the OS |
| Effort | Lowest; account concurrency quota must be managed | Containers, images, ALB | AMIs, patching, scaling policies |

**Verdict:** Lambda. It is cheapest at this utilisation (busy 2 months a year, idle at night) and absorbs the 9:00 spike without pre-scaling.

### 4.2 Answers store: RDS Multi-AZ vs Aurora Serverless v2 vs DynamoDB

| | **RDS PostgreSQL Multi-AZ (chosen)** | Aurora Serverless v2 | DynamoDB on-demand |
|---|---|---|---|
| Cost / month | **$122 normal (RI), $270 exam** | writer + reader ≥ 0.5 ACU each ≈ $115+ idle (verify ACU price); scales up in exams; plus I/O | ≈ $25–40 for autosave writes (≈ 23 M write units), but results, users and assignments still need a relational store or a redesign |
| Peak behaviour | Fixed size; resized by `exam_mode` | Scales ACUs in seconds | Effectively unlimited |
| Resilience / RPO | Sync standby, RPO 0, failover 1–2 min | 6 copies over 3 AZs, failover < 30 s | Multi-AZ by default; PITR 35 days |
| Effort | Same SQL as A2; resize twice a year | Same SQL, auto-scaling | Rewrite data model; tutors lose ad-hoc SQL reporting |

**Verdict:** keep RDS. At 100 writes/s a t4g.large is enough, and it is cheaper than Aurora's always-on minimum. Aurora Serverless v2 is the upgrade path if exams grow beyond one large instance.

### 4.3 Private traffic: NAT gateway vs VPC endpoints

| | 2 NAT gateways (A2) | **Endpoints (A3)** |
|---|---|---|
| Cost / year | **$1,037** (2 × $0.059 × 730 × 12 + processing) | **$456** (S3 gateway free; 2 interface endpoints × 2 AZ) |
| Resilience | One per AZ needed, otherwise an AZ loss cuts egress | ENI per AZ, no internet path to break |
| Security | Lambdas can reach any internet host | No internet egress at all (data-exfiltration risk drops) |
| Effort | Simple | Needed code changes: IAM DB auth, email via queue, admin Lambda outside the VPC |

**Verdict:** endpoints, saving $581/yr. More secure and no NAT single point of failure.

### 4.4 Pricing model: On-Demand vs Savings Plans vs Reserved Instances

| | On-Demand | Compute Savings Plan | **RDS Reserved Instance (chosen for the DB)** |
|---|---|---|---|
| Applies to | Everything | Lambda, Fargate, EC2 (not RDS) | RDS only, size-flexible within t4g |
| Saving here | – | Up to 17 % on Lambda ≈ **$2–3/month**: not worth a commitment | db.t4g.medium Multi-AZ $148 → $108/month = **$480/yr (27 %)** |
| Risk | None | Commitment for 1–3 years | 1-year commitment to the baseline class; the exam-month upgrade is billed on-demand for the difference only |

**Verdict:** 1-year no-upfront RI for the always-on baseline DB. Stay on-demand for Lambda and the exam-month extra capacity. Revisit a 3-year RI ($42 vs $54 per instance-month) once the platform is stable.

### 4.5 Five-year file retention: S3 Standard vs Intelligent-Tiering vs Glacier

Cost at month 60 (≈ 10.6 TB retained):

| | S3 Standard only | Intelligent-Tiering (+ Deep Archive tier opted in) | Lifecycle → Glacier Flexible (A2) | **Lifecycle → Glacier Deep Archive (A3)** |
|---|---|---|---|---|
| Storage / month at year 5 | ≈ $264 | ≈ $35 + monitoring ≈ $3.6 (1.4 M objects) | $59 | **$36** |
| Retrieval | Instant | Instant until archived; hours after | Minutes–hours | 12–48 h (fine for appeals and audits) |
| Effort | None | None, but archive tiers must be enabled | Lifecycle rule | Lifecycle rule (same) |

**Verdict:** Deep Archive after 180 days. Access patterns are predictable (files are read in the marking weeks, then almost never), so a fixed lifecycle beats Intelligent-Tiering's per-object monitoring fee.

## 5. Region: Singapore vs Mumbai

| | **Singapore ap-southeast-1 (required)** | Mumbai ap-south-1 |
|---|---|---|
| Annual cost, revised design | **${{SGP_YEAR}}** (avg ${{SGP_MONTH}}/month) | **${{BOM_YEAR}}** (avg ${{BOM_MONTH}}/month), ≈ 8 % cheaper |
| Biggest differences | db.t4g.medium $74/instance-month | db.t4g.medium $61/instance-month; API Gateway and egress slightly lower (verify) |
| Latency from Bhutan (estimate) | ≈ 80–120 ms RTT | ≈ 45–70 ms RTT |
| Evidence for latency | Kathmandu users see ~65–80 ms to Singapore; Dhaka ~85 ms | Kathmandu users see ~35–40 ms to Mumbai |
| Effect on users | Static files come from CloudFront edges in India either way; only API calls travel to the Region. Autosave is asynchronous, so +40–50 ms is not noticeable; exam start is slightly slower | Faster API round trips |
| Services | All services used are available | All services used are available |

The latency figures are estimates from neighbouring countries; there is no published Thimphu → AWS measurement. **Measure from Bhutan** (e.g. cloudping.info, or `curl -w "%{time_connect}"` to each Region's API endpoint) and add a screenshot to `evidence/`.

**Conclusion:** Mumbai is cheaper and closer. Singapore still meets every target with a large budget margin, and the extra latency only affects the API leg, not page loads. If the university can choose, Mumbai is the better Region; under this brief, Singapore is acceptable.

## 6. Feasibility verdict

| Requirement | Target | Evidence | Verdict |
|---|---|---|---|
| **Budget** | ≤ $1,000/month averaged | Revised design **${{SGP_MONTH}}/month** average (${{SGP_YEAR}}/yr; normal ${{A3_N}}, exam ${{A3_E}}). Even the costliest month is about 47 % under budget | **Meets**, with about 66 % headroom (about ${{HEADROOM}}/yr) |
| Cost per student | – | **${{PER_STUDENT}} per student per year** | Very low |
| **Peak load** | 3,000 starts in 5 min, autosave 30 s | 100 writes/s design capacity; exam_mode adds 100 warm Lambdas + t4g.large. Proven by load test R3 (`infra/load-test.md`) | **Meets if R3 passes.** Report the measured p95 and error % |
| **RPO** | ≤ 5 min | AZ loss: synchronous standby → 0 (F1). Corruption: PITR logs every 5 min → ≤ 5 min (F2, measured `LatestRestorableTime` lag) | **Meets** |
| **RTO** | ≤ 1 h | AZ loss ≈ 2 min (F1); bad deploy < 5 min (F3); PITR restore ≈ 20–45 min (F2 measured) | **Meets**; PITR has the least margin, so rehearse it each term |
| AZ loss | Survive one | Every tier spans two AZs; no NAT | **Meets** |
| 5-year retention | Files and records | S3 lifecycle (delete at 1,825 d), monthly DB backups kept 1,825 d | **Meets** |
| Region loss | Not required | Single-Region | **Accepted risk**; cross-region snapshot copy ≈ $5/month if wanted |

**Overall: feasible.** The platform costs about a third of the budget. The two remaining risks are operational, not financial: the Lambda concurrency quota and SES sending quota must be raised before the first exam week, and the PITR runbook must be rehearsed.

## 7. Optimisations (with savings)

| # | Optimisation | Before → after | Saving / year |
|---|---|---|---|
| O1 | Replace 2 NAT gateways with an S3 gateway endpoint + SQS/Secrets interface endpoints | $1,037 → $456 | **$581** |
| O2 | 1-year Reserved Instance for the baseline DB (db.t4g.medium Multi-AZ) | $148 → $108 per month | **$480** |
| O3 | Logs: JSON at WARN, drop platform lines, 30-day retention, IA class for access and flow logs; remove X-Ray | $286 → $34 | **$252** |
| O4 | Tutor downloads through CloudFront signed URLs instead of S3 egress | $110 → $0 | **$110** |
| O5 | Lifecycle to Glacier Deep Archive instead of Flexible Retrieval | $206 → $197 in year 1 | **$9** (year 1), **$285** (year 5) |
| O6 | Remove duplicate daily AWS Backup copies (RDS PITR already covers 35 days) | $54 → $23 | **$31** |
| – | *Added by load-test findings:* exam_mode (t4g.large + provisioned concurrency) | | −$368 |
| – | Other small items (WAF campus rule, extra alarms, 4th queue's polling, fewer KMS/Secrets calls, no CPU-credit surplus) | | −$3 |
| | **Net** | **${{A2_YEAR}} → ${{SGP_YEAR}}** | **${{NET}} (−{{NET_PCT}} %)** |

Considered but not applied: Lambda function URLs instead of API Gateway would save about $400/yr, but you would lose the managed JWT authorizer and throttling. A Compute Savings Plan would save under $40/yr.

## 8. Calculator evidence

Enter both profiles in the AWS Pricing Calculator using [`calculator-inputs.md`](calculator-inputs.md). Save each estimate, export it (CSV/PDF/JSON) into `evidence/`, and paste the share links here:

| Estimate | Link | Export file | Calculator total / month |
|---|---|---|---|
| Normal month (A3) | _paste share link_ | `evidence/calculator-normal.csv` | |
| Exam month (A3) | _paste share link_ | `evidence/calculator-exam.csv` | |
| Normal month (A2 baseline, for the savings) | _paste share link_ | `evidence/calculator-a2-normal.csv` | |
| Mumbai comparison (A3, normal) | _paste share link_ | `evidence/calculator-mumbai.csv` | |

If a Calculator total differs from §2 by more than about 5 %, update the matching price in `cost-model.py`, regenerate this report and note the change.

## 9. Model detail and sources

{{DETAIL}}

**Sources:** RDS instance prices (Singapore and Mumbai), bytebase.com/dbcost, updated 2026-07-20 · NAT and egress, egresscost.com/aws/ap-southeast-1 · CloudWatch Logs Singapore, dev.classmethod.jp (2023) · CloudFront free tier, aws.amazon.com/free · Cognito free tier, aws.amazon.com/cognito/pricing · PrivateLink, aws.amazon.com/privatelink/pricing · Latency, community.fly.io (Kathmandu), dev.to (Dhaka), economize.cloud (inter-region).
