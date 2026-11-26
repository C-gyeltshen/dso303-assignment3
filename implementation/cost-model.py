"""Assignment 3 cost model: ap-southeast-1 (Singapore), USD, On-Demand.
Prices come from the AWS Price List API (same data as the AWS Pricing Calculator),
read on 24 Nov 2026. Each price lists its usage type."""
import json

H = 730  # hours per month (AWS Pricing Calculator convention)

P = {  # unit prices, Singapore
    "fargate_arm_vcpu_h": 0.04045, "fargate_arm_gb_h": 0.00442,          # APS1-Fargate-ARM-*
    "fargate_x86_vcpu_h": 0.05056, "fargate_x86_gb_h": 0.00553,          # APS1-Fargate-*
    "alb_h": 0.0252, "alb_lcu_h": 0.008,                                 # APS1-LoadBalancerUsage / LCUUsage
    "nat_h": 0.059, "nat_gb": 0.059,                                     # AWS VPC pricing page (Singapore row)
    "ipv4_h": 0.005,                                                     # APS1-PublicIPv4:InUseAddress
    "aurora_t4g_medium_h": 0.114, "aurora_r6g_large_h": 0.313,           # APS1-InstanceUsage (Aurora PostgreSQL)
    "aurora_storage_gb": 0.11, "aurora_io_m": 0.22, "aurora_backup_gb": 0.023,
    "aurora_sv2_acu_h": 0.20,                                            # APS1-Aurora:ServerlessV2Usage
    "rds_proxy_vcpu_h": 0.018,                                           # APS1-RDS:ProxyUsage
    "rds_pg_t4g_medium_maz_h": 0.203, "rds_maz_gp3_gb": 0.276,           # RDS PostgreSQL Multi-AZ
    "redis_t4g_small_h": 0.048,                                          # ElastiCache Redis cache.t4g.small
    "ddb_wru_m": 0.71, "ddb_rru_m": 0.1425, "ddb_gb": 0.285, "ddb_pitr_gb": 0.228,
    "s3_std_gb": 0.025, "s3_ia_gb": 0.0138, "s3_int_fa_gb": 0.025, "s3_int_ia_gb": 0.0138,
    "s3_int_aia_gb": 0.005, "s3_int_monitor_1k": 0.0025, "s3_glacier_gb": 0.0045, "s3_gir_gb": 0.005,
    "s3_put_1k": 0.005, "s3_get_10k": 0.004,
    "cf_https_10k": 0.012, "cf_out_india_gb": 0.109, "cf_to_origin_gb": 0.06,  # AmazonCloudFront IN-/AP-
    "dt_out_gb": 0.12, "dt_regional_gb": 0.01,                           # AWSDataTransfer APS1
    "waf_acl": 5.0, "waf_rule": 1.0, "waf_req_m": 0.60,
    "lambda_req_m": 0.20, "lambda_arm_gbs": 0.0000133334,
    "sqs_req_m": 0.40, "eb_event_m": 1.00, "ses_email": 0.0001,
    "cw_logs_gb": 0.70, "cw_logs_store_gb": 0.03, "cw_metric": 0.30, "cw_alarm": 0.10,
    "xray_trace": 0.000005,
    "kms_key": 1.0, "kms_req_10k": 0.03, "secret": 0.40, "secret_api_10k": 0.05,
    "gd_cloudtrail_event": 0.0000046, "gd_logs_gb": 1.15,
    "r53_zone": 0.50, "r53_query_m": 0.40,
    "codebuild_arm_small_min": 0.004, "ecr_gb": 0.10,
    "ddb_backup_warm_gb": 0.114,
}

def task_h(arch="arm", vcpu=0.5, gb=1.0):
    if arch == "arm":
        return vcpu * P["fargate_arm_vcpu_h"] + gb * P["fargate_arm_gb_h"]
    return vcpu * P["fargate_x86_vcpu_h"] + gb * P["fargate_x86_gb_h"]

