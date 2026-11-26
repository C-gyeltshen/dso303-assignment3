# Task 2: Cost and service report

**Region:** Asia Pacific (Singapore) `ap-southeast-1` · **Currency:** USD · **Pricing:** On-Demand
**Prices checked:** 24 November 2026, from the AWS Price List API, which is the same price data the AWS Pricing Calculator uses. Every unit price and its source is listed in [`pricing-sources.md`](pricing-sources.md).
**Reproduce:** [`../implementation/cost-model.py`](../implementation/cost-model.py) holds every price and usage figure. The step-by-step calculator entries are in [`../implementation/costed-estimate.md`](../implementation/costed-estimate.md).

## 1. Monthly cost per service, annual total and cost per student

### Usage assumptions

| Item | Normal month (10 per year) | Exam month (2 per year) |
|---|---|---|
| Users | 8,000 students + 400 staff = 8,400 monthly active users; 300–500 online at once | The same, plus 20 exam sessions of 3,000 students (3,000 start within 5 minutes) |
| API requests through CloudFront | 15 million | 31 million (adds 3,000 students × 2 hours × 1 autosave every 30 s × 20 sessions) |
| Static website requests | 8 million | 12 million |
| Data to users (CloudFront) | 300 GB | 450 GB |
| Fargate tasks (0.5 vCPU, 1 GB, Graviton) | 2 all month (one per AZ) | 2, plus 10 extra for 60 scheduled exam hours, plus 100 task-hours of automatic scaling |
| DynamoDB autosaves | 1.0 M writes, 2 M reads | 15.4 M writes, 3 M reads |
| Aurora | 2 × db.t4g.medium, 30 GB, 30 M I/Os | 2 × db.t4g.medium, 30 GB, 80 M I/Os |
| Assignment files (8 per student per year, 8 MB each, about 512 GB per year) | Year-1 average: 50 GB Standard, 150 GB Standard-IA, 100 GB Glacier | 90 GB Standard (submission peak) |
| Logs into CloudWatch | 12 GB | 30 GB |
| Emails (SES) | 30,000 | 60,000 |
| NAT gateway data | 25 GB | 50 GB |

### Cost per service (Assignment 3 design)

| Service | Normal month | Exam month | Year (10 normal + 2 exam) |
|---|---:|---:|---:|
| ECS Fargate (Graviton, 0.5 vCPU / 1 GB) | $35.98 | $53.23 | $466.26 |
| Application Load Balancer | $24.24 | $27.16 | $296.72 |
| Lambda (marking, notify) | $0.00 | $0.00 | $0.00 |
| Aurora PostgreSQL (writer + reader) | $176.34 | $187.34 | $2,138.08 |
| DynamoDB on-demand + PITR | $2.13 | $13.19 | $47.68 |
| S3 assignments + web bucket | $4.20 | $5.54 | $53.08 |
| CloudFront | $16.20 | $42.00 | $246.00 |
| AWS WAF (1 ACL, 4 rules) | $22.80 | $34.80 | $297.60 |
| Route 53 | $2.50 | $3.70 | $32.40 |
| SQS + EventBridge | $0.05 | $0.28 | $1.06 |
| SES email | $3.00 | $6.00 | $42.00 |
| **Hidden:** KMS keys + requests | $2.84 | $3.74 | $35.88 |
| Secrets Manager | $0.70 | $1.00 | $9.00 |
| GuardDuty | $5.29 | $8.05 | $69.00 |
| **Hidden:** NAT gateways (2) hours + processing | $87.61 | $89.09 | $1,054.28 |
| **Hidden:** public IPv4 (ALB 2 + NAT 2) | $14.60 | $14.60 | $175.20 |
| **Hidden:** data transfer out (S3 downloads, cross-AZ) | $0.80 | $1.60 | $11.20 |
| **Hidden:** CloudWatch Logs, metrics, alarms | $9.26 | $22.40 | $137.40 |
| **Hidden:** X-Ray traces | $3.25 | $7.25 | $47.00 |
| **Hidden:** backups (Aurora snapshots, AWS Backup) | $6.42 | $7.79 | $79.78 |
| CI/CD (CodeBuild, CodePipeline, ECR) | $1.50 | $1.50 | $18.00 |
| Cognito (8,400 MAU, free tier 10,000) | $0.00 | $0.00 | $0.00 |
| **Total** | **$419.71** | **$530.26** | **$5,257.62** |

| Result | Value |
|---|---|
| Normal month | **$419.71** |
| Exam month | **$530.26** |
| Annual total | **$5,257.62** |
| Average month | **$438.13** (44% of the $1,000 budget) |
| Cost per student per year | **$0.66** ($5,257.62 ÷ 8,000) |
| Cost per student per month | **$0.055** |

### Hidden costs, called out

These don't appear as "a service" the team chose, but they add **$1,505/year (29% of the bill)**:

- **NAT gateway hours and processing ($87.61/month):** two NAT gateways at $0.059/hour, plus $0.059 for every GB they process. The hourly charge applies even when nothing is sent.
- **Public IPv4 addresses ($14.60/month):** every public IPv4 address now costs $0.005/hour. The ALB uses 2 and the NAT gateways use 2.
- **Data transfer out ($0.80–$1.60/month):** most user traffic leaves through CloudFront, which has 1 TB/month of free data out. Region → CloudFront transfer is $0.00/GB. Tutors downloading assignments straight from S3 stay inside the account's free 100 GB/month. Cross-AZ traffic costs $0.01/GB in each direction.
- **CloudWatch Logs ($9–$22/month):** $0.70/GB ingested after the 5 GB free tier. 30-day retention keeps storage small.
- **KMS requests ($2.84–$3.74/month):** $1 per key per month, plus $0.03 per 10,000 requests after 20,000 free. S3 Bucket Keys cut the number of requests.
- **Backups ($6.42–$7.79/month in year 1):** Aurora monthly snapshots kept for 5 years are charged at $0.023/GB-month, and this cost grows each year (see the note below). DynamoDB point-in-time recovery is $0.228/GB-month.
- **X-Ray traces ($3–$7/month):** 5% sampling, $5 per million traces after 100,000 free.

