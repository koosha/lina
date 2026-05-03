# lina-ci-runner — assumed by GitHub Actions runs in koosha/lina via OIDC.
# Trust policy restricts to repo:koosha/lina:* (any branch / PR / tag).

resource "aws_iam_role" "ci_runner" {
  name = "lina-ci-runner"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })

  tags = {
    Name = "lina-ci-runner"
  }
}

# Redshift Serverless permissions. GetWorkgroup + GetCredentials require
# Resource: "*" because the AWS APIs do not currently support resource-scoping
# on those operations. Acceptable in this single-environment sandbox account.
resource "aws_iam_role_policy" "ci_runner_redshift" {
  name = "lina-ci-runner-redshift"
  role = aws_iam_role.ci_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "redshift-serverless:GetWorkgroup",
        "redshift-serverless:GetCredentials",
      ]
      Resource = "*"
    }]
  })
}

# Secrets Manager — read on specific secrets, plus ListSecrets which the
# ci-redshift-dsn.sh helper uses to discover the auto-generated Redshift
# admin secret name. ListSecrets is account-wide metadata and does NOT
# support resource scoping, so it's split into its own "*"-resource statement.
resource "aws_iam_role_policy" "ci_runner_secrets" {
  name = "lina-ci-runner-secrets"
  role = aws_iam_role.ci_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadScopedSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region_for_resources}:${var.aws_account_id}:secret:redshift!lina-ci-ns-*",
          "arn:aws:secretsmanager:${var.aws_region_for_resources}:${var.aws_account_id}:secret:lina/sandbox/openai-api-key-*",
        ]
      },
      {
        Sid      = "ListSecretsForDiscovery"
        Effect   = "Allow"
        Action   = ["secretsmanager:ListSecrets"]
        Resource = "*"
      },
    ]
  })
}

# OpenSearch — HTTP queries against the lina-ci domain (es:ESHttp*) plus
# the metadata describe call used by the ci-opensearch-host.sh helper to
# discover the domain endpoint at workflow start.
resource "aws_iam_role_policy" "ci_runner_opensearch" {
  name = "lina-ci-runner-opensearch"
  role = aws_iam_role.ci_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "QueryDomain"
        Effect = "Allow"
        Action = ["es:ESHttp*"]
        Resource = [
          "arn:aws:es:${var.aws_region_for_resources}:${var.aws_account_id}:domain/lina-ci/*",
        ]
      },
      {
        Sid    = "DescribeDomainForDiscovery"
        Effect = "Allow"
        Action = [
          "es:DescribeDomain",
          "es:DescribeElasticsearchDomain",
        ]
        Resource = [
          "arn:aws:es:${var.aws_region_for_resources}:${var.aws_account_id}:domain/lina-ci",
        ]
      },
    ]
  })
}

# CloudWatch Logs for CI run output. Scope to /aws/ci/lina/* group prefix.
resource "aws_iam_role_policy" "ci_runner_logs" {
  name = "lina-ci-runner-logs"
  role = aws_iam_role.ci_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = [
        "arn:aws:logs:${var.aws_region_for_resources}:${var.aws_account_id}:log-group:/aws/ci/lina/*",
      ]
    }]
  })
}

# Cost Explorer — used by the daily cost watcher workflow. CE does not support
# resource-level scoping; "*" is required by the API.
resource "aws_iam_role_policy" "ci_runner_costexplorer" {
  name = "lina-ci-runner-costexplorer"
  role = aws_iam_role.ci_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ce:GetCostAndUsage"]
      Resource = "*"
    }]
  })
}
