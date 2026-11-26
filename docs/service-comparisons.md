# Task 2: Service comparisons and Region comparison

All prices are Singapore On-Demand prices, checked on 24 Nov 2026 (see [`pricing-sources.md`](pricing-sources.md)). One month = 730 hours.

## 3. Service choices compared with an alternative

### 3.1 Backend: ECS Fargate vs Lambda vs EC2 Auto Scaling

| | **ECS Fargate, Graviton (chosen)** | Lambda behind the ALB | EC2 Auto Scaling (t4g) |
|---|---|---|---|
| Cost: normal month | $35.98 (2 tasks × 730 h × $0.024645/h) | about $13 (15 M requests × $0.20/M + 0.1 s × 0.5 GB per request at $0.0000133/GB-s) | Similar to Fargate, plus instance patching and EBS |
| Cost: exam month | $53.23 | about $27 | Similar to Fargate |
| Performance | Always warm, and keeps database connections open. No cold start when 3,000 students arrive within 5 minutes | Cold starts during the exam-start burst. Each instance opens its own database connection, and without RDS Proxy a db.t4g.medium can run out of connections | Warm, but new instances take 2–4 minutes to boot, so scaling is slow |
| Resilience | ECS spreads tasks across AZs and replaces failed ones automatically | Runs across AZs automatically | Spreads across AZs automatically |
| Effort | No servers to patch; the container image is built by CodeBuild | Code has to be split into functions; harder to test locally | OS patching, AMI updates and agents to maintain |
| **Decision** | **Chosen.** Predictable at the exam peak, and the cost difference is small (about $23/month) | Cheaper at this load, but the database-connection risk would bring back RDS Proxy (+$26–$53/month) and cancel most of the saving | Most effort for no saving |

### 3.2 Database: Aurora provisioned vs Aurora Serverless v2 vs RDS Multi-AZ, and DynamoDB for answers

| | **Aurora PostgreSQL, 2 × db.t4g.medium (chosen)** | Aurora Serverless v2 | RDS PostgreSQL Multi-AZ, db.t4g.medium |
|---|---|---|---|
| Monthly compute | $166.44 (2 × $0.114 × 730) | $146 at the 0.5 ACU minimum per instance; **about $219** at a realistic 1.5 ACU average ($0.20/ACU-hour) | $148.19 ($0.203 × 730) + gp3 Multi-AZ storage at $0.276/GB ($8.28 for 30 GB) = **$156.47** |
| Performance | 2 vCPU, 4 GB, burstable; enough because autosaves go to DynamoDB | Scales up within seconds during exams | Similar to Aurora |
| Resilience | Failover to the AZ-B reader in about 30–60 s; storage keeps 6 copies across 3 AZs | Same | The standby can't serve reads; failover takes 60–120 s |
| Effort | Fixed size, so monitor CPU credits | No sizing needed | Same as Aurora |
| **Decision** | **Chosen:** steady, predictable cost, and can take a 1-year Reserved Instance | Costs more for this steady load | About $10/month cheaper, but slower failover and no read replica |

**Answers go to DynamoDB, not the database.** 15.4 M autosave writes in an exam month cost **$10.93** ($0.71 per million writes). Writing the same autosaves to Aurora would add about 15 M I/Os ($3.30). The real reason for DynamoDB is capacity: 100 writes/s at peak would compete with exam work on a 2-vCPU burstable instance. DynamoDB on-demand absorbs the burst without any capacity planning.

### 3.3 Private traffic: NAT gateways vs VPC endpoints

| | **2 NAT gateways + free gateway endpoints (chosen)** | Interface VPC endpoints only (no NAT) | 1 NAT gateway |
|---|---|---|---|
| Monthly cost | $87.61 (2 × 730 h × $0.059 + 25 GB × $0.059). S3 and DynamoDB gateway endpoints are free | 8 endpoints (ECR API, ECR images, Logs, Secrets Manager, SQS, EventBridge, SES, X-Ray) × 2 AZs × 730 h × $0.013 = **$151.84**, plus $0.01/GB | $43.07 + processing |
| Resilience | Each AZ has its own exit, so losing an AZ can't cut off the other | No internet path at all (safest), but every new service needs another endpoint | **Single point of failure:** if its AZ fails, the other AZ loses outbound access (logs, email, secrets) |
| Effort | Simple | High: one endpoint per service, DNS and policies for each | Simple |
| **Decision** | **Chosen:** cheapest option that survives an AZ loss. Gateway endpoints keep the largest traffic (S3, DynamoDB) off NAT for free | $64/month more | Would save about $44/month but break the "survive one AZ" target |

### 3.4 Pricing model: On-Demand vs Savings Plans vs Reserved Instances

