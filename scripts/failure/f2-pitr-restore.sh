#!/usr/bin/env bash
# F2 – data corruption / accidental deletion: point-in-time restore.
# Measures RPO (now - LatestRestorableTime) and RTO (time to a usable restored DB).
# Restores to a NEW single-AZ instance (cheaper for the test), then deletes it.
#   ./scripts/failure/f2-pitr-restore.sh            (takes ~15-40 min)
set -euo pipefail
cd "$(dirname "$0")/../.."
DB=$(terraform -chdir=infra output -raw db_instance_id)
NEW="${DB}-pitr-test"
LOG=evidence/f2-pitr-log.txt
: > "$LOG"
say() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$LOG"; }

T0=$(date -u +%s)
LRT=$(aws rds describe-db-instances --db-instance-identifier "$DB" --query 'DBInstances[0].LatestRestorableTime' --output text)
LAG=$(( T0 - $(date -u -d "$LRT" +%s) ))
say "Incident declared. LatestRestorableTime=$LRT  => worst-case data loss (RPO) = ${LAG}s (target <= 300s)"

SUBNETS=$(aws rds describe-db-instances --db-instance-identifier "$DB" --query 'DBInstances[0].DBSubnetGroup.DBSubnetGroupName' --output text)
SG=$(aws rds describe-db-instances --db-instance-identifier "$DB" --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' --output text)
say "Starting restore to $NEW"
aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier "$DB" \
  --target-db-instance-identifier "$NEW" --use-latest-restorable-time \
  --db-subnet-group-name "$SUBNETS" --vpc-security-group-ids "$SG" \
  --no-multi-az --no-publicly-accessible --db-instance-class db.t4g.medium > /dev/null
aws rds wait db-instance-available --db-instance-identifier "$NEW"
T1=$(date -u +%s)
say "Restored instance available after $(( (T1 - T0) / 60 )) min $(( (T1 - T0) % 60 )) s"
say "Production cut-over (runbook): register $NEW as the RDS Proxy target, or rename instances; estimate +5 min."
say "Measured RTO ~ $(( (T1 - T0) / 60 + 5 )) min (target <= 60 min)"

read -r -p "Delete the test instance $NEW now? [y/N] " A
if [ "${A:-N}" = "y" ]; then
  aws rds delete-db-instance --db-instance-identifier "$NEW" --skip-final-snapshot --delete-automated-backups > /dev/null
  say "Deleting $NEW"
fi
