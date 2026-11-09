variable "name" {
  type = string
}

variable "instance_id" {
  type = string
}

variable "db_instance_id" {
  type = string
}

variable "enabled" {
  description = "false にすると常時稼働（スケジュールを無効化）"
  type        = bool
  default     = true
}

variable "timezone" {
  type    = string
  default = "Asia/Tokyo"
}

variable "start_cron" {
  type    = string
  default = "cron(45 8 ? * MON-FRI *)"
}

variable "stop_cron" {
  type    = string
  default = "cron(0 15 ? * MON-FRI *)"
}