| | **On-Demand (year 1)** | Compute Savings Plan (Fargate, Lambda) | Aurora 1-year Reserved Instances |
|---|---|---|---|
| What it covers | Everything, with no commitment | The steady Fargate baseline (2 tasks) | The two db.t4g.medium instances, which run 24/7 |
| Discount | 0% | AWS states Compute Savings Plans can cut costs by **up to 66%** | AWS states 1-year Aurora RIs give discounts **up to 45%** (3-year up to 66%). No Upfront RIs typically save **about 30%** |
| Saving here | 0 | Baseline is only $36/month, so the saving is about $7–$15/month | 30%: **$49.93/month**; up to 45%: **$74.90/month** |
| Risk | None | A $/hour commitment for 1–3 years | Locked to the instance family and Region for the term |
| **Decision** | **Year 1:** run On-Demand while the real load is measured | Not worth committing for $36/month | **Buy at the start of year 2**, once db.t4g.medium is confirmed as the right size: about **$600–$900/year** saved |

### 3.5 Five-year file retention: S3 Standard vs Intelligent-Tiering vs a lifecycle to Glacier

By year 5 the archive is about **2.5 TB** (8,000 students × 8 files × 8 MB × 5 years ≈ 2,560 GB, 320,000 objects).

| | S3 Standard only | S3 Intelligent-Tiering | **Lifecycle: Standard → IA (30 d) → Glacier Flexible (180 d) → delete (5 yr) (chosen)** | Same lifecycle, but Glacier Instant Retrieval |
|---|---|---|---|---|
| Storage cost at year 5 | **$64.00/month** (2,560 GB × $0.025) | **$16.20/month** (recent 130 GB frequent tier + 2,430 GB archive-instant tier at $0.005 + $0.80 monitoring) | **$14.38/month** | $15.53/month |
| Access to old files | Instant | Instant | 3–5 hours to restore (only for appeals and audits) | Instant (milliseconds), higher retrieval fee |
| Resilience | 11 nines of durability, multi-AZ | Same | Same | Same |
| Effort | None | None (automatic) | One lifecycle rule; restore requests for old files | One lifecycle rule |
| **Decision** | 4× more expensive | Good, with no retrieval delay | **Chosen:** cheapest, and the 5-year deletion is automatic. Files older than 6 months are rarely opened | Use this if tutors need instant access to old files (+$1.15/month) |

## 4. Region comparison: Singapore vs Mumbai, including latency from Bhutan

### Cost (same design, same usage)

| Item that changes | Singapore `ap-southeast-1` | Mumbai `ap-south-1` |
|---|---:|---:|
| Fargate Graviton per task-hour (0.5 vCPU, 1 GB) | $0.024645 | $0.014525 |
| Aurora db.t4g.medium per hour | $0.114 | $0.093 |
| ALB per hour | $0.0252 | $0.0239 |
| NAT gateway per hour / per GB | $0.059 / $0.059 | $0.056 / $0.056 |
| Data transfer out per GB (first 10 TB) | $0.120 | $0.1093 |
| CloudWatch Logs per GB ingested | $0.70 | $0.67 |
| DynamoDB, S3, KMS, WAF, Lambda, SQS | same | same |
| **Normal month** | **$419.71** | **$368.67** |
| **Exam month** | **$530.26** | **$471.51** |
| **Year** | **$5,257.62** | **$4,629.72** (−$627.90, −12%) |

### Latency for users in Bhutan (measured)

Measured on **24 Nov 2026** from a computer in **Thimphu, Bhutan**: repeated HTTPS requests from the browser to each Region's public DynamoDB endpoint, after the connection was set up.

| Region | Fastest | Median | First request (includes TLS setup) |
|---|---:|---:|---:|
| Singapore `ap-southeast-1` | 105 ms | **110 ms** | 6.9 s |
| Mumbai `ap-south-1` | 86 ms | **97 ms** | 1.4 s |
| Hyderabad `ap-south-2` | 92 ms | 231 ms (unstable) | 4.9 s |

Static pages come from CloudFront edge locations near Bhutan (India pricing zone), so the Region only affects API calls. A 13 ms difference per API call is not noticeable for exam answering: one autosave every 30 seconds.

### Region verdict

| | Singapore | Mumbai |
|---|---|---|
| Cost | $5,258/year | $4,630/year (12% cheaper, mainly Fargate and Aurora) |
| Latency from Bhutan | about 110 ms | about 97 ms |
| Services needed | All available | All available |
| Fits the brief | ✅ Brief specifies Singapore | Would need approval |

**Recommendation:** stay in **Singapore**, as the brief requires. It is within budget and the latency difference is small. Mumbai is a sensible future option: it would save about $630/year and be slightly faster for Bhutan, and the design moves unchanged because it is all CloudFormation.
