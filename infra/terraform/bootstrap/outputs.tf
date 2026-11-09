output "tfstate_bucket" {
  description = "envs/*/backend.hcl の bucket に設定する"
  value       = aws_s3_bucket.tfstate.bucket
}
