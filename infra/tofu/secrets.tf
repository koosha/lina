# OpenAI key — secret container only. The value is set out-of-band via
# `aws secretsmanager put-secret-value` (see deploy/runbook.md) so the
# plaintext key never lands in Tofu state. A `sensitive` variable is
# still read by Tofu's CLI in plaintext at apply time and persists in
# state, which defeats the point.
resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "lina/sandbox/openai-api-key"
  description             = "OpenAI API key consumed by the chat Lambda"
  recovery_window_in_days = 7
}

# Shared API key checked by the API Gateway authorizer Lambda.
resource "random_password" "api_key" {
  length  = 40
  special = false
  upper   = true
  lower   = true
  numeric = true
}

resource "aws_secretsmanager_secret" "api_key" {
  name                    = "lina/sandbox/api-key"
  description             = "Shared x-api-key validated by the API Gateway authorizer Lambda"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = jsonencode({ api_key = random_password.api_key.result })
}

# Read-only Redshift runtime user used by the chat Lambda. The secret
# value is set out-of-band via `lina-redshift bootstrap-runtime-user
# --put-secret-arn <arn>` after `tofu apply`. We never write the value
# from Tofu so it doesn't end up in state.
resource "aws_secretsmanager_secret" "redshift_runtime" {
  name                    = "lina/sandbox/redshift-runtime"
  description             = "Read-only Redshift user (lina_app_readonly) consumed by the chat Lambda"
  recovery_window_in_days = 7
}
