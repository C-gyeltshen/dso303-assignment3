#!/usr/bin/env bash
# Prepares a load test: creates the load-test exams and N student users with fresh tokens.
#   ./scripts/loadtest/setup.sh [users=500] [exams=6]
set -euo pipefail
cd "$(dirname "$0")/../.."
USERS=${1:-500}; EXAMS=${2:-6}
TF="terraform -chdir=infra output -raw"

aws lambda invoke --function-name "$($TF migrate_function)" --cli-binary-format raw-in-base64-out \
  --payload "{\"loadtest\":{\"exams\":$EXAMS}}" /tmp/lt-seed.json > /dev/null
EXAM_IDS=$(python3 -c "import json;print(','.join(map(str,json.load(open('/tmp/lt-seed.json'))['loadTestExamIds'])))")

(cd scripts/loadtest && npm install --silent && node make-tokens.mjs "$($TF user_pool_id)" "$($TF user_pool_client_id)" "$USERS")

cat <<EOF

Ready. Run (from scripts/loadtest):
  k6 run -e BASE_URL=$($TF site_url) -e EXAM_IDS=$EXAM_IDS exam-peak.js
Lower-VU equivalent of 3,000 students (same 100 autosaves/s):
  k6 run -e BASE_URL=$($TF site_url) -e EXAM_IDS=$EXAM_IDS -e STUDENTS=1000 -e SAVE_INTERVAL=10 exam-peak.js
Write down the UTC start and end times, then:
  ./scripts/loadtest/collect-metrics.sh <label> <start> <end>
EOF
