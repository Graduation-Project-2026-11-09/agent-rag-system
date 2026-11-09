locals {
  name       = "${var.project}-stg"
  ssm_prefix = "/${var.project}/stg"
}

module "network" {
  source = "../../modules/network"
  name   = local.name
}

module "storage" {
  source        = "../../modules/storage"
  name          = local.name
  force_destroy = true
}

module "database" {
  source              = "../../modules/database"
  name                = local.name
  subnet_ids          = module.network.private_subnet_ids
  security_group_id   = module.network.db_security_group_id
  ssm_prefix          = local.ssm_prefix
  instance_class      = var.db_instance_class
  deletion_protection = false
  skip_final_snapshot = true

  # 無料プランでは保持期間に上限があるため、stg は 1 日にする（ダミーデータのみ）
  backup_retention_days = 1

  # 停止中は自動バックアップが取られないため、起動している時間帯（JST 12:00 / 水曜 13:00）にする
  backup_window      = "03:00-03:30"
  maintenance_window = "wed:04:00-wed:04:30"
}

module "app_server" {
  source               = "../../modules/app_server"
  name                 = local.name
  instance_type        = var.instance_type
  subnet_id            = module.network.public_subnet_id
  security_group_id    = module.network.app_security_group_id
  documents_bucket_arn = module.storage.documents_bucket_arn
  ssm_prefix           = local.ssm_prefix
  deploy_script_url    = "https://raw.githubusercontent.com/${var.github_repo}/main/deploy/stg/deploy.sh"
}

# 平日 8:45 に起動、22:00 に停止（利用時間 9:00〜22:00）。祝日は考慮しない
module "schedule" {
  source         = "../../modules/schedule"
  name           = local.name
  instance_id    = module.app_server.instance_id
  db_instance_id = module.database.instance_id
  enabled        = var.enable_schedule
  stop_cron      = "cron(0 22 ? * MON-FRI *)"
}

# ---------------------------------------------------------------
# アプリの設定値（SSM Parameter Store）
# ---------------------------------------------------------------
resource "random_password" "secret_key" {
  length  = 64
  special = false
}

resource "aws_ssm_parameter" "secret_key" {
  name  = "${local.ssm_prefix}/SECRET_KEY"
  type  = "SecureString"
  value = random_password.secret_key.result
}

# 値はコードに書かない。apply 後に AWS コンソールか CLI で手動設定する
resource "aws_ssm_parameter" "openai_api_key" {
  name  = "${local.ssm_prefix}/OPENAI_API_KEY"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# stg の動作確認用ダミー利用者のパスワード（deploy.sh の flask seed-users が使う）
resource "random_password" "seed_user" {
  length  = 16
  special = false
}

resource "aws_ssm_parameter" "seed_user_password" {
  name  = "${local.ssm_prefix}/SEED_USER_PASSWORD"
  type  = "SecureString"
  value = random_password.seed_user.result
}

resource "aws_ssm_parameter" "documents_bucket" {
  name  = "${local.ssm_prefix}/DOCUMENTS_BUCKET"
  type  = "String"
  value = module.storage.documents_bucket_name
}

# ---------------------------------------------------------------
# HTTPS（ドメインを買わずに sslip.io を使う）
# 15-134-254-123.sslip.io のような名前は、その IP アドレスに解決される。
# Caddy がこの名前で Let's Encrypt の証明書を自動で取得し、HTTP は HTTPS にリダイレクトする
# ---------------------------------------------------------------
locals {
  site_domain = "${replace(module.app_server.public_ip, ".", "-")}.sslip.io"
}

resource "aws_ssm_parameter" "site_address" {
  name  = "${local.ssm_prefix}/SITE_ADDRESS"
  type  = "String"
  value = local.site_domain
}

# HTTPS で配信しているので、ログインの Cookie は HTTPS のときだけ送る
resource "aws_ssm_parameter" "session_cookie_secure" {
  name  = "${local.ssm_prefix}/SESSION_COOKIE_SECURE"
  type  = "String"
  value = "true"
}
