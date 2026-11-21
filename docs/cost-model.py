#!/usr/bin/env python3
"""
Cost model for the exam platform in Asia Pacific (Singapore), ap-southeast-1.

Every unit price is listed once in PRICES with its source and status:
  sourced = taken from the cited page on the date checked
  verify  = best available figure; confirm it in the AWS Pricing Calculator and edit here
Run:  python3 docs/cost-model.py            -> prints markdown tables used in docs/cost-report.md
      python3 docs/cost-model.py --csv      -> writes evidence/cost-model.csv
"""
import csv
import sys

DATE_CHECKED = "2026-11-21"
H = 730  # hours per month (AWS Pricing Calculator convention)

# ---------------------------------------------------------------- prices (USD)
PRICES = {
    # key: (price, unit, source, status)
    "lambda_req":        (0.20 / 1e6, "per request", "aws.amazon.com/lambda/pricing", "verify"),
    "lambda_gbs_arm":    (0.0000133334, "per GB-s (arm64)", "aws.amazon.com/lambda/pricing", "verify"),
    "lambda_pc_gbs_arm": (0.0000033334, "per GB-s provisioned (arm64)", "aws.amazon.com/lambda/pricing", "verify"),
    "apigw_http":        (1.20 / 1e6, "per request (first 300M)", "aws.amazon.com/api-gateway/pricing (US $1.00; APAC higher)", "verify"),
    "cf_https_10k":      (0.012, "per 10k HTTPS requests (Asia Pacific)", "cloudzero.com/blog/cloudfront-pricing", "sourced"),
    "cf_free_req":       (10_000_000, "free requests / month", "aws.amazon.com/free/networking", "sourced"),
    "cf_free_gb":        (1024, "free GB out / month", "aws.amazon.com/free/networking", "sourced"),
    "cf_dto_india":      (0.109, "per GB (India)", "aws.amazon.com/cloudfront/pricing", "verify"),
    "waf_acl":           (5.00, "per web ACL / month", "aws.amazon.com/waf/pricing", "verify"),
    "waf_rule":          (1.00, "per rule / month", "aws.amazon.com/waf/pricing", "verify"),
    "waf_req":           (0.60 / 1e6, "per request", "aws.amazon.com/waf/pricing", "verify"),
    "rds_t4g_medium_maz":    (148.0, "per month, Multi-AZ on-demand (2 x $74)", "bytebase.com/dbcost (updated 2026-07-20)", "sourced"),
    "rds_t4g_medium_maz_ri": (108.0, "per month, Multi-AZ 1-yr RI (2 x $54)", "bytebase.com/dbcost (updated 2026-07-20)", "sourced"),
    "rds_t4g_large_maz":     (296.0, "per month, Multi-AZ on-demand (2 x $148)", "bytebase.com/dbcost", "sourced"),
    "rds_gp3_maz":       (0.276, "per GB-month, Multi-AZ gp3", "aws.amazon.com/rds/postgresql/pricing", "verify"),
    "rds_cpu_credit":    (0.075, "per vCPU-hour surplus credits", "aws.amazon.com/rds/postgresql/pricing", "sourced"),
    "rds_snapshot":      (0.095, "per GB-month backup storage beyond free", "aws.amazon.com/rds/postgresql/pricing", "verify"),
    "rds_proxy_vcpu":    (0.018, "per vCPU-hour (min 2 vCPU)", "aws.amazon.com/rds/proxy/pricing (US $0.015)", "verify"),
    "nat_hour":          (0.059, "per NAT gateway-hour", "egresscost.com/aws/ap-southeast-1", "sourced"),
    "nat_gb":            (0.059, "per GB processed (some sources list $0.045)", "aws-nat-gateway-cost-calculator (aws.amazon.com/vpc/pricing)", "verify"),
    "vpce_hour":         (0.013, "per interface endpoint per AZ-hour", "aws.amazon.com/privatelink/pricing (US $0.01)", "verify"),
    "vpce_gb":           (0.01, "per GB processed", "aws.amazon.com/privatelink/pricing", "sourced"),
    "s3_std":            (0.025, "per GB-month S3 Standard", "aws.amazon.com/s3/pricing", "verify"),
    "s3_ia":             (0.0138, "per GB-month Standard-IA", "aws.amazon.com/s3/pricing", "verify"),
    "s3_gfr":            (0.0045, "per GB-month Glacier Flexible Retrieval", "aws.amazon.com/s3/pricing", "verify"),
    "s3_gda":            (0.002, "per GB-month Glacier Deep Archive", "aws.amazon.com/s3/pricing", "verify"),
    "s3_put_1k":         (0.005, "per 1,000 PUT/POST", "aws.amazon.com/s3/pricing", "verify"),
    "s3_transition_1k":  (0.05, "per 1,000 lifecycle transitions (avg)", "aws.amazon.com/s3/pricing", "verify"),
    "dto_internet":      (0.12, "per GB region -> internet", "egresscost.com/aws/ap-southeast-1", "sourced"),
    "dto_free_gb":       (100, "free GB / month, all regions", "aws.amazon.com/blogs/aws (Dec 2021)", "sourced"),
    "inter_az_gb":       (0.02, "per GB cross-AZ (0.01 each way)", "egresscost.com/aws/ap-southeast-1", "sourced"),
    "sqs_req":           (0.40 / 1e6, "per request after 1M free", "aws.amazon.com/sqs/pricing", "verify"),
    "ses_email":         (0.10 / 1000, "per email", "aws.amazon.com/ses/pricing", "verify"),
    "cognito_mau":       (0.015, "per MAU above 10,000 free (Essentials)", "aws.amazon.com/cognito/pricing", "sourced"),
    "kms_key":           (1.00, "per CMK / month", "aws.amazon.com/kms/pricing", "verify"),
    "kms_req":           (0.03 / 10000, "per request", "aws.amazon.com/kms/pricing", "verify"),
    "secret":            (0.40, "per secret / month", "aws.amazon.com/secrets-manager/pricing", "verify"),
    "secret_call":       (0.05 / 10000, "per API call", "aws.amazon.com/secrets-manager/pricing", "verify"),
    "cwl_ingest":        (0.70, "per GB Standard log ingestion (Singapore)", "dev.classmethod.jp (Singapore, 2023) / jdn.gov.my price list", "sourced"),
    "cwl_ingest_ia":     (0.35, "per GB Infrequent Access (50% of Standard)", "aws.amazon.com/blogs/aws (IA log class)", "sourced"),
    "cwl_store":         (0.03, "per GB-month archived", "dev.classmethod.jp (Singapore)", "sourced"),
    "cw_alarm":          (0.10, "per alarm / month after 10 free", "aws.amazon.com/cloudwatch/pricing", "verify"),
    "xray_trace":        (5.00 / 1e6, "per trace recorded after 100k free", "aws.amazon.com/xray/pricing", "verify"),
    "route53_zone":      (0.50, "per hosted zone / month", "aws.amazon.com/route53/pricing", "verify"),
}
P = {k: v[0] for k, v in PRICES.items()}

