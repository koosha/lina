output "redshift_endpoint" {
  description = "Redshift Serverless workgroup hostname (port 5439)."
  value       = aws_redshiftserverless_workgroup.this.endpoint[0].address
}

output "redshift_admin_secret_arn" {
  description = "ARN of the Redshift admin password secret (managed by AWS)."
  value       = aws_redshiftserverless_namespace.this.admin_password_secret_arn
}

output "opensearch_host" {
  description = "OpenSearch domain HTTPS endpoint."
  value       = "https://${aws_opensearch_domain.this.endpoint}"
}

output "redshift_workgroup_name" {
  description = "Workgroup name (used by the helper scripts)."
  value       = aws_redshiftserverless_workgroup.this.workgroup_name
}

output "opensearch_domain_name" {
  description = "OpenSearch domain name (used by the helper scripts)."
  value       = aws_opensearch_domain.this.domain_name
}
