#!/usr/bin/env bash
# F4 – a whole exam hall behind ONE campus NAT IP trips the WAF per-IP rate limit.
# Step 1 (before fix): set waf_rate_limit = 500 and campus_cidrs = [] and apply.
# Step 2: run this script -> 300 "students" from your single IP; WAF starts returning 403.
# Step 3 (fix): add your IP to campus_cidrs, apply, run again -> no 403s.
#   ./scripts/failure/f4-exam-hall-waf.sh <label>
set -euo pipefail
cd "$(dirname "$0")/../.."
LABEL=${1:-f4}
URL=$(terraform -chdir=infra output -raw site_url)
EXAM_IDS=$(python3 -c "import json;print(','.join(map(str,json.load(open('/tmp/lt-seed.json'))['loadTestExamIds'])))")
echo "Your public IP: $(curl -s https://checkip.amazonaws.com) (put it in campus_cidrs as x.x.x.x/32 for the fix)"
START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
(cd scripts/loadtest && k6 run -e BASE_URL="$URL" -e EXAM_IDS="$EXAM_IDS" -e STUDENTS=300 \
   -e START_WINDOW=30 -e SAVE_INTERVAL=3 -e HOLD=240 --summary-export "../../evidence/${LABEL}-k6.json" exam-peak.js) || true
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
aws cloudwatch get-metric-statistics --region us-east-1 --namespace AWS/WAFV2 --metric-name BlockedRequests \
  --dimensions Name=WebACL,Value=exam-platform-waf Name=Rule,Value=RateLimitPerIP \
  --start-time "$START" --end-time "$END" --period 60 --statistics Sum --output table | tee "evidence/${LABEL}-waf-blocked.txt"
