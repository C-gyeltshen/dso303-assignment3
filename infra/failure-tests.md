# Failure tests

Targets: **RPO ≤ 5 min**, **RTO ≤ 1 h**, survive the loss of one AZ. Each test has a script in [`scripts/failure/`](../scripts/failure) that **measures** the result and writes a log to `evidence/`.

> Run the tests on the deployed stack, then copy the measured numbers into the "Measured" column. The "Expected" column is the prediction made before running the test. Keep both, because the difference between them is part of the analysis.

## Summary

| # | Scenario | Expected impact | Expected RPO / RTO | Measured RPO / RTO | Meets target? | Fix (in this repo) |
|---|---|---|---|---|---|---|
| F1 | Loss of AZ-a (compute and DB primary) | Autosaves fail for about 1–2 min while RDS fails over; browser keeps answers and retries | RPO 0 / RTO ≈ 2 min | _fill in from `evidence/f1-*`_ | | Multi-AZ RDS + Proxy, Lambdas and endpoints in both AZs, client-side retry with local copy |
| F2 | Data corruption / accidental deletion (bad SQL, bad release) | Wrong or missing answers until restored; platform read-only during cut-over | RPO ≤ 5 min / RTO ≈ 20–45 min | _fill in from `evidence/f2-pitr-log.txt`_ | | 35-day PITR, scripted restore and runbook |
| F3 | Bad deployment reaches production | Every API call returns 5xx until rollback | RPO 0 / RTO < 5 min | _fill in from `evidence/f3-bad-deploy-log.txt`_ | | Alias `live` = instant rollback; 5xx alarm; pipeline tests |
| F4 | Exam hall of 300 students behind one campus IP trips the WAF rate limit | 403s for the whole hall for up to 5 min; answers held in the browser | RPO 0 (local copy) / RTO 5 min **per incident**, repeatable | _fill in from `evidence/f4-*`_ | | `campus_cidrs` exempt from the rate rule (change C12) |

---

## F1 – Loss of one Availability Zone

**What fails:** everything in AZ-a: the DB primary, the AZ-a Lambda ENIs and the AZ-a endpoint ENIs.

**How:** `scripts/failure/f1-az-loss.sh` pins every VPC Lambda to the AZ-b subnet (compute loses AZ-a) and runs `aws rds reboot-db-instance --force-failover` (the DB loses AZ-a). Run `scripts/failure/probe.sh f1 600` in a second terminal at the same time.

**Expected impact on the infrastructure:**
- RDS promotes the standby in AZ-b and the endpoint DNS flips: about 60–120 s with no DB.
- RDS Proxy keeps client connections open and reconnects to the new primary. In-flight queries fail with `57P01` / `ECONNRESET`, and `db.js` retries them once.
- Lambda keeps serving from AZ-b. With no NAT there is no per-AZ egress to lose; the SQS and Secrets Manager endpoints still have their AZ-b ENIs.
- CloudWatch: RDS event "failover" goes to SNS; API 5xx spike and Lambda errors; the dashboard shows `dbSubnet` in `/api/health` changing from `private-data AZ-a` to `AZ-b`.

**Measure:** RTO = the failed window in `evidence/f1-probe.csv` (first to last non-200). RPO = "acknowledged autosaves lost" in the same file. It must be 0, because Multi-AZ replication is synchronous.

**Fix / likely solution:** already in place (Multi-AZ, Proxy, two-AZ subnets). If the measured window is too long, use the Proxy's failover-aware DNS and shorter client retry back-off (the frontend retries every 30 s; drop it to 5 s after a failure).

**Restore:** `terraform -chdir=infra apply` puts the Lambdas back in both AZs.

## F2 – Data corruption: point-in-time restore

**What fails:** the data, not the infrastructure. Example: a tutor script or bad migration deletes an exam's answers at 10:02.

**How:** `scripts/failure/f2-pitr-restore.sh` reads `LatestRestorableTime` (this is the RPO) and restores the database to a new instance, timing until it is available (this is most of the RTO). Then it deletes the test instance.

**Expected impact:** the platform should go read-only (maintenance page) while the restored DB is checked and swapped in. Answers saved after the restore point but before the incident are recovered from the restored copy.

**Expected:** RDS uploads transaction logs about every 5 minutes, so `now − LatestRestorableTime` ≤ 5 min (meets RPO). A 50 GB instance typically restores in 15–40 min, plus about 5 min to point RDS Proxy at it (meets the 60-min RTO with little margin).

**Fix / likely solution:** keep the DB small (archive old attempts), rehearse the runbook each term, and have Terraform hold the proxy target as a variable so the cut-over is one `apply`. Option for a faster RTO: keep a delayed logical replica (extra cost).

## F3 – Bad deployment

**What fails:** a release with a broken setting (simulated: `DB_HOST=broken.invalid`) is published and the `live` alias points to it.

**How:** `scripts/failure/f3-bad-deploy.sh` publishes the broken version, moves the alias, polls `/api/health` until it fails (detection), then moves the alias back to the last good version (rollback) and times the recovery.

**Expected impact:** 100 % of API calls fail with 500. Autosaves are held in the browser. The `api-5xx` alarm fires after 3 one-minute periods.

**Expected:** RPO 0 (the bad version writes nothing). RTO is detection (≤ 3 min by alarm, seconds by the probe) plus rollback (alias switch, < 10 s).

**Fix / likely solution:** rollback by alias is instant. The next step would be CodeDeploy canary traffic shifting on the alias (10 % for 5 min with automatic rollback on the 5xx alarm), so a bad release reaches only a fraction of users.

## F4 – Exam hall blocked by the WAF rate limit

**What fails:** the WAF per-IP rate rule treats a campus NAT address, shared by a whole exam hall, as one abusive client.

**How:** set `waf_rate_limit = 500` (scaled down so a laptop can trip it) and `campus_cidrs = []`, apply, and run `scripts/failure/f4-exam-hall-waf.sh before`: 300 virtual students from one IP. Then add your IP to `campus_cidrs`, apply, and run `... after`.

**Expected impact (before):** once the IP passes the limit in the 5-minute window, WAF returns 403 to every student in the hall. `BlockedRequests{Rule=RateLimitPerIP}` rises and k6 `http_req_failed` jumps. Answers stay in the browser (RPO 0), but students cannot save or submit until the window resets (≈ 5 min, then it repeats).

**Expected (after fix):** 0 blocked requests from the campus range, while the rate limit still protects against every other IP.

**Fix:** change C12, `campus_cidrs` scope-down on the rate rule. Ask university IT for the exam-hall NAT ranges before go-live.

---

## Other failures considered (reasoned, not run)

| Failure | Impact | Handling |
|---|---|---|
| SES rejects or throttles email | Result emails delayed | `email` queue retries, then DLQ (alarm), then redrive after the fix. No data loss. |
| A worker Lambda throws (poison message) | One upload not recorded / one attempt not marked | `ReportBatchItemFailures` isolates the message; after 5 tries it goes to the DLQ with an alarm; redrive after the fix |
| Region outage (Singapore) | Full outage | Accepted. RTO 1 h cannot be met without a second Region; option: cross-region snapshot copy (≈ $5/month) for a multi-hour recovery |
| KMS key disabled | Uploads, DB and logs unreadable | Accepted risk; deletion has a 7-day window, admin-only IAM and CloudTrail alerts |
