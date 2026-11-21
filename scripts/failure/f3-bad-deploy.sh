#!/usr/bin/env bash
# F3 – a bad release reaches production (simulated by publishing a version with a broken
# DB_HOST and pointing the `live` alias at it), then rollback by moving the alias back.
# Measures time to detect (first 5xx / alarm) and time to recover.
#   ./scripts/failure/f3-bad-deploy.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
FN=$(terraform -chdir=infra output -raw api_function)
URL=$(terraform -chdir=infra output -raw site_url)
LOG=evidence/f3-bad-deploy-log.txt
: > "$LOG"
say() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$LOG"; }

GOOD=$(aws lambda get-alias --function-name "$FN" --name live --query FunctionVersion --output text)
say "live alias -> version $GOOD (good)"

ENV=$(aws lambda get-function-configuration --function-name "$FN" --query 'Environment.Variables' --output json)
BAD_ENV=$(python3 -c "import json,sys;e=json.loads(sys.argv[1]);e['DB_HOST']='broken.invalid';print(json.dumps({'Variables':e}))" "$ENV")
aws lambda update-function-configuration --function-name "$FN" --environment "$BAD_ENV" > /dev/null
aws lambda wait function-updated --function-name "$FN"
BAD=$(aws lambda publish-version --function-name "$FN" --description "F3 bad release" --query Version --output text)
aws lambda update-alias --function-name "$FN" --name live --function-version "$BAD" > /dev/null
T0=$(date -u +%s); say "BAD release live (version $BAD)"

for i in $(seq 1 30); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL/api/health")
  say "health $CODE"
  [ "$CODE" != "200" ] && break
  sleep 2
done
T1=$(date -u +%s); say "Detected after $((T1 - T0)) s (in production: API 5xx alarm, 3 x 1-min periods)"

# Rollback = point the alias back to the last good version (what the pipeline's revert would do).
aws lambda update-alias --function-name "$FN" --name live --function-version "$GOOD" > /dev/null
aws lambda update-function-configuration --function-name "$FN" --environment "{\"Variables\":$ENV}" > /dev/null
until [ "$(curl -s -o /dev/null -w "%{http_code}" "$URL/api/health")" = "200" ]; do sleep 1; done
T2=$(date -u +%s); say "Recovered $((T2 - T1)) s after rollback started. Outage = $((T2 - T0)) s. RPO = 0 (no data written by the bad version)."
