# Viva preparation – likely questions and short answers

**Why serverless (Lambda) instead of EC2/ECS?**
Exam load is spiky: quiet most of the year, 3,000 starts in 5 minutes during exam week. Lambda scales per request in seconds and costs nothing when idle. ECS would need pre-scaled tasks and pays 24/7.

**Why is Lambda inside a VPC, and doesn't that slow it down?**
So it can reach the private database without the DB ever being public. Since 2019 Lambda uses shared Hyperplane ENIs, so VPC cold starts are no longer slow.

**What does RDS Proxy do?**
It pools connections. Hundreds of concurrent Lambdas would each open a PostgreSQL connection and exhaust `max_connections`; the proxy multiplexes them onto a small pool and holds client connections during failover.

**How do you meet RPO 5 min / RTO 1 h?**
AZ loss: Multi-AZ synchronous replication → RPO ≈ 0, automatic failover in 1–2 min. Data corruption or a bad deploy: point-in-time restore (transaction logs are uploaded every 5 min → RPO ≤ 5 min), and a restore of a small DB finishes well inside 1 hour. The browser also keeps a local copy of answers and re-sends it.

**Why 99.9 %?**
That allows about 43 minutes of downtime a month. Every component is either a multi-AZ managed service or deployed across two AZs, with no single instance in the request path.

**Why presigned POST rather than uploading through the API?**
API Gateway caps payloads at 10 MB and Lambda at 6 MB. A presigned POST lets the browser send the 50 MB file straight to S3, and its policy enforces the 50 MB maximum (`content-length-range`), the content type and the key prefix.

**How is the tutor notified?**
S3 `ObjectCreated` → SQS → upload-processor Lambda → validates magic bytes → inserts submission row → SES email. SQS gives retries and a DLQ, and the `ON CONFLICT DO NOTHING` insert makes it idempotent so retries never send duplicate emails.

**How are the 5-year records kept?**
Uploads: S3 lifecycle (IA at 30 days, Glacier at 180 days, expire at 1,825 days). DB: AWS Backup monthly backups retained 1,825 days. Audit: CloudTrail bucket with a 5-year lifecycle.

**How do roles work?**
Cognito groups `students`, `tutors`, `admins` appear in the ID token's `cognito:groups` claim. API Gateway verifies the token's signature; the Lambda checks the group for each route (e.g. only tutors can release results).

**What stops a student cheating with the timer?**
The deadline is set and enforced by the server (`deadline` column, 60-s grace); the client clock is only for display. Answer keys are never sent to students.

**What happens if one AZ fails mid-exam?**
CloudFront/S3/API Gateway/SQS/Cognito are regional, so they're unaffected. Lambda keeps running in the healthy AZ's subnets with its own NAT gateway. RDS promotes the standby; for ~1–2 minutes autosaves may fail, the UI shows "kept on this device, retrying", and the next autosave after failover succeeds with no data lost.

**Why GitHub Actions and Terraform?**
The code is on GitHub, and OIDC means no AWS keys are stored. Terraform gives a reviewed plan on every PR and makes the whole stack reproducible: `terraform destroy` and `apply` rebuild it from nothing.

**What would you change for production scale?**
`single_nat_gateway = false`, a bigger DB class (`db.t4g.medium`/`r7g`), deletion protection, reserved and provisioned concurrency for exam weeks, SES production access, federation with the university's SSO, and a cross-region backup copy for regional disaster recovery.

---

# Assignment 3 – extra viva questions

**Why is the database still the biggest cost?**
Multi-AZ means paying for two instances: primary and synchronous standby. That is the price of RPO 0 when an AZ fails. The Reserved Instance cuts the baseline by 27 %, and the larger class is only paid for in the two exam months.

**How did you remove the NAT gateways without breaking anything?**
Each private Lambda used NAT for one of four things:
- S3: now the free gateway endpoint.
- SQS: now an interface endpoint.
- The DB secret: replaced by IAM auth to RDS Proxy, where the token is signed locally with no network call.
- SES and Cognito: moved into Lambdas outside the VPC (`mailer`, `admin`), fed by a queue or the API.

**What did the load test prove?**
Quote your measured numbers. The method: R1 at the brief's peak (or a 60-s herd), the CloudWatch dashboard to find the metric that saturates (Throttles, ConcurrentExecutions, DB CPU, CPU credits), the fix through `exam_mode`, then R3 at the same load against the SLO (errors < 1 %, p95 < 1 s).

**What are hidden costs and which mattered here?**
Charges that don't come from the main service line. The ones that mattered:
- NAT hourly charges ($86/month for two).
- CloudWatch Logs and X-Ray, which scale with every request.
- S3 egress for tutor downloads ($0.12/GB).
- Duplicate backups.
- SQS empty receives from Lambda pollers.

**Why Singapore if Mumbai is cheaper and closer?**
The brief requires Singapore. It still meets every target with about 66 % budget headroom. Page loads come from CloudFront edges in India either way, and autosave is asynchronous, so the extra ~40 ms only affects API calls.

**What is still a single point of failure?**
The Region itself (accepted; a 1-hour RTO can't cover it without a second Region), Cognito (a regional service) and the KMS key (protected by a deletion window). Everything else is either in both AZs or a multi-AZ managed service.
