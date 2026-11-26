# Task 3: Failure tests

Four failure scenarios. Each lists its expected impact on the infrastructure and is measured against **RPO 5 minutes** and **RTO 1 hour**, with the fix. Every scenario has a ready-made Cloud Architecture Lab file in [`lab/`](lab/).

## How to run a test in the lab

1. Open the Cloud Architecture Lab and choose **Export → Upload JSON** (or *Resume draft*), then select the scenario file.
2. For F1, open **Failure Lab** and click **AZ-A outage**. F2–F4 already have the failed part marked as unhealthy inside the file.
3. Click **Send Request**, then **Trace** to see each decision.
4. Save a screenshot and **Export → Download PNG / Download JSON** into `evidence/`, and copy the result into the "Lab result" column.

## Summary

| # | Scenario | Lab file | Expected impact | RPO (target 5 min) | RTO (target 1 h) | Meets target? |
|---|---|---|---|---|---|---|
| F1 | **Loss of Availability Zone A** | `a3-F1-az-a-outage.json` | AZ-A task, NAT A, the Aurora writer and the AZ-A subnets fail. The ALB sends traffic to AZ-B; Aurora promotes the AZ-B reader | **About 0**: Aurora copies storage across 3 AZs synchronously; DynamoDB is multi-AZ; browsers retry autosaves | **About 1 minute**: ALB health check about 20 s, Aurora failover about 35–60 s | ✅ |
| F2 | **Aurora writer instance fails** (AZ still healthy) | `a3-F2-aurora-writer-failure.json` | Database writes pause; reads and autosaves (DynamoDB) continue; the reader is promoted | **0** | **About 35–60 s** | ✅ |
| F3 | **Fargate task in AZ-A crashes** | `a3-F3-fargate-task-az-a-failure.json` | The ALB marks the target unhealthy and sends autosaves to the AZ-B task; ECS starts a replacement | **0**: an autosave that fails is retried from the browser's local copy | **About 20 s** for traffic, **about 1–2 min** for full capacity | ✅ |
| F4 | **`notify-fn` Lambda fails** (for example, a bad deployment) | `a3-F4-notify-lambda-failure.json` | The upload still succeeds (the file is in S3, HTTP 202). Messages stay in SQS and are retried 5 times, then go to the dead-letter queue and raise an alarm. Tutor emails are delayed | **0**: no submission is lost; the file and message are both kept (SQS keeps messages for 4 days) | **Time to roll back + redrive**: under 30 min with CodePipeline rollback | ✅ (emails delayed only) |
| F5 | *(reasoned, not run)* **Whole Singapore Region down** | — | Everything stops (SPOF 17) | Up to the last backup that left the Region; **no copy outside the Region today** | Until AWS restores the Region | ❌ **Accepted**: outside the brief's AZ-level target |

## Details and fixes

### F1: Loss of Availability Zone A
- **Result already measured with the same lab engine** (Assignment 2 evidence `06-az-a-failure-exam-start`): the lab reported *"4 resource(s) directly failed. 5 dependent(s) fully survived via redundancy"*. The ALB *"Selected healthy target … tasks AZ-B"*, and the database step was *"Multi-AZ Automated Database Failover … (~35 seconds)"*. The request returned **HTTP 200 in 183 ms**. The A3 design keeps the same ALB, Aurora and NAT layout, so the same path applies. Run `a3-F1-az-a-outage.json` to record it for A3.
- **Capacity risk:** in a normal month only **1 task** survives in AZ-B, which is enough for 300–500 users while ECS replaces the lost task.
- **Fix applied:** scheduled scaling keeps **6 tasks per AZ** during exams, so AZ-B alone can carry an exam. The NAT gateway in AZ-B keeps that zone's outbound access, because each AZ has its own route table.

### F2: Aurora writer instance fails
- **Expected lab trace:** "Multi-AZ Automated Database Failover … promoted standby replica … (~35 seconds)", then HTTP 200.
- **Fixes:**
  - The application uses the **cluster writer endpoint**, never an instance address, so it reconnects automatically after failover.
  - Database calls retry with backoff for up to 60 s.
  - A CloudWatch alarm on the Aurora `failover` event notifies the operations team through SNS.

### F3: Fargate task in AZ-A crashes
- **Expected lab trace:** the ALB evaluates 2 targets, finds 1 failed and selects the AZ-B task; then DynamoDB autosave succeeds.
- **Fixes:**
  - ALB health check on `/health` every **10 s** with an unhealthy threshold of **2**, so a failed task is removed in about 20 s.
  - The ECS service keeps the desired count and replaces the task.
  - Exam months run 6 tasks per AZ, so losing one task barely changes capacity.

### F4: `notify-fn` Lambda fails
- **Expected lab trace:** the upload is accepted (S3 → EventBridge → SQS, HTTP 202), and the failed consumer leaves the message in the queue.
- **Fixes:**
  - Dead-letter queue after **5 receives**, with a CloudWatch alarm whenever it holds any message.
  - CodePipeline **rolls back** a failed Lambda deployment automatically.
  - Once fixed, messages are redriven from the dead-letter queue to the main queue.
  - Students see "Uploaded" whatever happens, because the file is already in S3.

### F5: Region outage (accepted)
- **Why accepted:** the brief asks to survive one AZ, not a Region, and a second Region would roughly double the always-on costs (Aurora, NAT gateways, ALB).
- **Cheapest fix if the university later wants it:** AWS Backup cross-Region copy of the monthly Aurora snapshots and DynamoDB backups, plus S3 Cross-Region Replication of assignment files to Mumbai, for about **$5–$10/month**. That gives RPO ≤ 24 h and RTO of a few hours, because the stacks are rebuilt from CloudFormation.
