# ---------------------------------------------------------------------------
# Chat Lambda (container image) + execution role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${local.name_prefix}-chat-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_secrets" {
  statement {
    sid     = "ReadAppSecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.openai_api_key.arn,
      aws_secretsmanager_secret.api_key.arn,
      aws_redshiftserverless_namespace.this.admin_password_secret_arn,
    ]
  }
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name   = "${local.name_prefix}-chat-secrets"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_secrets.json
}

data "aws_iam_policy_document" "lambda_opensearch" {
  statement {
    sid     = "OpenSearchHttp"
    effect  = "Allow"
    actions = ["es:ESHttpGet", "es:ESHttpPost", "es:ESHttpPut", "es:ESHttpDelete", "es:ESHttpHead"]
    resources = [
      aws_opensearch_domain.this.arn,
      "${aws_opensearch_domain.this.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_opensearch" {
  name   = "${local.name_prefix}-chat-opensearch"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_opensearch.json
}

# ---------------------------------------------------------------------------
# Lambda security group + Redshift ingress
# ---------------------------------------------------------------------------

resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-lambda-sg"
  description = "LINA sandbox: chat Lambda egress (no ingress)"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "Egress: anywhere"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-lambda-sg"
  }
}

# SANDBOX-ONLY: open Redshift to 0.0.0.0/0 on port 5439 so the chat Lambda
# (which runs outside any VPC and thus picks up an unpredictable AWS-owned
# outbound IP) can reach the workgroup. Authentication still requires the
# Redshift admin password from Secrets Manager. Tighten before any production
# deployment by either putting Lambda inside the VPC or restricting to known
# AWS public IP ranges (Boto3 fetches these from
# https://ip-ranges.amazonaws.com/ip-ranges.json).
resource "aws_security_group_rule" "redshift_from_lambda" {
  type              = "ingress"
  from_port         = 5439
  to_port           = 5439
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.redshift.id
  description       = "Sandbox: chat Lambda to Redshift (Lambda is outside VPC)"
}

# ---------------------------------------------------------------------------
# OpenSearch domain access policy (depends on the Lambda role we just created)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "opensearch" {
  statement {
    sid    = "AllowOperatorAndLambdaSigV4"
    effect = "Allow"

    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/koosha-cli",
        aws_iam_role.lambda_exec.arn,
      ]
    }

    actions = ["es:*"]

    resources = [
      aws_opensearch_domain.this.arn,
      "${aws_opensearch_domain.this.arn}/*",
    ]
  }

  statement {
    sid    = "AllowOperatorIp"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions = ["es:ESHttp*"]

    resources = [
      aws_opensearch_domain.this.arn,
      "${aws_opensearch_domain.this.arn}/*",
    ]

    condition {
      test     = "IpAddress"
      variable = "aws:SourceIp"
      values   = [local.operator_cidr]
    }
  }
}

resource "aws_opensearch_domain_policy" "this" {
  domain_name     = aws_opensearch_domain.this.domain_name
  access_policies = data.aws_iam_policy_document.opensearch.json
}

# ---------------------------------------------------------------------------
# Chat Lambda function (container image)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "lambda_chat" {
  name              = "/aws/lambda/${local.name_prefix}-chat"
  retention_in_days = 7
}

resource "aws_lambda_function" "chat" {
  function_name = "${local.name_prefix}-chat"
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.this.repository_url}:${var.image_tag}"

  memory_size   = 1024
  timeout       = 60
  architectures = ["x86_64"]

  environment {
    variables = {
      LINA_OPENSEARCH_HOST     = "https://${aws_opensearch_domain.this.endpoint}"
      LINA_OPENSEARCH_AUTH     = "aws_sigv4"
      LINA_AWS_REGION          = var.aws_region
      LINA_OPENAI_SECRET_ARN   = aws_secretsmanager_secret.openai_api_key.arn
      LINA_REDSHIFT_SECRET_ARN = aws_redshiftserverless_namespace.this.admin_password_secret_arn
      LINA_REDSHIFT_HOST       = aws_redshiftserverless_workgroup.this.endpoint[0].address
      LINA_SUPERVISOR_MODEL    = "gpt-5.2"
      LINA_LOG_FORMAT          = "json"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_chat,
    aws_iam_role_policy.lambda_secrets,
    aws_iam_role_policy.lambda_opensearch,
  ]

  lifecycle {
    # Operator updates the image via `aws lambda update-function-code`
    # outside of OpenTofu; subsequent applies must not revert it.
    ignore_changes = [image_uri]
  }
}

# ---------------------------------------------------------------------------
# Authorizer Lambda — small zip, validates x-api-key against Secrets Manager
# ---------------------------------------------------------------------------

data "archive_file" "authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_authorizer"
  output_path = "${path.module}/.terraform/lambda_authorizer.zip"
}

resource "aws_iam_role" "authorizer_exec" {
  name               = "${local.name_prefix}-authorizer-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "authorizer_basic" {
  role       = aws_iam_role.authorizer_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "authorizer_secret" {
  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.api_key.arn]
  }
}

resource "aws_iam_role_policy" "authorizer_secret" {
  name   = "${local.name_prefix}-authorizer-secret"
  role   = aws_iam_role.authorizer_exec.id
  policy = data.aws_iam_policy_document.authorizer_secret.json
}

resource "aws_cloudwatch_log_group" "lambda_authorizer" {
  name              = "/aws/lambda/${local.name_prefix}-authorizer"
  retention_in_days = 7
}

resource "aws_lambda_function" "authorizer" {
  function_name    = "${local.name_prefix}-authorizer"
  role             = aws_iam_role.authorizer_exec.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.authorizer.output_path
  source_code_hash = data.archive_file.authorizer.output_base64sha256

  memory_size = 128
  timeout     = 5

  environment {
    variables = {
      LINA_API_KEY_SECRET_ARN = aws_secretsmanager_secret.api_key.arn
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_authorizer,
    aws_iam_role_policy.authorizer_secret,
  ]
}
