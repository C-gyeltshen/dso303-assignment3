#!/usr/bin/env bash
# Simulates the loss of Availability Zone A on the real AWS deployment and records evidence.
#   1. Polls /api/health every 2 s (shows which AZ the DB primary is in) -> evidence/az-failover-log.txt
#   2. Removes AZ-a subnets from every Lambda (compute "loses" AZ-a)
#   3. Forces an RDS Multi-AZ failover (primary moves to the standby AZ)
# Restore afterwards with:  terraform -chdir=infra apply   (puts Lambdas back in both AZs)
# Run scripts/failure/probe.sh in a second terminal at the same time to measure RPO.
set -euo pipefail

cd "$(dirname "$0")/../.."
URL=$(terraform -chdir=infra output -raw site_url)
DB=$(terraform -chdir=infra output -raw db_instance_id)
PROJECT=${PROJECT:-exam-platform}
LOG=evidence/f1-az-loss-log.txt
mkdir -p evidence
: > "$LOG"

poll() {
  while true; do
    ts=$(date -u +%H:%M:%S)
    body=$(curl -s -m 5 "$URL/api/health" || echo '{"ok":false,"error":"request failed"}')
    echo "$ts $body" | tee -a "$LOG"
    sleep 2
  done
}

echo "== Before: DB primary in $(aws rds describe-db-instances --db-instance-identifier "$DB" --query 'DBInstances[0].AvailabilityZone' --output text)" | tee -a "$LOG"
poll & POLL_PID=$!
trap 'kill $POLL_PID 2>/dev/null || true' EXIT
sleep 10

# --- Compute: pin every function to the AZ-b app subnet only ---
SUBNET_B=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=${PROJECT}-app-*b" --query 'Subnets[0].SubnetId' --output text)
SG=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${PROJECT}-lambda-sg" --query 'SecurityGroups[0].GroupId' --output text)
for fn in api marker upload-processor notifier migrate; do   # mailer/admin run outside the VPC
  echo "== Removing AZ-a from ${PROJECT}-${fn}" | tee -a "$LOG"
  aws lambda update-function-configuration --function-name "${PROJECT}-${fn}" \
    --vpc-config "SubnetIds=${SUBNET_B},SecurityGroupIds=${SG}" > /dev/null
done

# --- Database: force Multi-AZ failover ---
echo "== $(date -u +%H:%M:%S) Forcing RDS failover" | tee -a "$LOG"
aws rds reboot-db-instance --db-instance-identifier "$DB" --force-failover > /dev/null
aws rds wait db-instance-available --db-instance-identifier "$DB"
echo "== $(date -u +%H:%M:%S) DB available again, primary now in $(aws rds describe-db-instances --db-instance-identifier "$DB" --query 'DBInstances[0].AvailabilityZone' --output text)" | tee -a "$LOG"
sleep 30
FIRST_FAIL=$(grep -m1 '"ok":false\|request failed\|Internal' "$LOG" | cut -d' ' -f1 || true)
LAST_FAIL=$(grep '"ok":false\|request failed\|Internal' "$LOG" | tail -1 | cut -d' ' -f1 || true)
echo "== Measured outage window (health check): ${FIRST_FAIL:-none} -> ${LAST_FAIL:-none}" | tee -a "$LOG"
echo "== Done. See $LOG. Restore both AZs with: terraform -chdir=infra apply" | tee -a "$LOG"
