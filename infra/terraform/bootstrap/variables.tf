variable "project" {
  type    = string
  default = "agent-rag"
}

variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "monthly_budget_usd" {
  type    = number
  default = 30
}

variable "budget_email" {
  description = "予算アラートの通知先。公開リポジトリなので terraform.tfvars（Git 管理外）に書く"
  type        = string
}
