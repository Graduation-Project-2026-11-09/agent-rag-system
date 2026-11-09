variable "name" {
  type = string
}

variable "force_destroy" {
  description = "destroy 時に中身ごと削除する（stg のみ true）"
  type        = bool
  default     = false
}
