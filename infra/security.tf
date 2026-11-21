# Customer-managed KMS key used for data at rest (S3 uploads, RDS, secrets, logs, SNS).
resource "aws_kms_key" "main" {
  description             = "${local.name} data-at-rest key"
  enable_key_rotation     = true
  deletion_window_in_days = 7

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountAdmin"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudWatchLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${var.region}.amazonaws.com" }
        Action    = ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"]
        Resource  = "*"
        Condition = {
          ArnLike = { "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:*" }
        }
      },
      {
        Sid       = "CloudWatchAlarmsToSNS"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource  = "*"
      },
      {
        Sid       = "RdsEventsToSNS"
        Effect    = "Allow"
        Principal = { Service = "events.rds.amazonaws.com" }
        Action    = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource  = "*"
      },
      {
        Sid       = "CloudFrontOACReadUploads"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = ["kms:Decrypt"]
        Resource  = "*"
        Condition = { StringLike = { "aws:SourceArn" = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/*" } }
      },
      {
        Sid       = "S3EventsToSQS"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action    = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource  = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "main" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.main.key_id
}

# ---------------- CloudFront signed URLs for tutor downloads (A3, optimisation O5) ----------------
# Downloads are served by CloudFront (1 TB/month free) instead of S3 direct ($0.12/GB).
resource "tls_private_key" "cf" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_cloudfront_public_key" "files" {
  name        = "${local.name}-files"
  encoded_key = tls_private_key.cf.public_key_pem
}

resource "aws_cloudfront_key_group" "files" {
  name  = "${local.name}-files"
  items = [aws_cloudfront_public_key.files.id]
}

resource "aws_secretsmanager_secret" "cf_key" {
  name                    = "${local.name}/cloudfront-signing-key"
  kms_key_id              = aws_kms_key.main.arn
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cf_key" {
  secret_id     = aws_secretsmanager_secret.cf_key.id
  secret_string = tls_private_key.cf.private_key_pem
}
