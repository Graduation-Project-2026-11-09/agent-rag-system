variable "name" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_group_id" {
  type = string
}

variable "ssm_prefix" {
  type = string
}

variable "engine_version" {
  type    = string
  default = "17"
}

variable "instance_class" {
  type = string
}

variable "allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "app"
}

variable "username" {
  type    = string
  default = "app"
}

variable "backup_retention_days" {
  description = "自動バックアップの保持日数（計画書の要件は 7 日）"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "UTC。既定は JST 2:00-3:00"
  type        = string
  default     = "17:00-18:00"
}

variable "maintenance_window" {
  description = "UTC。backup_window と重ならないようにする。既定は JST 月曜 3:30-4:30"
  type        = string
  default     = "sun:18:30-sun:19:30"
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "skip_final_snapshot" {
  type    = bool
  default = false
}
