# Evidence

## Assignment 3

### Pricing Calculator exports (required)
- [ ] `calculator-normal.csv` / `.pdf` – normal-month estimate (A3)
- [ ] `calculator-exam.csv` / `.pdf` – exam-month estimate (A3)
- [ ] `calculator-a2-normal.csv` – A2 baseline (to show the savings)
- [ ] `calculator-mumbai.csv` – region comparison
- [x] `cost-model.csv` – line items from `docs/cost-model.py` (generated)

### Load test
- [ ] `loadtest-R1-k6.json`, `loadtest-R1-metrics.json`, `loadtest-R1-dashboard.png` – baseline (bottleneck visible)
- [ ] `loadtest-R2-*` – step-up (if R1 passed)
- [ ] `loadtest-R3-k6.json`, `loadtest-R3-metrics.json`, `loadtest-R3-dashboard.png` – after the fix

### Failure tests
- [ ] `f1-az-loss-log.txt`, `f1-probe.csv`, screenshot of the RDS failover event
- [ ] `f2-pitr-log.txt`
- [ ] `f3-bad-deploy-log.txt`, screenshot of the 5xx alarm
- [ ] `f4-before-k6.json`, `f4-before-waf-blocked.txt`, `f4-after-*`

### Latency from Bhutan
- [ ] `latency-thimphu.png` – cloudping.info (or curl timings) to ap-southeast-1 and ap-south-1

## Assignment 2 (kept)
Lab screenshots (`lab-0*.png`) and AWS deployment screenshots, as listed in the Assignment 2 README.
