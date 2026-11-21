resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_db_parameter_group" "pg" {
  name   = "${local.name}-pg16"
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.exam_mode ? var.db_instance_class_exam : var.db_instance_class
  db_name        = "exams"
  username       = "exam_admin"

  # Master password generated, stored and rotated by Secrets Manager (encrypted with our CMK)
  manage_master_user_password   = true
  master_user_secret_kms_key_id = aws_kms_key.main.arn

  multi_az               = var.db_multi_az # synchronous standby in the second AZ
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  parameter_group_name   = aws_db_parameter_group.pg.name

  allocated_storage     = 20
  max_allocated_storage = 200
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.main.arn

  backup_retention_period    = 35 # point-in-time restore; logs shipped every 5 min => RPO <= 5 min
  backup_window              = "18:00-18:30"         # UTC = 23:30 Bhutan time
  maintenance_window         = "sun:19:00-sun:20:00" # outside exam hours
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.main.arn
  performance_insights_retention_period = 7
  enabled_cloudwatch_logs_exports       = ["postgresql"]

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${local.name}-final" : null
  apply_immediately         = true
}

# --- RDS Proxy: pools Lambda connections, speeds up failover ---
resource "aws_iam_role" "proxy" {
  name = "${local.name}-rds-proxy"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "rds.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "proxy" {
  role = aws_iam_role.proxy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_db_instance.main.master_user_secret[0].secret_arn },
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = aws_kms_key.main.arn }
    ]
  })
}

resource "aws_db_proxy" "main" {
  name                   = "${local.name}-proxy"
  engine_family          = "POSTGRESQL"
  role_arn               = aws_iam_role.proxy.arn
  vpc_subnet_ids         = aws_subnet.app[*].id
  vpc_security_group_ids = [aws_security_group.proxy.id]
  require_tls            = true
  idle_client_timeout    = 1800

  # A3: Lambdas authenticate to the proxy with short-lived IAM tokens (signed locally),
  # so they never call Secrets Manager at runtime. The proxy itself uses the secret.
  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "REQUIRED"
    secret_arn  = aws_db_instance.main.master_user_secret[0].secret_arn
  }
}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name
  connection_pool_config {
    max_connections_percent      = 75
    max_idle_connections_percent = 25
    connection_borrow_timeout    = 30
  }
}

resource "aws_db_proxy_target" "main" {
  db_proxy_name          = aws_db_proxy.main.name
  target_group_name      = aws_db_proxy_default_target_group.main.name
  db_instance_identifier = aws_db_instance.main.identifier
}

# --- AWS Backup: monthly copies kept 5 years (records-retention requirement) ---
resource "aws_backup_vault" "main" {
  name          = "${local.name}-vault"
  kms_key_arn   = aws_kms_key.main.arn
  force_destroy = !var.deletion_protection
}

resource "aws_backup_plan" "main" {
  name = "${local.name}-plan"

  # A3: the daily AWS Backup rule was removed - RDS automated backups already give 35-day PITR.
  rule {
    rule_name         = "monthly-5y"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 20 1 * ? *)"
    lifecycle {
      delete_after = 1825 # 5 years
    }
  }
}

resource "aws_iam_role" "backup" {
  name = "${local.name}-backup"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "backup.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_backup_selection" "db" {
  name         = "${local.name}-db"
  plan_id      = aws_backup_plan.main.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [aws_db_instance.main.arn]
}
