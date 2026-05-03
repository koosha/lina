# OpenAI key — operator passes via TF_VAR_openai_api_key on first apply.
resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "lina/sandbox/openai-api-key"
  description             = "OpenAI API key consumed by the chat Lambda"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = jsonencode({ api_key = var.openai_api_key })
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