**Backups grow over time.** By year 5, about 60 monthly Aurora snapshots × 30 GB = 1.8 TB × $0.023 = **about $41/month**. The assignment archive reaches about 2.5 TB (about $14/month with the lifecycle rule). Budget for roughly **$475–$500/month on average by year 5**, still well under $1,000.

### For comparison: the Assignment 2 design at Singapore prices

| Service (Assignment 2 design) | Normal month | Exam month |
|---|---:|---:|
| ECS Fargate (x86, 0.5 vCPU / 1 GB) | $89.97 | $107.22 |
| Application Load Balancer | $24.24 | $27.16 |
| Lambda (marking, notify) | $0.00 | $0.00 |
| Aurora PostgreSQL (writer + reader) | $466.88 | $477.88 |
| RDS Proxy | $52.56 | $52.56 |
| ElastiCache Redis (2 x cache.t4g.small) | $70.08 | $70.08 |
| DynamoDB on-demand + PITR | $2.13 | $13.19 |
| S3 assignments + web bucket | $4.20 | $5.54 |
| CloudFront | $16.20 | $42.00 |
| AWS WAF (1 ACL, 4 rules) | $22.80 | $34.80 |
| Route 53 | $2.50 | $3.70 |
| SQS + EventBridge | $0.05 | $0.28 |
| SES email | $3.00 | $6.00 |
| KMS | $3.84 | $4.74 |
| Secrets Manager | $1.10 | $1.40 |
| GuardDuty | $5.29 | $8.05 |
| Hidden: NAT gateways (2) hours + processing | $87.61 | $89.09 |
| Hidden: public IPv4 (ALB 2 + NAT 2) | $14.60 | $14.60 |
| Hidden: data transfer out (S3 downloads, cross-AZ) | $0.80 | $1.60 |
| Hidden: CloudWatch Logs, metrics, alarms | $32.30 | $80.00 |
| Hidden: X-Ray traces | $13.00 | $29.00 |
| Hidden: backups (Aurora snapshots, AWS Backup) | $50.85 | $61.11 |
| CI/CD (CodeBuild, CodePipeline, ECR) | $1.50 | $1.50 |
| Cognito (8,400 MAU, free tier 10,000) | $0.00 | $0.00 |
| **Total** | **$965.50** | **$1,131.50** |

Assignment 2 averages **$993/month, 99% of the budget**, with exam months at $1,131.50, over budget. The four optimisations below bring it to $438.

## 2. The three most expensive components

| Rank | Component | Per year | Share | Why it costs this much |
|---|---|---:|---:|---|
| 1 | **Aurora PostgreSQL** (writer + reader, db.t4g.medium) | $2,138 | 41% | Two instances run all 730 hours of every month, even at night and between terms, because the second instance is the failover copy in AZ-B that the "survive one AZ" target needs. You pay for capacity, not use. |
| 2 | **NAT gateways** (2) | $1,054 | 20% | A fixed hourly charge per gateway (one per AZ so a zone failure can't cut off the other zone), plus a per-GB charge. Very little data flows through them, so almost all of this is standby cost. |
| 3 | **ECS Fargate** (Graviton) | $466 | 9% | The API runs all the time (2 tasks) and scales to 12 during exams. This is cheap because of Graviton and the small baseline. |

WAF ($298) and the ALB ($297) are close behind. Together, these always-on charges are the reason a mostly idle university system still costs about $400/month.

## 5. Feasibility verdict

| Question | Target | Result | Verdict |
|---|---|---|---|
| Budget | ≤ $1,000/month averaged over the year | $438.13 average; most expensive month $530.26 | ✅ **Meets it**, with $562/month of headroom. Even at year-5 storage (about $500), it is still within budget. |
| Peak load | 3,000 students start an exam within 5 minutes | About 10 starts/s plus 100 autosaves/s. 12 Fargate tasks are scheduled before each exam. DynamoDB on-demand absorbs the writes. Passed the lab simulation at 100× spike (HTTP 200, 185 ms) | ✅ **Meets it on design and simulation.** Confirm with a real load test before the first exam week (see [`load-test.md`](../implementation/load-test.md)). |
| RPO | ≤ 5 minutes of answers lost | Autosave every 30 s to DynamoDB (point-in-time recovery to the second). Aurora copies writes across 3 AZs synchronously. The browser keeps a local copy | ✅ **Meets it:** about 0 for an AZ or instance failure, and at most 30 s of typing |
| RTO | Back within 1 hour | AZ failure: ALB moves traffic in about 20 s, Aurora fails over in about 35–60 s. A full point-in-time restore takes well under an hour | ✅ **Meets it** for AZ, instance and task failures. ⚠️ **Not for losing the whole Region:** that is an accepted risk (SPOF 17) |

**Overall: feasible.** The design meets the budget with a wide margin, survives the loss of one AZ, and meets the RPO and RTO for every failure the brief lists. The remaining risk, a Singapore-wide outage, is accepted and costed: see [`../architecture/spof-and-changelog.md`](../architecture/spof-and-changelog.md).

Parts 3 and 4 (service comparisons and the Region comparison) are in [`service-comparisons.md`](service-comparisons.md).