# ---------------- usage assumptions (per month) ----------------
U = {
    "normal": dict(
        api_req_m=15, static_req_m=8,           # millions of requests through CloudFront
        cf_out_gb=300, cf_to_origin_gb=10,
        extra_task_h=0,                          # Fargate task-hours above the 2-task baseline
        alb_lcu=1.0,
        nat_gb=25,
        ddb_wru_m=1.0, ddb_rru_m=2.0, ddb_gb=5,
        aurora_io_m=30, aurora_gb=30,
        logs_gb=12, traces=750_000, emails=30_000, events_m=0.05,
        sqs_req_m=0.3, lambda_req_m=0.1,
        kms_req=300_000, secret_api=60_000,
        s3_std_gb=50, s3_ia_gb=150, s3_glacier_gb=100, s3_puts=80_000,
        s3_direct_out_gb=60, cross_az_gb=40, ct_events=400_000, gd_logs_gb=3,
        dns_m=5,
    ),
    "exam": dict(
        api_req_m=31, static_req_m=12,
        cf_out_gb=450, cf_to_origin_gb=40,
        extra_task_h=10 * 60 + 100,              # 10 extra tasks x 60 scheduled exam hours + 100 h target-tracking
        alb_lcu=1.5,
        nat_gb=50,
        ddb_wru_m=15.4, ddb_rru_m=3.0, ddb_gb=8,
        aurora_io_m=80, aurora_gb=30,
        logs_gb=30, traces=1_550_000, emails=60_000, events_m=0.2,
        sqs_req_m=1.2, lambda_req_m=0.3,
        kms_req=600_000, secret_api=120_000,
        s3_std_gb=90, s3_ia_gb=150, s3_glacier_gb=100, s3_puts=150_000,
        s3_direct_out_gb=90, cross_az_gb=80, ct_events=500_000, gd_logs_gb=5,
        dns_m=8,
    ),
}

