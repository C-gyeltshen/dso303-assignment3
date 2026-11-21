# Online Exams & Assignments Platform on AWS – cost, resilience and load (Assignment 3)

Revised, cost-optimised version of the Assignment 2 platform, moved to **Asia Pacific (Singapore) `ap-southeast-1`** for 8,000 students and about 400 staff.

## Summary

- **Cost:** **$4,089/year**, an average of **$341/month** (normal month $302, exam month $533), which is **$0.51 per student per year**. That is 21 % below the Assignment 2 design priced in Singapore ($5,181/yr).
- **What changed:**
  - NAT gateways replaced by VPC endpoints.
  - Reserved Instance for the database, with an `exam_mode` switch for exam months.
  - Leaner logging; X-Ray removed.
  - Glacier Deep Archive for the 5-year file retention.
  - Tutor downloads through CloudFront.
  - WAF rate limit no longer applies to campus IPs.

  Details: [change log](architecture/README.md#what-changed-and-why).
- **Tested:** four failure scenarios measured against RPO and RTO ([`infra/failure-tests.md`](infra/failure-tests.md)), and a k6 load test of the exam peak with CloudWatch evidence ([`infra/load-test.md`](infra/load-test.md)).

## Feasibility verdict

| Requirement | Result |
|---|---|
| Budget ≤ $1,000/month (yearly average) | **Meets**: $341/month; the costliest month ($533) is still 47 % under budget |
| Peak: 3,000 students start within 5 min | **Meets once load test R3 passes** (exam_mode: t4g.large + 100 provisioned concurrency). _Add measured p95 / error % here_ |
| RPO ≤ 5 min | **Meets**: AZ loss 0 (synchronous standby); corruption ≤ 5 min (PITR) |
| RTO ≤ 1 h | **Meets**: AZ loss ≈ 2 min, bad deploy < 5 min, PITR restore ≈ 20–45 min. _Add measured values_ |
| Survive loss of one AZ | **Meets**: every tier in two AZs, no NAT single point of failure |
| Files kept 5 years | **Meets**: S3 lifecycle + monthly backups kept 1,825 days |

**Overall: feasible.** The remaining risks are operational. Raise the Lambda concurrency and SES sending quotas before the first exam week, and rehearse the PITR runbook. Mumbai would be about 8 % cheaper and closer to Bhutan ([region comparison](docs/cost-report.md#5-region-singapore-vs-mumbai)).

## Links

| Item | Link |
|---|---|
| AWS Pricing Calculator – normal month | _paste share link_ |
| AWS Pricing Calculator – exam month | _paste share link_ |
| AWS Pricing Calculator – A2 baseline / Mumbai | _paste share links_ |
| **Demo video** (≤ 5 min, own voice: one failure test + the load test) | _paste link_ |

## Deliverables

| Deliverable | Where |
|---|---|
| Revised diagram, single-point-of-failure register, change log | [`architecture/`](architecture/README.md) (A2 version kept in `architecture-a2.png` / `assignment2.md`) |
| Cost and service report | [`docs/cost-report.md`](docs/cost-report.md), generated from [`docs/cost-model.py`](docs/cost-model.py) |
| Calculator inputs for both profiles | [`docs/calculator-inputs.md`](docs/calculator-inputs.md) |
| Failure test scenarios (impact, measurement, fix) | [`infra/failure-tests.md`](infra/failure-tests.md) + [`scripts/failure/`](scripts/failure) |
| Load test plan and results | [`infra/load-test.md`](infra/load-test.md) + [`scripts/loadtest/`](scripts/loadtest) |
| Calculator exports, test logs, screenshots | [`evidence/`](evidence/README.md) |
| Service table | [`docs/services.md`](docs/services.md) |
| Infrastructure as code / CI/CD | [`infra/`](infra), [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) |

## Deploy

Same as Assignment 2, now in Singapore:

1. **Bootstrap once:** `cd infra/bootstrap && terraform init && terraform apply -var github_repo=<user>/<repo>`.
2. **GitHub secrets:** `AWS_DEPLOY_ROLE_ARN`, `TF_STATE_BUCKET`. **Variables:** `ALARM_EMAIL`, `SES_SENDER_EMAIL`, `SES_VERIFY_EMAILS`.
3. **Push to `main`.** The pipeline tests, applies Terraform, migrates the database, deploys the SPA and smoke-tests it.
4. **Exam month:** set `exam_mode = true` in [`infra/prod.auto.tfvars`](infra/prod.auto.tfvars), commit and push. Set it back to `false` afterwards. The DB resize causes a ~1-minute Multi-AZ failover, so do it outside exam hours.

> New AWS accounts often have a Lambda concurrency limit of 10. Request an increase (Service Quotas → Lambda → Concurrent executions, e.g. 1,000) before turning on `exam_mode`, because 100 provisioned concurrency needs it.

## Running the tests

```bash
# Load test (needs k6: https://k6.io)
./scripts/loadtest/setup.sh 500 6        # 6 exams x 500 students = 3,000 attempts
cd scripts/loadtest && k6 run -e BASE_URL=<site_url> -e EXAM_IDS=<ids> -e START_WINDOW=60 \
     --summary-export ../../evidence/loadtest-R1-k6.json exam-peak.js
cd ../.. && ./scripts/loadtest/collect-metrics.sh R1 <start-utc> <end-utc>

# Failure tests
./scripts/failure/probe.sh f1 600 &      # RPO/RTO probe in parallel
./scripts/failure/f1-az-loss.sh          # then: terraform -chdir=infra apply  (restore)
./scripts/failure/f2-pitr-restore.sh
./scripts/failure/f3-bad-deploy.sh
./scripts/failure/f4-exam-hall-waf.sh before    # then add your IP to campus_cidrs, apply, run "after"

# Cost model
python3 docs/build-cost-report.py        # regenerates docs/cost-report.md after price edits
```

## Demo video plan (≤ 5 minutes, your own voice)

| Time | Show |
|---|---|
| 0:00–0:40 | Revised diagram: what changed and why (NAT → endpoints, exam_mode, SPOF register) |
| 0:40–1:20 | Calculator estimates for both profiles; $341/month vs the $1,000 budget |
| 1:20–3:00 | **Load test:** k6 running, CloudWatch dashboard showing the bottleneck (throttles / DB CPU), the `exam_mode` commit, and the re-run passing |
| 3:00–4:30 | **Failure test F1 (AZ loss):** probe output, the RDS failover event, measured RTO and "0 autosaves lost" |
| 4:30–5:00 | Verdict |

## Tear down

```bash
terraform -chdir=infra destroy
# then empty and destroy the bootstrap state bucket: infra/bootstrap -> terraform destroy
```
Delete any `*-pitr-test` instance left by F2, any load-test Cognito users (they are in the pool and go with it), and AWS Backup recovery points if destroy reports the vault isn't empty.
