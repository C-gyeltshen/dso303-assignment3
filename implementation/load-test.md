# Task 3: Load test and bottlenecks

## The load to prove

| Moment | Requests |
|---|---|
| Exam start: 3,000 students in 5 minutes | about **10 exam starts/s** (each start = 1 API call + cached web pages) |
| During the exam: 3,000 autosaves every 30 s | about **100 writes/s** to DynamoDB for up to 2 hours |
| Exam end: 3,000 submissions in about 2 minutes | about **25 submissions/s** → SQS → marking Lambda |

## Main bottleneck: Fargate capacity at exam start

### 1. Found
The cost-optimised design runs only **1 Fargate task per AZ** in normal months. In the lab, **Analyze → Architecture Risks** flagged both tasks:

> "runs a single instance/task (replicas: 1) … no capacity to absorb a health-check failure, an AZ outage, or routine maintenance."

### 2. Proven with CloudWatch (procedure to run on AWS)
The Cloud Architecture Lab does not simulate CPU saturation for ECS or Fargate. Its ECS step states that *"load saturation and scheduler timing are not modeled"*. The proof therefore needs a real test before the first exam week:

1. Deploy with the normal-month baseline (**2 tasks**) and switch off scheduled scaling.
2. Generate the exam-start load with the **Distributed Load Testing on AWS** solution, or k6 on a small EC2 instance: ramp to 3,000 virtual users over 5 minutes, each calling `GET /api/exams/{id}/start` once and then `PUT /answers` every 30 s.
3. Watch these CloudWatch metrics and screenshot them into `evidence/load-test/`:

| Metric | Namespace | Bottleneck if |
|---|---|---|
| `CPUUtilization` (service) | `AWS/ECS` | > 80% for 2+ minutes |
| `TargetResponseTime` p95 | `AWS/ApplicationELB` | > 1 s |
| `HTTPCode_Target_5XX_Count` / `HTTPCode_ELB_5XX_Count` | `AWS/ApplicationELB` | > 0 |
| `RequestCountPerTarget` | `AWS/ApplicationELB` | well above about 60/s per 0.5-vCPU task |

**Expected result with 2 tasks:** CPU climbs to 100% within the first 2 minutes, p95 response time goes over 1 s, and 5XX errors appear. That is about 110 requests/s shared between two 0.5-vCPU tasks, with token checks and database reads.

### 3. Fixed
- A **scheduled action** in ECS Service Auto Scaling sets the minimum to **12 tasks (6 per AZ)**, 30 minutes before each exam, from the exam timetable.
- **Target tracking** on `ECSServiceAverageCPUUtilization` = 50% stays on (maximum 20).
- The exam paper is cached in each task's memory, so starts don't all hit Aurora.

### 4. Re-tested
- **In the lab:** the A3 design at a **100× traffic spike** (`lab/a3-L1-exam-start-100x.json`) returned **HTTP 200 in 185 ms**. The path was Route 53 → WAF → CloudFront → ALB → Fargate AZ-A → Aurora writer, with no bottlenecks reported (measured 24 Nov 2026). `lab/a3-L2-autosave-100x.json` re-runs the autosave path.
- **On AWS:** repeat the same load with the scheduled minimum of 12 tasks. Pass if CPU stays under 60%, p95 is under 500 ms, and there are no 5XX errors. Save the same four CloudWatch graphs as the "after" evidence.

## Two more bottlenecks (reasoned)

### B2: WAF rate limit vs a shared campus IP address
- **Risk:** a whole lab of students often shares a few public IP addresses through the campus NAT. A per-IP rate limit of a few hundred requests in 5 minutes would block a hall of 300 students all starting an exam together, and they would see HTTP 403.
- **How to see it:** the WAF metric `BlockedRequests` for the rate rule, in CloudWatch under `AWS/WAFV2`.
- **Fix:**
  - Apply the rate rule to `/login` only.
  - Set it above campus volume (for example 2,000 per 5 minutes).
  - Add the campus IP range to an allow list that the rate rule skips.

### B3: Aurora db.t4g.medium CPU credits at exam end
- **Risk:** the db.t4g.medium is burstable. At exam end, 3,000 submissions and the marking writes arrive together. Long busy periods can use up CPU credits and slow the database to its baseline speed.
- **How to see it:** the `CPUCreditBalance` and `CPUUtilization` metrics for the Aurora writer (`AWS/RDS`), and Lambda `Throttles` for `marking-fn`.
- **Fix (in the design):**
  - Marking runs through **SQS → Lambda with reserved concurrency 10**, so the database never sees more than 10 marking connections. A burst of submissions waits in the queue instead of hitting Aurora.
  - Unlimited burst mode stays on for the T4g instance.
  - If credits drop below 20% during the trial run, move to db.r6g.large for exam months only. That costs $0.199/h extra ($0.313 vs $0.114), about $12 per instance for 60 exam hours.

**One more to watch:** DynamoDB on-demand serves up to double the previous peak straight away. The first exam of the term is far above normal traffic, so pre-warm the table with **warm throughput** (or run a short practice exam the day before) to avoid throttling.
