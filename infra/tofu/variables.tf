variable "aws_region" {
  description = "AWS region for the sandbox stack."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS profile name (must exist in ~/.aws/credentials)."
  type        = string
  default     = "lina-sandbox"
}

variable "operator_ip" {
  description = <<EOT
CIDR block (e.g. 73.123.45.6/32) used to allowlist Redshift Serverless and
OpenSearch public endpoints. When null, the module computes the current
public IP via the http data source — fine for one-off use, but operators
should set TF_VAR_operator_ip explicitly so a roaming connection doesn't
silently lose access between applies.
EOT
  type        = string
  default     = null
}

variable "openai_api_key" {
  description = <<EOT
OpenAI API key. Pass via TF_VAR_openai_api_key — never commit. The IaC
writes the value into Secrets Manager (lina/sandbox/openai-api-key) on
apply; the Lambda execution role is the only consumer.
EOT
  type        = string
  sensitive   = true
}

variable "redshift_admin_username" {
  description = "Admin username for the Redshift Serverless namespace."
  type        = string
  default     = "lina_admin"
}

variable "image_tag" {
  description = "ECR image tag the Lambda container points at on first apply."
  type        = string
  default     = "v1.1.0"
}
