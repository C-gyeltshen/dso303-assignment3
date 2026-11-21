variable "project" {
  description = "Name prefix for all resources"
  type        = string
  default     = "exam-platform"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "region" {
  type    = string
  default = "ap-southeast-1" # A3: Asia Pacific (Singapore), as required by the brief
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "exam_mode" {
  description = "Exam-month settings (load-test finding): larger DB class and provisioned concurrency on the API. Flip in terraform.tfvars a week before exams; the pipeline applies it."
  type        = bool
  default     = false
}

variable "db_instance_class" {
  description = "Normal-month DB class (covered by a 1-year Reserved Instance)"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_instance_class_exam" {
  description = "Exam-month DB class"
  type        = string
  default     = "db.t4g.large"
}

variable "api_provisioned_concurrency" {
  description = "Provisioned concurrency on the API alias while exam_mode = true"
  type        = number
  default     = 100
}

variable "campus_cidrs" {
  description = "University NAT/public IP ranges exempt from the WAF per-IP rate limit (failure test 4 fix)"
  type        = list(string)
  default     = []
}

variable "api_log_level" {
  description = "Application log level for the API Lambda (WARN in production to cut CloudWatch Logs cost)"
  type        = string
  default     = "WARN"
}

variable "db_multi_az" {
  type    = bool
  default = true
}

variable "deletion_protection" {
  description = "Protect the database from deletion. Set false for a demo you will tear down."
  type        = bool
  default     = false
}

variable "alarm_email" {
  description = "Email that receives CloudWatch alarms"
  type        = string
}

variable "ses_sender_email" {
  description = "Verified SES sender address (e.g. exams-noreply@uni.edu). In the SES sandbox recipients must be verified too."
  type        = string
}

variable "ses_verify_emails" {
  description = "Extra addresses to verify in the SES sandbox (tutor/student test accounts)"
  type        = list(string)
  default     = []
}

variable "domain_name" {
  description = "Optional custom domain (e.g. exams.example.edu) with a Route 53 hosted zone. Empty = use the CloudFront domain."
  type        = string
  default     = ""
}

variable "hosted_zone_name" {
  description = "Route 53 hosted zone that contains domain_name (e.g. example.edu)"
  type        = string
  default     = ""
}

variable "waf_rate_limit" {
  description = "Requests per 5 minutes per IP before WAF blocks"
  type        = number
  default     = 10000
}

variable "enable_cloudtrail" {
  description = "Create a dedicated CloudTrail trail (disable if your account/organisation already has one)"
  type        = bool
  default     = true
}
