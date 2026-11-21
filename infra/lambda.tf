# Backend code is built by `npm ci --omit=dev` in ../backend (CI does this) and zipped here.
data "archive_file" "backend" {
  type        = "zip"
  source_dir  = "${path.module}/../backend"
  output_path = "${path.module}/.build/backend.zip"
}

locals {
  proxy_resource_id = split(":", aws_db_proxy.main.arn)[6] # prx-xxxxxxxx

  common_env = {
    DB_HOST          = aws_db_proxy.main.endpoint
    DB_NAME          = aws_db_instance.main.db_name
    DB_USER          = aws_db_instance.main.username
    UPLOAD_BUCKET    = aws_s3_bucket.uploads.bucket
    MARKING_QUEUE    = aws_sqs_queue.q["marking"].url
    NOTIFY_QUEUE     = aws_sqs_queue.q["notify"].url
    EMAIL_QUEUE      = aws_sqs_queue.q["email"].url
    SES_SENDER       = var.ses_sender_email
    USER_POOL_ID     = aws_cognito_user_pool.main.id
    SITE_URL         = local.site_url
    CF_KEY_PAIR_ID   = aws_cloudfront_public_key.files.id
    CF_KEY_SECRET    = aws_secretsmanager_secret.cf_key.arn
    NODE_OPTIONS     = "--enable-source-maps"
  }

  # in_vpc = false: functions that never touch the database run outside the VPC,
  # so they need no NAT gateway or extra endpoints to reach SES / Cognito.
  functions = {
    api              = { handler = "src/api.handler", timeout = 10, memory = 512, in_vpc = true, log_level = var.api_log_level }
    marker           = { handler = "src/marker.handler", timeout = 10, memory = 256, in_vpc = true, log_level = "INFO" }
    upload-processor = { handler = "src/uploadProcessor.handler", timeout = 30, memory = 256, in_vpc = true, log_level = "INFO" }
    notifier         = { handler = "src/notifier.handler", timeout = 30, memory = 256, in_vpc = true, log_level = "INFO" }
    migrate          = { handler = "src/migrate.handler", timeout = 120, memory = 256, in_vpc = true, log_level = "INFO" }
    mailer           = { handler = "src/mailer.handler", timeout = 15, memory = 256, in_vpc = false, log_level = "INFO" }
    admin            = { handler = "src/admin.handler", timeout = 10, memory = 256, in_vpc = false, log_level = "INFO" }
  }
}

