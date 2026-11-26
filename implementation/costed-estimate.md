# Task 3: Costed estimate in the AWS Pricing Calculator

Enter both load profiles in the **AWS Pricing Calculator** (calculator.aws) using the exact inputs below. When the estimate is complete, save the evidence into `evidence/` (see the last section). The expected total for each group is given so you can check your entries. Small differences (under 3%) come from calculator rounding.

## Set-up

1. Open **calculator.aws → Create estimate**.
2. Rename the estimate to **"Exam platform A3 – ap-southeast-1"**.
3. Create two groups: **"Normal month"** and **"Exam month"**.
4. For every service: **Location type = Region**, **Region = Asia Pacific (Singapore)**.
5. Add each service below to **both** groups with that group's values.

## Inputs

| # | Calculator service | Field | Normal month | Exam month | Expected cost (normal / exam) |
|---|---|---|---|---|---|
| 1 | **AWS Fargate** | OS Linux, CPU architecture **ARM**; number of tasks; duration; vCPU 0.5; memory 1 GB; ephemeral storage 20 GB | 2 tasks × 730 hours | Line 1: 2 tasks × 730 h. Line 2: 700 task-hours (10 extra tasks × 60 scheduled exam hours + 100 h of automatic scaling; enter 1 task × 700 h) | $35.98 / $53.23 |
| 2 | **Elastic Load Balancing** | Application Load Balancer, 1 in the Region; processed bytes, new connections, active connections, rule evaluations | Inputs that give about 1.0 LCU on average | about 1.5 LCU on average | $24.24 / $27.16 |
| 3 | **Amazon Aurora PostgreSQL-Compatible** | Provisioned, **db.t4g.medium, 2 nodes**, On-Demand, 100% utilisation; storage 30 GB; I/O | 30 million I/Os | 80 million I/Os | $176.34 / $187.34 |
| 3b | Aurora backup storage (same entry) | Additional backup storage | 180 GB (6 monthly snapshots × 30 GB, year-1 average) | 180 GB | about $4.14 / $4.14 |
| 4 | **Amazon DynamoDB** | On-demand capacity; standard table class; storage; point-in-time recovery | 5 GB storage, 1.0 M writes, 2.0 M reads, PITR 5 GB | 8 GB, 15.4 M writes, 3.0 M reads, PITR 8 GB | $2.13 / $13.19 |
| 5 | **Amazon S3** | S3 Standard (incl. web bucket); Standard-IA; Glacier Flexible Retrieval; PUT requests | 51 GB Std, 150 GB IA, 100 GB Glacier, 80,000 PUTs | 91 GB Std, 150 GB IA, 100 GB Glacier, 150,000 PUTs | $4.20 / $5.54 |
| 6 | **Amazon CloudFront** | Data transfer out to the internet: India; HTTPS requests; data to origin | 300 GB, 23 million HTTPS requests, 10 GB to origin | 450 GB, 43 million requests, 40 GB to origin | $16.20 / $42.00 (after the always-free 1 TB and 10 M requests) |
| 7 | **AWS WAF** | 1 web ACL, 4 rules (3 managed rule groups + 1 rate rule), requests | 23 million requests | 43 million requests | $22.80 / $34.80 |
| 8 | **Amazon VPC – NAT gateway** | 2 NAT gateways, 730 hours each; data processed | 25 GB | 50 GB | $87.61 / $89.09 |
| 9 | **Amazon VPC – public IPv4 addresses** | 4 in-use addresses × 730 h | 4 | 4 | $14.60 / $14.60 |
| 10 | **Data transfer** | Inter-AZ (intra-Region); internet out from S3 | 40 GB inter-AZ; 60 GB out (inside the 100 GB free tier) | 80 GB; 90 GB out | $0.80 / $1.60 |
| 11 | **Amazon CloudWatch** | Logs: standard ingestion and storage; 10 custom metrics; 10 standard alarms | 12 GB ingested, 12 GB stored | 30 GB ingested, 30 GB stored | $9.26 / $22.40 |
| 12 | **AWS X-Ray** | Traces recorded (5% sampling) | 750,000 | 1,550,000 | $3.25 / $7.25 |
| 13 | **AWS KMS** | 2 customer-managed keys; symmetric requests | 300,000 requests | 600,000 requests | $2.84 / $3.74 |
| 14 | **AWS Secrets Manager** | 1 secret; API calls | 60,000 | 120,000 | $0.70 / $1.00 |
| 15 | **Amazon GuardDuty** | CloudTrail management events; VPC flow / DNS logs analysed | 400,000 events; 3 GB | 500,000 events; 5 GB | $5.29 / $8.05 |
| 16 | **AWS Backup** | DynamoDB warm backup storage | 20 GB | 32 GB | $2.28 / $3.65 |
| 17 | **Amazon Route 53** | 1 hosted zone; standard queries | 5 million | 8 million | $2.50 / $3.70 |
| 18 | **Amazon SES** | Outbound emails (not from EC2) | 30,000 | 60,000 | $3.00 / $6.00 |
| 19 | **Amazon EventBridge** | Custom events | 50,000 | 200,000 | $0.05 / $0.20 |
| 20 | **Amazon SQS** | Standard queue requests | 300,000 | 1,200,000 | $0.00 / $0.08 |
| 21 | **AWS Lambda** | ARM; requests; 0.5 s; 512 MB | 100,000 | 300,000 | $0.00 / $0.00 (free tier) |
| 22 | **AWS CodeBuild** | arm1.small; build minutes | 300 | 300 | $1.20 / $1.20 |
| 23 | **Amazon ECR** | Storage | 3 GB | 3 GB | $0.30 / $0.30 |
| 24 | **Amazon Cognito** | User pools, Essentials, monthly active users | 8,400 | 8,400 | $0.00 (10,000 free) |
| | **Group total** | | | | **$419.71 / $530.26** |

