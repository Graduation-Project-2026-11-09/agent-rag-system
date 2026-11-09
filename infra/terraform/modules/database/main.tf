resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

# pgvector は RDS for PostgreSQL 17 に同梱。接続後に CREATE EXTENSION vector で有効化する
resource "aws_db_instance" "this" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  storage_type      = "gp3"
  allocated_storage = var.allocated_storage_gb
  storage_encrypted = true

  db_name  = var.db_name
  username = var.username
  password = random_password.master.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  multi_az               = false

  # 毎日バックアップ（時刻は UTC）
  backup_retention_period    = var.backup_retention_days
  backup_window              = var.backup_window
  maintenance_window         = var.maintenance_window
  auto_minor_version_upgrade = true
  apply_immediately          = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-final"
}

# アプリは SSM からこの値を読んで接続する
resource "aws_ssm_parameter" "database_url" {
  name  = "${var.ssm_prefix}/DATABASE_URL"
  type  = "SecureString"
  value = "postgresql+psycopg://${var.username}:${random_password.master.result}@${aws_db_instance.this.address}:5432/${var.db_name}"
}