def month(profile, design="a3"):
    u = U[profile]
    c = {}
    # ---- compute
    if design == "a3":
        c["ECS Fargate (Graviton, 0.5 vCPU / 1 GB)"] = (2 * H + u["extra_task_h"]) * task_h("arm")
    else:  # A2: x86, minimum 4 tasks, scheduled 12
        c["ECS Fargate (x86, 0.5 vCPU / 1 GB)"] = (4 * H + (u["extra_task_h"] * 0.8)) * task_h("x86")
    c["Application Load Balancer"] = H * P["alb_h"] + H * u["alb_lcu"] * P["alb_lcu_h"]
    lam_gbs = u["lambda_req_m"] * 1e6 * 0.5 * 0.512
    c["Lambda (marking, notify)"] = max(0, u["lambda_req_m"] - 1) * P["lambda_req_m"] + max(0, lam_gbs - 400_000) * P["lambda_arm_gbs"]
    # ---- data
    inst = P["aurora_t4g_medium_h"] if design == "a3" else P["aurora_r6g_large_h"]
    c["Aurora PostgreSQL (writer + reader)"] = 2 * H * inst + u["aurora_gb"] * P["aurora_storage_gb"] + u["aurora_io_m"] * P["aurora_io_m"]
    if design == "a2":
        c["RDS Proxy"] = 2 * 2 * H * P["rds_proxy_vcpu_h"]
        c["ElastiCache Redis (2 x cache.t4g.small)"] = 2 * H * P["redis_t4g_small_h"]
    c["DynamoDB on-demand + PITR"] = u["ddb_wru_m"] * P["ddb_wru_m"] + u["ddb_rru_m"] * P["ddb_rru_m"] + max(0, u["ddb_gb"] - 25) * P["ddb_gb"] + u["ddb_gb"] * P["ddb_pitr_gb"]
    c["S3 assignments + web bucket"] = (u["s3_std_gb"] + 1) * P["s3_std_gb"] + u["s3_ia_gb"] * P["s3_ia_gb"] + u["s3_glacier_gb"] * P["s3_glacier_gb"] + u["s3_puts"] / 1000 * P["s3_put_1k"]
    # ---- edge
    cf_req = u["api_req_m"] + u["static_req_m"]
    c["CloudFront"] = max(0, cf_req - 10) * 100 * P["cf_https_10k"] + max(0, u["cf_out_gb"] - 1024) * P["cf_out_india_gb"] + u["cf_to_origin_gb"] * P["cf_to_origin_gb"]
    c["AWS WAF (1 ACL, 4 rules)"] = P["waf_acl"] + 4 * P["waf_rule"] + cf_req * P["waf_req_m"]
    c["Route 53"] = P["r53_zone"] + u["dns_m"] * P["r53_query_m"]
    # ---- messaging
    c["SQS + EventBridge"] = max(0, u["sqs_req_m"] - 1) * P["sqs_req_m"] + u["events_m"] * P["eb_event_m"]
    c["SES email"] = u["emails"] * P["ses_email"]
    # ---- security
    keys = 2 if design == "a3" else 3
    c["KMS"] = keys * P["kms_key"] + max(0, u["kms_req"] - 20_000) / 10_000 * P["kms_req_10k"]
    c["Secrets Manager"] = (1 if design == "a3" else 2) * P["secret"] + u["secret_api"] / 10_000 * P["secret_api_10k"]
    c["GuardDuty"] = u["ct_events"] * P["gd_cloudtrail_event"] + u["gd_logs_gb"] * P["gd_logs_gb"]
    # ---- hidden costs
    c["HIDDEN: NAT gateways (2) hours + processing"] = 2 * H * P["nat_h"] + u["nat_gb"] * P["nat_gb"]
    c["HIDDEN: public IPv4 (ALB 2 + NAT 2)"] = 4 * H * P["ipv4_h"]
    c["HIDDEN: data transfer out (S3 downloads, cross-AZ)"] = max(0, u["s3_direct_out_gb"] - 100) * P["dt_out_gb"] + u["cross_az_gb"] * 2 * P["dt_regional_gb"]
    logs = u["logs_gb"] if design == "a3" else u["logs_gb"] * 2.5   # A2: Container Insights + DEBUG logs, 1-year retention
    store = logs * (1 if design == "a3" else 12)
    c["HIDDEN: CloudWatch Logs, metrics, alarms"] = max(0, logs - 5) * P["cw_logs_gb"] + store * P["cw_logs_store_gb"] + 10 * P["cw_metric"] + 10 * P["cw_alarm"]
    c["HIDDEN: X-Ray traces"] = max(0, u["traces"] - 100_000) * P["xray_trace"] * (1 if design == "a3" else 4)
    # backups: Aurora monthly snapshots kept 5 yr (year-1 average 6 snapshots) + DynamoDB PITR above
    if design == "a3":
        c["HIDDEN: backups (Aurora snapshots, AWS Backup)"] = 6 * u["aurora_gb"] * P["aurora_backup_gb"] + 4 * u["ddb_gb"] * P["ddb_backup_warm_gb"]
    else:  # A2: daily backups kept 5 yr + cross-Region copy
        c["HIDDEN: backups (Aurora snapshots, AWS Backup)"] = 180 * u["aurora_gb"] * P["aurora_backup_gb"] * 0.25 + 30 * u["ddb_gb"] * P["ddb_backup_warm_gb"] + 30 * 0.09
    c["CI/CD (CodeBuild, CodePipeline, ECR)"] = 300 * P["codebuild_arm_small_min"] + 3 * P["ecr_gb"]
    c["Cognito (8,400 MAU, free tier 10,000)"] = 0.0
    return {k: round(v, 2) for k, v in c.items()}

def total(m): return round(sum(m.values()), 2)

if __name__ == "__main__":
    out = {}
    for d in ("a2", "a3"):
        n, e = month("normal", d), month("exam", d)
        out[d] = {"normal": n, "exam": e, "normal_total": total(n), "exam_total": total(e),
                  "annual": round(10 * total(n) + 2 * total(e), 2)}
        out[d]["avg_month"] = round(out[d]["annual"] / 12, 2)
        out[d]["per_student_year"] = round(out[d]["annual"] / 8000, 2)
    json.dump(out, open("cost-model-output.json", "w"), indent=1)
    for d in out:
        print(d, out[d]["normal_total"], out[d]["exam_total"], out[d]["annual"], out[d]["avg_month"], out[d]["per_student_year"])
    for k, v in out["a3"]["normal"].items():
        print(f"{v:8.2f}  {out['a3']['exam'][k]:8.2f}  {k}")
