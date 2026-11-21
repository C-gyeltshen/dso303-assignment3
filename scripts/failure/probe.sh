#!/usr/bin/env bash
# RPO/RTO probe: one student autosaves every 2 s with an increasing clientSeq and logs each result.
# After the failure ends it reads the attempt back: if the stored clientSeq >= the last
# acknowledged (HTTP 200) seq, no acknowledged answer was lost  => RPO = 0.
#   ./scripts/failure/probe.sh <label> <duration-seconds>
# Needs scripts/loadtest/tokens.json (run scripts/loadtest/setup.sh 1 1 first).
set -uo pipefail
cd "$(dirname "$0")/../.."
LABEL=${1:-probe}; DURATION=${2:-600}
URL=$(terraform -chdir=infra output -raw site_url)
TOKEN=$(python3 -c "import json;print(json.load(open('scripts/loadtest/tokens.json'))[0])")
EXAM=$(python3 -c "import json;print(json.load(open('/tmp/lt-seed.json'))['loadTestExamIds'][0])" 2>/dev/null || echo "${EXAM_ID:?set EXAM_ID}")
LOG=evidence/${LABEL}-probe.csv
H=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

ATTEMPT=$(curl -s -X POST "${H[@]}" "$URL/api/exams/$EXAM/start" | python3 -c "import json,sys;print(json.load(sys.stdin)['attempt']['id'])")
SEQ=$(curl -s "${H[@]}" "$URL/api/attempts/$ATTEMPT" | python3 -c "import json,sys;print(json.load(sys.stdin)['clientSeq'])")
echo "utc,seq,http_status,ms" > "$LOG"
LAST_OK=$SEQ; FIRST_FAIL=""; LAST_FAIL=""
END=$(( $(date +%s) + DURATION ))
while [ "$(date +%s)" -lt "$END" ]; do
  SEQ=$((SEQ + 1))
  OUT=$(curl -s -o /dev/null -m 10 -w "%{http_code} %{time_total}" -X PUT "${H[@]}" \
        -d "{\"answers\":{\"probe\":$SEQ},\"clientSeq\":$SEQ}" "$URL/api/attempts/$ATTEMPT/answers")
  CODE=${OUT% *}; MS=$(python3 -c "print(round(${OUT#* }*1000))")
  NOW=$(date -u +%H:%M:%S)
  echo "$NOW,$SEQ,$CODE,$MS" >> "$LOG"
  if [ "$CODE" = "200" ]; then LAST_OK=$SEQ; else [ -z "$FIRST_FAIL" ] && FIRST_FAIL=$NOW; LAST_FAIL=$NOW; fi
  sleep 2
done
STORED=$(curl -s "${H[@]}" "$URL/api/attempts/$ATTEMPT" | python3 -c "import json,sys;print(json.load(sys.stdin)['clientSeq'])")
{
  echo "# last acknowledged seq: $LAST_OK, stored seq after recovery: $STORED"
  if [ "$STORED" -ge "$LAST_OK" ]; then echo "# RPO: 0 acknowledged autosaves lost"; else echo "# RPO: $((LAST_OK - STORED)) acknowledged autosaves LOST"; fi
  echo "# failed window: ${FIRST_FAIL:-none} -> ${LAST_FAIL:-none} (RTO for writes)"
} | tee -a "$LOG"