# ---------------------------------------------------------------- workload
STUDENTS = 8000
USERS = 8400  # students + staff

def workload(profile):
    """Monthly volumes. Assumptions are documented in docs/cost-report.md section 1."""
    normal_api = 400 / 20 * 12 * 3600 * 30          # 400 concurrent, 1 call / 20 s, 12 h/day, 30 days
    w = {
        "api_requests": normal_api,                   # 25.92 M
        "static_requests": USERS * 20 * 6,            # 20 sessions x 6 files
        "uploads": 24_000, "upload_gb": 192.0,        # 3 uploads/student, 8 MB avg
        "emails": 24_000,                             # one tutor email per upload
        "marking_msgs": 0,
        "exam_hours_peak": 0,
    }
    if profile == "exam":
        autosaves = STUDENTS * 6 * 2 * 120             # 6 exams x 2 h x 120 saves/h = 11.52 M
        w.update({
            "api_requests": normal_api + autosaves + STUDENTS * 6 * 3,   # + start/submit/results
            "static_requests": USERS * 26 * 6,
            "uploads": 12_000, "upload_gb": 96.0,
            "emails": 12_000 + STUDENTS * 6,           # tutor emails + result emails
            "marking_msgs": STUDENTS * 6,
            "exam_hours_peak": 60,                     # hours/month with exam traffic (provisioned concurrency window)
        })
    return w

# ---------------------------------------------------------------- S3 storage (lifecycle simulation)
def s3_storage(month_index, archive_price, monthly_gb=176.0):
    """Storage cost in a given month (1-based) with Standard 30 d -> IA to 180 d -> archive -> delete at 60 months.
    monthly_gb = year average of new uploads (10 x 192 + 2 x 96) / 12 = 176 GB."""
    std = monthly_gb
    ia = monthly_gb * min(max(month_index - 1, 0), 5)
    arch = monthly_gb * min(max(month_index - 6, 0), 54)
    return std * P["s3_std"] + ia * P["s3_ia"] + arch * archive_price, (std, ia, arch)

