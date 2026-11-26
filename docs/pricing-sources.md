# Pricing sources

**Date checked:** 24 November 2026
**Currency:** USD, On-Demand, before tax
**Main source:** the AWS Price List API (`https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/<service>/current/<region>/index.json`). This is the same price data the AWS Pricing Calculator uses. The "Published" column is the `publicationDate` inside each price file.

## Singapore (`ap-southeast-1`)

| Service | Usage type | Price | Published |
|---|---|---|---|
| Fargate Graviton vCPU | `APS1-Fargate-ARM-vCPU-Hours:perCPU` | $0.04045 per vCPU-hour | 2026-11-11 |
| Fargate Graviton memory | `APS1-Fargate-ARM-GB-Hours` | $0.00442 per GB-hour | 2026-11-11 |
| Fargate x86 vCPU / memory | `APS1-Fargate-vCPU-Hours:perCPU` / `-GB-Hours` | $0.05056 / $0.00553 | 2026-11-11 |
| Application Load Balancer | `APS1-LoadBalancerUsage` / `APS1-LCUUsage` | $0.0252 per hour / $0.008 per LCU-hour | 2026-11-19 |
| Aurora PostgreSQL db.t4g.medium | `APS1-InstanceUsage:db.t4g.medium` | $0.114 per hour | 2026-11-20 |
| Aurora PostgreSQL db.r6g.large | `APS1-InstanceUsage:db.r6g.large` | $0.313 per hour | 2026-11-20 |
| Aurora storage / I/O / backup | `APS1-Aurora:StorageUsage`, `StorageIOUsage`, `BackupUsage` | $0.11 per GB-month / $0.22 per million / $0.023 per GB-month | 2026-11-20 |
| Aurora Serverless v2 | `APS1-Aurora:ServerlessV2Usage` | $0.20 per ACU-hour | 2026-11-20 |
| RDS Proxy | `APS1-RDS:ProxyUsage` | $0.018 per vCPU-hour | 2026-11-20 |
| RDS PostgreSQL Multi-AZ db.t4g.medium | `APS1-Multi-AZUsage:db.t4g.medium` | $0.203 per hour | 2026-11-20 |
| RDS Multi-AZ gp3 storage | `APS1-RDS:Multi-AZ-GP3-Storage` | $0.276 per GB-month | 2026-11-20 |
| ElastiCache Redis cache.t4g.small | `APS1-NodeUsage:cache.t4g.small` | $0.048 per hour | 2026-11-18 |
| DynamoDB on-demand | `APS1-WriteRequestUnits` / `ReadRequestUnits` | $0.71 / $0.1425 per million | 2026-11-11 |
| DynamoDB storage / PITR | `APS1-TimedStorage-ByteHrs` / `TimedPITRStorage` | $0.285 per GB-month (first 25 GB free) / $0.228 per GB-month | 2026-11-11 |
| S3 Standard / Standard-IA | `APS1-TimedStorage-ByteHrs` / `-SIA-ByteHrs` | $0.025 / $0.0138 per GB-month | 2026-11-21 |
| S3 Intelligent-Tiering, archive instant tier | `APS1-TimedStorage-INT-AIA-ByteHrs` | $0.005 per GB-month (+ $0.0025 per 1,000 objects monitored) | 2026-11-21 |
| S3 Glacier Flexible / Glacier Instant Retrieval | `APS1-TimedStorage-GlacierByteHrs` / `-GIR-ByteHrs` | $0.0045 / $0.005 per GB-month | 2026-11-21 |
| S3 requests | `APS1-Requests-Tier1` / `Tier2` | $0.005 per 1,000 PUTs / $0.004 per 10,000 GETs | 2026-11-21 |
| CloudFront HTTPS requests (India and Asia) | `IN-Requests-Tier2-HTTPS` | $0.012 per 10,000 | 2026-10-19 |
| CloudFront data out (India) | `IN-DataTransfer-Out-Bytes` | $0.109 per GB (first 10 TB) | 2026-10-19 |
| CloudFront data to origin (Asia) | `AP-DataTransfer-Out-OBytes` | $0.060 per GB | 2026-10-19 |
| Data transfer out to the internet | `APS1-DataTransfer-Out-Bytes` | $0.120 per GB (first 10 TB) | 2026-11-19 |
| Region to CloudFront | `APS1-CloudFront-Out-Bytes` | $0.00 per GB | 2026-11-19 |
| Cross-AZ data | `APS1-DataTransfer-Regional-Bytes` | $0.010 per GB, each direction | 2026-11-19 |
| Public IPv4 address | `APS1-PublicIPv4:InUseAddress` | $0.005 per hour | 2026-11-23 |
| Interface VPC endpoint | `APS1-VpcEndpoint-Hours` / `-Bytes` | $0.013 per hour / $0.01 per GB | 2026-11-23 |
| AWS WAF | `APS1-WebACLV2` / `RuleV2` / `Request` | $5.00 per ACL-month / $1.00 per rule / $0.60 per million requests | 2026-11-23 |
| Lambda (ARM) | `APS1-Request-ARM` / `APS1-Lambda-GB-Second-ARM` | $0.20 per million / $0.0000133334 per GB-second (1 M requests and 400,000 GB-s free) | 2026-11-20 |
| SQS standard | `APS1-Requests-Tier1` | $0.40 per million (first 1 million free) | 2026-11-11 |
| SES outbound email | `APS1-Recipients` | $0.0001 per email | 2026-11-04 |
| CloudWatch Logs ingestion / storage | `APS1-DataProcessing-Bytes` / `TimedStorage-ByteHrs` | $0.70 per GB / $0.03 per GB-month (5 GB free) | 2026-11-19 |
| CloudWatch metrics / alarms | `APS1-CW:MetricMonitorUsage` / `AlarmMonitorUsage` | $0.30 per metric / $0.10 per alarm per month | 2026-11-19 |
| KMS | `ap-southeast-1-KMS-Keys` / `-KMS-Requests` | $1 per key-month / $0.03 per 10,000 requests (20,000 free) | 2026-11-08 |
| Secrets Manager | `APS1-AWSSecretsManager-Secret` / `-APIRequest` | $0.40 per secret / $0.05 per 10,000 calls | 2026-11-11 |
| GuardDuty | `APS1-PaidEventsAnalyzed` / `-Bytes` | $0.0000046 per CloudTrail event / $1.15 per GB of logs | 2026-10-30 |
| AWS Backup (DynamoDB warm) | `APS1-WarmStorage-ByteHrs-DynamoDB` | $0.114 per GB-month | 2026-11-20 |
| Cognito user pools | `Global-CognitoFreeTierMAU` | First 10,000 monthly active users free (8,400 needed) | 2026-11-19 |
| CodeBuild ARM small | `APS1-Build-Min:ARM:g1.small` | $0.004 per minute | 2026-09-11 |
| CodePipeline | `Global-activePipeline` | First active pipeline free | 2026-09-11 |
| ECR storage | `APS1-TimedStorage-ByteHrs` | $0.10 per GB-month | 2026-11-13 |

