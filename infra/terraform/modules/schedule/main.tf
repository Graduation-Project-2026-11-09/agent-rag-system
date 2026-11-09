# EventBridge Scheduler で EC2・RDS を決まった時刻に起動・停止する（費用削減）
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  region     = data.aws_region.current.region
  account_id = data.aws_caller_identity.current.account_id

  # RDS は起動に数分かかるので start_cron は利用開始の少し前にする
  schedules = {
    ec2-start = { cron = var.start_cron, target = "arn:aws:scheduler:::aws-sdk:ec2:startInstances", input = { InstanceIds = [var.instance_id] } }
    ec2-stop  = { cron = var.stop_cron, target = "arn:aws:scheduler:::aws-sdk:ec2:stopInstances", input = { InstanceIds = [var.instance_id] } }
    rds-start = { cron = var.start_cron, target = "arn:aws:scheduler:::aws-sdk:rds:startDBInstance", input = { DbInstanceIdentifier = var.db_instance_id } }
    rds-stop  = { cron = var.stop_cron, target = "arn:aws:scheduler:::aws-sdk:rds:stopDBInstance", input = { DbInstanceIdentifier = var.db_instance_id } }
  }
}

data "aws_iam_policy_document" "assume_scheduler" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.assume_scheduler.json
}

data "aws_iam_policy_document" "this" {
  statement {
    actions   = ["ec2:StartInstances", "ec2:StopInstances"]
    resources = ["arn:aws:ec2:${local.region}:${local.account_id}:instance/${var.instance_id}"]
  }
  statement {
    actions   = ["rds:StartDBInstance", "rds:StopDBInstance"]
    resources = ["arn:aws:rds:${local.region}:${local.account_id}:db:${var.db_instance_id}"]
  }
}

resource "aws_iam_role_policy" "this" {
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

resource "aws_scheduler_schedule" "this" {
  for_each = local.schedules

  name                         = "${var.name}-${each.key}"
  schedule_expression          = each.value.cron
  schedule_expression_timezone = var.timezone
  state                        = var.enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = each.value.target
    role_arn = aws_iam_role.this.arn
    input    = jsonencode(each.value.input)

    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}
