output "public_ip" {
  description = "stg の URL は http://<この IP>"
  value       = module.app_server.public_ip
}

output "instance_id" {
  value = module.app_server.instance_id
}

output "db_instance_id" {
  value = module.database.instance_id
}

output "ssm_prefix" {
  value = local.ssm_prefix
}
