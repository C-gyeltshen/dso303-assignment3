# Operational switches – committed, so every change is reviewed and deployed by a push to main.
# Exam weeks: set exam_mode = true about a week before the first exam (DB resize causes a ~1 min
# Multi-AZ failover, so apply it outside exam hours), and back to false afterwards.
exam_mode         = false
db_instance_class = "db.t4g.medium"
campus_cidrs      = [] # e.g. ["203.0.113.0/24"] – exam-hall NAT addresses from university IT
waf_rate_limit    = 10000