**Annual:** in the calculator's summary, multiply the Normal group by 10 and the Exam group by 2. The result is **$5,257.62** (average month **$438.13**, **$0.66 per student per year**).

## Optimisations, each with its saving

The calculator is the way to show each saving: duplicate the group, change the one input listed, and record the difference. Savings are monthly and come from the cost model ([`cost-model.py`](cost-model.py)).

| # | Optimisation | What to change in the calculator | Before | After | **Saving per month** | Saving per year |
|---|---|---|---:|---:|---:|---:|
| 1 | **Right-size Aurora** | Instance type db.r6g.large → db.t4g.medium (2 nodes) | $457.00 | $166.44 | **$290.54** | $3,486 |
| 2 | **Remove ElastiCache** (cache the exam paper in task memory) | Delete the ElastiCache entry (2 × cache.t4g.small Redis) | $70.08 | $0 | **$70.08** | $841 |
| 3 | **Graviton + 2-task baseline** | Fargate: x86 → ARM, 4 tasks → 2 tasks | $89.97 | $35.98 | **$53.99** | $648 |
| 4 | **Remove RDS Proxy** (Lambda reserved concurrency 10) | Delete the RDS Proxy entry (4 vCPU × $0.018/h) | $52.56 | $0 | **$52.56** | $631 |
| 5 | **Backups: monthly kept 5 years instead of daily, no cross-Region copy** | Aurora backup storage and AWS Backup GB | $50.85 | $6.42 | **$44.43** | $533 |
| 6 | **Logging: 30-day retention, INFO level, 5% tracing** | CloudWatch Logs GB and X-Ray traces | $45.30 | $12.51 | **$32.79** | $393 |
| | **All optimisations** | | **$965.50** | **$419.71** | **$545.79 (−57%)** | **$6,660** |

### Next optimisation, not yet applied

| # | Optimisation | Saving | Why it waits |
|---|---|---:|---|
| 7 | Aurora **1-year Reserved Instances** for the two db.t4g.medium (No Upfront, typically about 30%; AWS states up to 45%) | **$49.93–$74.90 per month** ($600–$900 per year) | Buy at the start of year 2, after a year of CloudWatch data confirms db.t4g.medium is the right size |

## Evidence to save

1. In the calculator, click **Save and share**. Copy the public estimate link into `evidence/calculator-link.txt`.
2. **Export → CSV** and **Export → PDF**, saved as `evidence/calculator-estimate.csv` and `.pdf`.
3. Take screenshots of the **Normal month** and **Exam month** group totals and the **Summary** page.
4. For each optimisation, take a screenshot of the before and after group totals.
5. Write the date you entered the estimate next to the link. AWS prices change, and the brief asks for the date checked.