## Mumbai (`ap-south-1`), for the Region comparison

| Service | Price | Published |
|---|---|---|
| Fargate Graviton vCPU / memory | $0.02383 per vCPU-hour / $0.00261 per GB-hour | 2026-11-11 |
| ALB | $0.0239 per hour, $0.008 per LCU-hour | 2026-11-19 |
| Aurora PostgreSQL db.t4g.medium | $0.093 per hour | 2026-11-20 |
| Aurora Serverless v2 | $0.18 per ACU-hour | 2026-11-20 |
| Data transfer out | $0.1093 per GB | 2026-11-19 |
| CloudWatch Logs ingestion | $0.67 per GB | 2026-11-19 |
| DynamoDB | $0.71 / $0.1425 per million (same as Singapore) | 2026-11-11 |

## Prices taken from AWS pricing web pages

The price files for these were too large to load or don't list a per-Region file. Check them in the AWS Pricing Calculator when you enter the estimate.

| Item | Price used | Source |
|---|---|---|
| NAT gateway, Singapore / Mumbai | $0.059 per hour + $0.059 per GB / $0.056 + $0.056 | Amazon VPC pricing page, Region table (archived copy) |
| Route 53 | $0.50 per hosted zone + $0.40 per million standard queries | aws.amazon.com/route53/pricing |
| EventBridge custom events | $1.00 per million | aws.amazon.com/eventbridge/pricing |
| X-Ray | $5.00 per million traces (first 100,000 free) | aws.amazon.com/cloudwatch/pricing |
| CloudFront free tier | 1 TB data out + 10 million HTTPS requests per month | AWS Free Tier (always free) |
| Data transfer out free tier | 100 GB per month per account | AWS Free Tier |
| Aurora Reserved Instances | 1-year up to 45% off; No Upfront typically about 30% | aws.amazon.com/rds/aurora/pricing |
| Compute Savings Plans | Up to 66% off | aws.amazon.com/savingsplans/compute-pricing |

## Latency measurement

24 Nov 2026, from Thimphu, Bhutan, using a browser on the student's computer. Nine HTTPS requests were sent to `https://dynamodb.<region>.amazonaws.com/ping` in each Region; the first request is reported separately because it includes TLS setup.
