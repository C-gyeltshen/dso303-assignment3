#!/usr/bin/env bash
# Pulls the CloudWatch metrics that prove (or rule out) each bottleneck for a test window.
#   ./scripts/loadtest/collect-metrics.sh <label> <start ISO-8601 UTC> <end ISO-8601 UTC>
#   e.g. ./scripts/loadtest/collect-metrics.sh run1-baseline 2026-11-25T03:00:00Z 2026-11-25T03:20:00Z
# Writes evidence/loadtest-<label>-metrics.json and prints the peak of each metric.
set -euo pipefail
cd "$(dirname "$0")/../.."
LABEL=$1; START=$2; END=$3
TF="terraform -chdir=infra output -raw"
REGION=$($TF region); FN=$($TF api_function); API=$($TF api_id); DB=$($TF db_instance_id); PROXY=$($TF proxy_name)
OUT=evidence/loadtest-${LABEL}-metrics.json

q() { # id namespace metric stat dims-json
  printf '{"Id":"%s","MetricStat":{"Metric":{"Namespace":"%s","MetricName":"%s","Dimensions":%s},"Period":60,"Stat":"%s"}}' "$1" "$2" "$3" "$5" "$4"
}
QUERIES="[
$(q apiCount AWS/ApiGateway Count Sum "[{\"Name\":\"ApiId\",\"Value\":\"$API\"},{\"Name\":\"Stage\",\"Value\":\"\$default\"}]"),
$(q api5xx AWS/ApiGateway 5xx Sum "[{\"Name\":\"ApiId\",\"Value\":\"$API\"},{\"Name\":\"Stage\",\"Value\":\"\$default\"}]"),
$(q api4xx AWS/ApiGateway 4xx Sum "[{\"Name\":\"ApiId\",\"Value\":\"$API\"},{\"Name\":\"Stage\",\"Value\":\"\$default\"}]"),
$(q apiP95 AWS/ApiGateway Latency p95 "[{\"Name\":\"ApiId\",\"Value\":\"$API\"},{\"Name\":\"Stage\",\"Value\":\"\$default\"}]"),
$(q lambdaConc AWS/Lambda ConcurrentExecutions Maximum "[{\"Name\":\"FunctionName\",\"Value\":\"$FN\"}]"),
$(q lambdaThrottles AWS/Lambda Throttles Sum "[{\"Name\":\"FunctionName\",\"Value\":\"$FN\"}]"),
$(q lambdaErrors AWS/Lambda Errors Sum "[{\"Name\":\"FunctionName\",\"Value\":\"$FN\"}]"),
$(q lambdaP95 AWS/Lambda Duration p95 "[{\"Name\":\"FunctionName\",\"Value\":\"$FN\"}]"),
$(q pcSpill AWS/Lambda ProvisionedConcurrencySpilloverInvocations Sum "[{\"Name\":\"FunctionName\",\"Value\":\"$FN\"},{\"Name\":\"Resource\",\"Value\":\"$FN:live\"}]"),
$(q dbCpu AWS/RDS CPUUtilization Maximum "[{\"Name\":\"DBInstanceIdentifier\",\"Value\":\"$DB\"}]"),
$(q dbCredits AWS/RDS CPUCreditBalance Minimum "[{\"Name\":\"DBInstanceIdentifier\",\"Value\":\"$DB\"}]"),
$(q dbConns AWS/RDS DatabaseConnections Maximum "[{\"Name\":\"DBInstanceIdentifier\",\"Value\":\"$DB\"}]"),
$(q proxyClients AWS/RDS ClientConnections Maximum "[{\"Name\":\"ProxyName\",\"Value\":\"$PROXY\"}]"),
$(q proxyBorrow AWS/RDS DatabaseConnectionsBorrowLatency Maximum "[{\"Name\":\"ProxyName\",\"Value\":\"$PROXY\"}]")
]"

aws cloudwatch get-metric-data --region "$REGION" --start-time "$START" --end-time "$END" \
  --metric-data-queries "$QUERIES" --output json > "$OUT"

python3 - "$OUT" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(f"{'metric':<18}{'peak':>12}{'sum':>14}")
for r in d["MetricDataResults"]:
    v = r["Values"]
    print(f"{r['Id']:<18}{(max(v) if v else 0):>12.1f}{(sum(v) if v else 0):>14.1f}")
PY
echo "saved $OUT"