# ---------------- IAM: one least-privilege role per function ----------------
resource "aws_iam_role" "fn" {
  for_each = local.functions
  name     = "${local.name}-${each.key}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "basic" {
  for_each   = local.functions
  role       = aws_iam_role.fn[each.key].name
  policy_arn = each.value.in_vpc ? "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole" : "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

locals {
  db_connect_stmt = [{
    Effect   = "Allow"
    Action   = ["rds-db:connect"]
    Resource = "arn:aws:rds-db:${var.region}:${data.aws_caller_identity.current.account_id}:dbuser:${local.proxy_resource_id}/${aws_db_instance.main.username}"
  }]
  send_email_stmt = [{ Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.q["email"].arn }]
  consume = { for k in ["marking", "uploads", "notify", "email"] : k => [{
    Effect   = "Allow"
    Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    Resource = aws_sqs_queue.q[k].arn
  }] }

  fn_policies = {
    api = concat(local.db_connect_stmt, [
      { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.uploads.arn}/submissions/*" },
      { Effect = "Allow", Action = ["kms:GenerateDataKey", "kms:Decrypt"], Resource = aws_kms_key.main.arn },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [aws_sqs_queue.q["marking"].arn, aws_sqs_queue.q["notify"].arn] },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.cf_key.arn }
    ])
    marker           = concat(local.db_connect_stmt, local.consume["marking"])
    upload-processor = concat(local.db_connect_stmt, local.send_email_stmt, local.consume["uploads"], [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObjectTagging"], Resource = "${aws_s3_bucket.uploads.arn}/submissions/*" },
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = aws_kms_key.main.arn }
    ])
    notifier = concat(local.db_connect_stmt, local.send_email_stmt, local.consume["notify"], [
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.q["notify"].arn }
    ])
    migrate = local.db_connect_stmt
    mailer = concat(local.consume["email"], [{
      Effect = "Allow", Action = ["ses:SendEmail", "ses:SendRawEmail"], Resource = "*",
      Condition = { StringEquals = { "ses:FromAddress" = var.ses_sender_email } }
    }])
    admin = [{
      Effect   = "Allow"
      Action   = ["cognito-idp:AdminCreateUser", "cognito-idp:AdminAddUserToGroup"]
      Resource = aws_cognito_user_pool.main.arn
    }]
  }
}

resource "aws_iam_role_policy" "fn" {
  for_each = local.functions
  role     = aws_iam_role.fn[each.key].id
  policy   = jsonencode({ Version = "2012-10-17", Statement = local.fn_policies[each.key] })
}

# ---------------- Functions ----------------
resource "aws_cloudwatch_log_group" "fn" {
  for_each          = local.functions
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = 30 # A3: was 90; audit records live in the DB, S3 and CloudTrail, not in app logs
  kms_key_id        = aws_kms_key.main.arn
}

resource "aws_lambda_function" "fn" {
  for_each         = local.functions
  function_name    = "${local.name}-${each.key}"
  role             = aws_iam_role.fn[each.key].arn
  runtime          = "nodejs22.x"
  architectures    = ["arm64"]
  handler          = each.value.handler
  filename         = data.archive_file.backend.output_path
  source_code_hash = data.archive_file.backend.output_base64sha256
  timeout          = each.value.timeout
  memory_size      = each.value.memory
  publish          = each.key == "api" # versions are needed for the provisioned-concurrency alias

  dynamic "vpc_config" {
    for_each = each.value.in_vpc ? [1] : []
    content {
      subnet_ids         = aws_subnet.app[*].id # both AZs
      security_group_ids = [aws_security_group.lambda.id]
    }
  }

  environment { variables = local.common_env }

  # A3: JSON logs with levels; platform START/END/REPORT lines are dropped (system level WARN).
  logging_config {
    log_format            = "JSON"
    log_group             = aws_cloudwatch_log_group.fn[each.key].name
    application_log_level = each.value.log_level
    system_log_level      = "WARN"
  }

  depends_on = [aws_iam_role_policy_attachment.basic]
}

# Alias the API Gateway invokes; carries provisioned concurrency in exam mode.
resource "aws_lambda_alias" "api_live" {
  name             = "live"
  function_name    = aws_lambda_function.fn["api"].function_name
  function_version = aws_lambda_function.fn["api"].version
}

resource "aws_lambda_provisioned_concurrency_config" "api" {
  count                             = var.exam_mode ? 1 : 0
  function_name                     = aws_lambda_alias.api_live.function_name
  qualifier                         = aws_lambda_alias.api_live.name
  provisioned_concurrent_executions = var.api_provisioned_concurrency
}

# ---------------- SQS triggers ----------------
locals {
  triggers = {
    marker           = { queue = "marking", batch = 10, max_concurrency = 20 }
    upload-processor = { queue = "uploads", batch = 5, max_concurrency = 10 }
    notifier         = { queue = "notify", batch = 10, max_concurrency = 5 }
    mailer           = { queue = "email", batch = 10, max_concurrency = 5 }
  }
}

resource "aws_lambda_event_source_mapping" "sqs" {
  for_each                = local.triggers
  event_source_arn        = aws_sqs_queue.q[each.value.queue].arn
  function_name           = aws_lambda_function.fn[each.key].arn
  batch_size              = each.value.batch
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config {
    maximum_concurrency = each.value.max_concurrency # caps DB load and keeps the mailer under the SES send rate (bottleneck #3)
  }
}
