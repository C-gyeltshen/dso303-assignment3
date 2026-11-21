# AWS Pricing Calculator – inputs for both load profiles

Open <https://calculator.aws/#/estimate>, choose **Region: Asia Pacific (Singapore)** for every service (WAF is global), and create **two estimates**: "Exam platform – normal month" and "Exam platform – exam month". Add a group per tier so the export mirrors `cost-report.md`.

| Service (Calculator name) | Field | Normal month | Exam month |
|---|---|---|---|
| **Amazon RDS for PostgreSQL** | Instances / class | 1 × db.t4g.medium | 1 × db.t4g.large |
| | Deployment | Multi-AZ (one standby) | Multi-AZ (one standby) |
| | Pricing model | Reserved, 1 yr, No Upfront | On-Demand (note: RI covers the medium share; see report) |
| | Storage | gp3, 50 GB | gp3, 50 GB |
| | Backup storage (additional) | 20 GB | 20 GB |
| **Amazon RDS Proxy** | vCPUs of DB | 2 | 2 |
| **AWS Lambda** | Architecture | Arm | Arm |
| | Requests | 26,000,000 | 37,700,000 |
| | Duration / memory | 60 ms, 512 MB | 60 ms, 512 MB |
| | Provisioned concurrency | 0 | 100 for 60 h, 512 MB |
| **Amazon API Gateway** | HTTP API requests | 25,920,000 | 37,584,000 |
| | Average request size | ≤ 512 KB | ≤ 512 KB |
| **Amazon CloudFront** | Data transfer out (India) | 310 GB | 261 GB |
| | HTTPS requests (India) | 26,900,000 | 38,900,000 |
| **AWS WAF** | Web ACLs / rules | 1 / 5 | 1 / 5 |
| | Requests | 26.9 M | 38.9 M |
| **Amazon VPC** | Interface endpoints | 2 endpoints × 2 AZ, 4 GB processed | same |
| | NAT gateways | 0 (A2 baseline estimate: 2, 5 GB) | 0 |
| **Amazon S3** | S3 Standard | 176 GB | 176 GB |
| | S3 Standard-IA | 880 GB | 880 GB |
| | S3 Glacier Deep Archive | 1,056 GB (month 12) | 1,056 GB |
| | PUT/POST requests | 24,000 | 12,000 |
| | Lifecycle transitions | 48,000 | 24,000 |
| **Amazon SQS** | Standard requests | 2.7 M | 3.0 M |
| **Amazon SES** | Emails from Lambda | 24,000 | 60,000 |
| **Amazon Cognito** | MAU (Essentials) | 8,400 | 8,400 |
| **AWS KMS** | Keys / requests | 1 / 100,000 | 1 / 100,000 |
| **AWS Secrets Manager** | Secrets / API calls | 1 / 2,000 | 1 / 2,000 |
| **Amazon CloudWatch** | Logs ingested Standard / IA | 2.0 GB / 7.5 GB | 2.3 GB / 10.4 GB |
| | Alarms | 20 standard | 20 standard |
| | Dashboards | 1 | 1 |
| **Amazon Route 53** | Hosted zones | 1 | 1 |
| **Data Transfer** | Inter-AZ | 50 GB | 70 GB |

After saving: **Share** → copy the link into `docs/cost-report.md` §8, then **Export → CSV** (and PDF) into `evidence/` as `calculator-normal.csv` and `calculator-exam.csv`. Write the date you checked at the top of each export's file name or in the report.

For the A2 baseline estimate (used to show the savings), clone the normal-month estimate and change: RDS to On-Demand; VPC to 2 NAT gateways with 5 GB processed and no interface endpoints; S3 archive to Glacier Flexible Retrieval; CloudWatch Logs to 19.4 GB Standard (normal) / 26.9 GB (exam); add X-Ray 1.3 M + 5 % of requests traced; S3 data transfer out 192 GB.