def s3_year1_avg(archive_price):
    return sum(s3_storage(m, archive_price)[0] for m in range(1, 13)) / 12

# ---------------------------------------------------------------- line items
def lines(profile, design):
    """design: 'a2' = Assignment 2 as designed, priced in Singapore; 'a3' = cost-optimised revision."""
    w = workload(profile)
    exam = profile == "exam"
    a3 = design == "a3"
    L = []

    def add(service, item, cost, hidden=False):
        L.append((service, item, round(cost, 2), hidden))

    # --- Edge
    total_cf_req = w["api_requests"] + w["static_requests"]
    add("CloudFront", f"{total_cf_req/1e6:.1f} M HTTPS requests (10 M free)",
        max(total_cf_req - P["cf_free_req"], 0) / 1e4 * P["cf_https_10k"])
    dto_gb = w["api_requests"] * 3 / 1e6 + w["static_requests"] * 40 / 1e6  # 3 KB API, 40 KB avg static
    if a3:
        dto_gb += w["upload_gb"]  # O5: tutor downloads served through CloudFront
    add("CloudFront", f"Data transfer out {dto_gb:.0f} GB (1 TB free)",
        max(dto_gb - P["cf_free_gb"], 0) * P["cf_dto_india"], hidden=True)
    rules = 5 if a3 else 4
    add("AWS WAF", f"1 web ACL, {rules} rules, {total_cf_req/1e6:.1f} M requests",
        P["waf_acl"] + rules * P["waf_rule"] + total_cf_req * P["waf_req"])
    add("Route 53", "1 hosted zone (alias queries free)", P["route53_zone"])

    # --- API + compute
    add("API Gateway", f"HTTP API {w['api_requests']/1e6:.1f} M requests", w["api_requests"] * P["apigw_http"])
    worker_inv = w["uploads"] + w["emails"] + w["marking_msgs"] + 2000
    inv = w["api_requests"] + worker_inv
    gbs = w["api_requests"] * 0.060 * 0.5 + worker_inv * 0.3 * 0.25
    add("Lambda", f"{inv/1e6:.1f} M invocations, {gbs/1e3:.0f}k GB-s (1 M / 400k GB-s free)",
        max(inv - 1e6, 0) * P["lambda_req"] + max(gbs - 400_000, 0) * P["lambda_gbs_arm"])
    if a3 and exam:
        pc_gbs = 100 * 0.5 * w["exam_hours_peak"] * 3600
        add("Lambda", f"Provisioned concurrency 100 x 512 MB for {w['exam_hours_peak']} h", pc_gbs * P["lambda_pc_gbs_arm"])

    # --- Database
    if a3 and exam:
        add("RDS PostgreSQL", "db.t4g.large Multi-AZ (exam mode; RI covers the medium share)",
            P["rds_t4g_medium_maz_ri"] + (P["rds_t4g_large_maz"] - P["rds_t4g_medium_maz"]))
    elif a3:
        add("RDS PostgreSQL", "db.t4g.medium Multi-AZ, 1-yr Reserved (no upfront)", P["rds_t4g_medium_maz_ri"])
    else:
        add("RDS PostgreSQL", "db.t4g.medium Multi-AZ on-demand", P["rds_t4g_medium_maz"])
        if exam:
            add("RDS PostgreSQL", "CPU credit surplus (36 vCPU-h above baseline)", 36 * P["rds_cpu_credit"], hidden=True)
    add("RDS PostgreSQL", "50 GB gp3 storage x 2 AZ", 50 * P["rds_gp3_maz"])
    backup_gb = 20 if a3 else 47.5  # A2 also kept 35 daily AWS Backup copies on top of RDS PITR
    add("Backups", f"Snapshot storage beyond free allowance ({backup_gb} GB)", backup_gb * P["rds_snapshot"], hidden=True)
    add("RDS Proxy", "2 vCPU x 730 h", 2 * H * P["rds_proxy_vcpu"])

    # --- Network
    if a3:
        add("VPC endpoints", "SQS + Secrets Manager interface endpoints x 2 AZ", 2 * 2 * H * P["vpce_hour"])
        add("VPC endpoints", "Data processed 4 GB", 4 * P["vpce_gb"], hidden=True)
    else:
        add("NAT gateway", "2 NAT gateways (one per AZ)", 2 * H * P["nat_hour"])
        add("NAT gateway", "Data processed 5 GB (SQS, SES, Secrets, Cognito, X-Ray)", 5 * P["nat_gb"], hidden=True)
    add("Data transfer", "Cross-AZ Lambda <-> RDS Proxy (~50 GB)", 50 * P["inter_az_gb"] * (1.4 if exam else 1), hidden=True)
    if not a3:
        add("Data transfer", f"S3 -> internet, tutor downloads {w['upload_gb']:.0f} GB (100 GB free)",
            max(w["upload_gb"] - P["dto_free_gb"], 0) * P["dto_internet"], hidden=True)

    # --- Storage
    arch = P["s3_gda"] if a3 else P["s3_gfr"]
    add("S3", f"Uploads storage, year-1 average ({'Deep Archive' if a3 else 'Glacier Flexible'} after 180 d)", s3_year1_avg(arch))
    add("S3", f"{w['uploads']/1e3:.0f}k uploads + lifecycle transitions", w["uploads"] / 1000 * (P["s3_put_1k"] + 2 * P["s3_transition_1k"]))

    # --- Async + identity
    sqs_req = (4 if a3 else 3) * 650_000 + w["uploads"] * 3 + w["emails"] * 3 + w["marking_msgs"] * 3
    add("SQS", f"{sqs_req/1e6:.1f} M requests incl. empty long-polls (1 M free)", max(sqs_req - 1e6, 0) * P["sqs_req"], hidden=True)
    add("SES", f"{w['emails']/1e3:.0f}k emails", w["emails"] * P["ses_email"])
    add("Cognito", f"{USERS} MAU (10,000 free, Essentials)", max(USERS - 10_000, 0) * P["cognito_mau"])

    # --- Security
    kms_req = 100_000 if a3 else 300_000
    add("KMS", "1 customer-managed key", P["kms_key"])
    add("KMS", f"{kms_req/1e3:.0f}k requests", kms_req * P["kms_req"], hidden=True)
    secret_calls = 2_000 if a3 else 60_000
    add("Secrets Manager", f"1 secret, {secret_calls/1e3:.0f}k calls", P["secret"] + secret_calls * P["secret_call"])

    # --- Observability
    if a3:
        std_gb = w["api_requests"] * 0.02 / 1e6 + 1.5          # WARN-level app logs only + workers
        ia_gb = w["api_requests"] * 0.25 / 1e6 + 1.0           # API access logs + flow logs in IA class
        add("CloudWatch Logs", f"Ingest {std_gb:.1f} GB Standard + {ia_gb:.1f} GB Infrequent Access (5 GB free)",
            max(std_gb - 5, 0) * P["cwl_ingest"] + ia_gb * P["cwl_ingest_ia"], hidden=True)
        add("CloudWatch Logs", "Storage, 30-day retention", (std_gb + ia_gb) * 0.15 * P["cwl_store"], hidden=True)
        add("CloudWatch", "20 alarms, 1 dashboard (10 alarms, 3 dashboards free)", 10 * P["cw_alarm"])
    else:
        gb = w["api_requests"] * 0.65 / 1e6 + 2.5               # START/END/REPORT + access logs + workers + flow
        add("CloudWatch Logs", f"Ingest {gb:.1f} GB Standard (5 GB free)", max(gb - 5, 0) * P["cwl_ingest"], hidden=True)
        add("CloudWatch Logs", "Storage, 90-day retention", gb * 3 * 0.15 * P["cwl_store"], hidden=True)
        add("CloudWatch", "16 alarms, 1 dashboard", 6 * P["cw_alarm"])
        traces = 1.3e6 + 0.05 * (w["api_requests"] - 1.3e6)
        add("X-Ray", f"{traces/1e6:.1f} M traces (100k free)", max(traces - 1e5, 0) * P["xray_trace"])
    add("CloudTrail", "Management trail (first copy free) + S3", 0.10)
    return L

