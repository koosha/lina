output "redshift_endpoint" {
  description = "Redshift Serverless workgroup hostname (port 5439)."
  value       = aws_redshiftserverless_workgroup.this.endpoint[0].address
}

output "redshift_dsn_template" {
  description = "Postgres DSN template; substitute the admin password from Secrets Manager."
  value       = "postgresql://${var.redshift_admin_username}:<password>@${aws_redshiftserverless_workgroup.this.endpoint[0].address}:5439/dev"
}

output "redshift_admin_secret_arn" {
  description = "ARN of the Redshift admin password secret (managed by AWS)."
  value       = aws_redshiftserverless_namespace.this.admin_password_secret_arn
}

output "opensearch_host" {
  description = "OpenSearch domain HTTPS endpoint."
  value       = "https://${aws_opensearch_domain.this.endpoint}"
}

output "lambda_function_name" {
  description = "Name of the chat Lambda function."
  value       = aws_lambda_function.chat.function_name
}

output "api_endpoint" {
  description = "Public HTTPS endpoint for POST /ask."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "ecr_repository_url" {
  description = "ECR repository URL for the chat Lambda image."
  value       = aws_ecr_repository.this.repository_url
}

output "api_key_secret_arn" {
  description = "ARN of the api-key secret (retrieve value via aws secretsmanager get-secret-value)."
  value       = aws_secretsmanager_secret.api_key.arn
}

output "openai_api_key_secret_arn" {
  description = "ARN of the OpenAI key secret consumed by the chat Lambda."
  value       = aws_secretsmanager_secret.openai_api_key.arn
}

output "next_steps_runbook" {
  description = "Pointer to the post-apply operator runbook."
  value       = "See deploy/runbook.md for image build, migrate, seed, and smoke-test commands."
}

output "redshift_runtime_secret_arn" {
  description = "ARN of the lina_app_readonly Redshift runtime secret. Bootstrapped via `lina-redshift bootstrap-runtime-user --put-secret-arn <this>`."
  value       = aws_secretsmanager_secret.redshift_runtime.arn
}

output "alarms_topic_arn" {
  description = "SNS topic that receives CloudWatch alarm notifications. Subscribe an operator email out-of-band."
  value       = aws_sns_topic.alarms.arn
}
