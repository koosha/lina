output "ci_runner_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions runs via OIDC."
  value       = aws_iam_role.ci_runner.arn
}

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider."
  value       = aws_iam_openid_connect_provider.github.arn
}
