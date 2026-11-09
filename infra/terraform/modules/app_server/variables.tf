variable "name" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "documents_bucket_arn" {
  type = string
}

variable "ssm_prefix" {
  description = "アプリが読み取れる SSM パラメータのパス（例: /agent-rag/stg）"
  type        = string
}

variable "deploy_script_url" {
  description = "EC2 が定期的に取得して実行するデプロイスクリプトの URL"
  type        = string
}

variable "cpu_credits" {
  description = "T 系インスタンスの CPU クレジット（standard / unlimited）"
  type        = string
  default     = "standard"
}

variable "root_volume_gb" {
  type    = number
  default = 20
}
