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

# NOTE: previously `variable "openai_api_key"`. Removed in Wave 6 of the
# remediation plan — the plaintext value would otherwise persist in Tofu
# state. The Secrets Manager *container* is still managed by Tofu (see
# secrets.tf), but the value is set out-of-band via the AWS CLI; see
# deploy/runbook.md for the put-secret-value step.

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

variable "cors_allowed_origins" {
  description = <<EOT
Origins permitted to call POST /ask from a browser. Defaults to "*" so the
sandbox UI can be served from any host (S3 bucket website, Vercel, local
preview). Tighten to the specific UI origin (e.g. ["https://lina.example.com"])
once a permanent host is chosen.
EOT
  type        = list(string)
  default     = ["*"]
}
