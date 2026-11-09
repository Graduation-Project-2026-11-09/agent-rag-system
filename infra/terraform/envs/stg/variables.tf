variable "project" {
  type    = string
  default = "agent-rag"
}

variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "github_repo" {
  description = "デプロイスクリプトとイメージを取得する GitHub リポジトリ（owner/name）"
  type        = string
  default     = "Graduation-Project-2026-11-09/agent-rag-system"
}

# stg は最小構成。本番（計画書: t3.medium / db.t4g.small）より小さくする
variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "enable_schedule" {
  description = "平日 9:00〜22:00 だけ起動する。発表前などで常時稼働させたいときは false"
  type        = bool
  default     = true
}