def total(L):
    return round(sum(x[2] for x in L), 2)

# ---------------------------------------------------------------- report
def table(design):
    n, e = lines("normal", design), lines("exam", design)
    services = []
    for s, *_ in n + e:
        if s not in services:
            services.append(s)
    rows = []
    for s in services:
        cn = sum(x[2] for x in n if x[0] == s)
        ce = sum(x[2] for x in e if x[0] == s)
        rows.append((s, cn, ce, 10 * cn + 2 * ce))
    return rows, total(n), total(e)

def md():
    out = [f"<!-- generated by docs/cost-model.py on {DATE_CHECKED} -->"]
    for design, title in (("a3", "Revised (Assignment 3) design"), ("a2", "Assignment 2 design priced in Singapore (baseline)")):
        rows, tn, te = table(design)
        annual = 10 * tn + 2 * te
        out.append(f"\n#### {title}\n")
        out.append("| Service | Normal month (USD) | Exam month (USD) | Year (10 normal + 2 exam) |")
        out.append("|---|---:|---:|---:|")
        for s, cn, ce, ca in sorted(rows, key=lambda r: -r[3]):
            out.append(f"| {s} | {cn:,.2f} | {ce:,.2f} | {ca:,.2f} |")
        out.append(f"| **Total** | **{tn:,.2f}** | **{te:,.2f}** | **{annual:,.2f}** |")
        out.append(f"\nAverage per month: **${annual/12:,.2f}**. Cost per student per year: **${annual/STUDENTS:,.2f}** "
                   f"(per student per month ${annual/12/STUDENTS:.3f}).\n")
    for design in ("a3",):
        for profile in ("normal", "exam"):
            out.append(f"\n#### Line items – {design.upper()} {profile} month\n")
            out.append("| Service | Item | USD | Hidden cost |")
            out.append("|---|---|---:|:---:|")
            for s, item, c, hid in lines(profile, design):
                out.append(f"| {s} | {item} | {c:,.2f} | {'yes' if hid else ''} |")
            out.append(f"| **Total** | | **{total(lines(profile, design)):,.2f}** | |")
    out.append("\n#### S3 uploads storage over 5 years (month-end cost)\n")
    out.append("| Month | Standard GB | IA GB | Archive GB | Glacier Flexible (A2) | Deep Archive (A3) |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for m in (1, 6, 12, 24, 36, 48, 60):
        c2, (s, i, a) = s3_storage(m, P["s3_gfr"])
        c3, _ = s3_storage(m, P["s3_gda"])
        out.append(f"| {m} | {s:,.0f} | {i:,.0f} | {a:,.0f} | {c2:,.2f} | {c3:,.2f} |")
    out.append("\n#### Unit prices used (Singapore, checked " + DATE_CHECKED + ")\n")
    out.append("| Key | Price (USD) | Unit | Source | Status |")
    out.append("|---|---:|---|---|---|")
    for k, (v, unit, src, st) in PRICES.items():
        out.append(f"| `{k}` | {v:.10g} | {unit} | {src} | {st} |")
    return "\n".join(out)

# ---------------------------------------------------------------- region comparison
MUMBAI_OVERRIDES = {
    # bytebase.com/dbcost (updated 2026-07-20): db.t4g.medium Mumbai $61 on-demand / $45 1-yr RI per instance
    "rds_t4g_medium_maz": 122.0,
    "rds_t4g_medium_maz_ri": 90.0,
    "rds_t4g_large_maz": 244.0,   # scaled by the medium ratio 61/74 - verify
    "apigw_http": 1.00 / 1e6,     # API Gateway page lists Mumbai with US pricing - verify for HTTP APIs
    "dto_internet": 0.1093,       # verify
}

def region_totals(overrides):
    saved = dict(P)
    P.update(overrides)
    try:
        n, e = total(lines("normal", "a3")), total(lines("exam", "a3"))
    finally:
        P.clear(); P.update(saved)
    return n, e, 10 * n + 2 * e

if __name__ == "__main__":
    if "--regions" in sys.argv:
        for name, ov in (("Singapore ap-southeast-1", {}), ("Mumbai ap-south-1", MUMBAI_OVERRIDES)):
            n, e, a = region_totals(ov)
            print(f"| {name} | {n:,.2f} | {e:,.2f} | {a:,.2f} | {a/12:,.2f} |")
        sys.exit()
    if "--csv" in sys.argv:
        with open("evidence/cost-model.csv", "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["design", "profile", "service", "item", "usd", "hidden"])
            for d in ("a2", "a3"):
                for p in ("normal", "exam"):
                    for s, item, c, hid in lines(p, d):
                        wr.writerow([d, p, s, item, c, hid])
        print("wrote evidence/cost-model.csv")
    else:
        print(md())
