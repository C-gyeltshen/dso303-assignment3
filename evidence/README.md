# Assignment 3 evidence

## Already recorded

| Evidence | Where | Result |
|---|---|---|
| Singapore and Mumbai prices from the AWS Price List API, 24 Nov 2026 | [`../docs/pricing-sources.md`](../docs/pricing-sources.md) | Every unit price with its usage type and publication date |
| Latency from Thimphu, Bhutan, 24 Nov 2026 | [`../docs/service-comparisons.md`](../docs/service-comparisons.md#latency-for-users-in-bhutan-measured) | Singapore median 110 ms, Mumbai 97 ms |
| Cloud Architecture Lab: A3 design at a 100× spike | [`../implementation/lab/a3-L1-exam-start-100x.json`](../implementation/lab/a3-L1-exam-start-100x.json) | HTTP 200, 185 ms, no bottlenecks reported |
| Cloud Architecture Lab: Analyze tab on the A3 design | [`../implementation/load-test.md`](../implementation/load-test.md) | 0 single points of failure, 0 bottlenecks; risks flagged: 1 task per AZ, plain HTTP from ALB to tasks, Cognito dependency concentration |
| AZ-A outage with the same engine (Assignment 2 build) | `../../evidence/exam-platform-06-az-a-failure-exam-start.*` | HTTP 200, ALB moved to AZ-B, Aurora failover about 35 s |

## Still to add before you submit

| # | What | How |
|---|---|---|
| 1 | AWS Pricing Calculator estimate (both groups) | Follow [`costed-estimate.md`](../implementation/costed-estimate.md). Save the share link, CSV, PDF and screenshots here |
| 2 | Optimisation before/after screenshots | One pair per optimisation from the calculator |
| 3 | Failure tests F1–F4 in the lab | Load each `a3-F*.json`, run it, then **Download PNG + JSON** into this folder |
| 4 | Load test with CloudWatch graphs (real AWS) | The procedure in [`load-test.md`](../implementation/load-test.md); put before/after graphs in `load-test/` |
