# Redshift Serverless namespace + workgroup for CI integration tests.
# Auto-pause keeps idle bill ~$0; admin password lives in Secrets Manager.

resource "aws_redshiftserverless_namespace" "this" {
  namespace_name        = "${local.name_prefix}-ns"
  admin_username        = var.redshift_admin_username
  manage_admin_password = true
  db_name               = "dev"

  iam_roles = []

  log_exports = ["userlog", "connectionlog", "useractivitylog"]
}

resource "aws_redshiftserverless_workgroup" "this" {
  namespace_name      = aws_redshiftserverless_namespace.this.namespace_name
  workgroup_name      = "${local.name_prefix}-wg"
  base_capacity       = 8
  publicly_accessible = true

  security_group_ids = [aws_security_group.redshift.id]
  subnet_ids         = data.aws_subnets.default.ids

  config_parameter {
    parameter_key   = "max_query_execution_time"
    parameter_value = "60000"
  }
}

# Public ingress 5439 from anywhere — GitHub-hosted CI runners use a large
# rotating IP range and AWS does not publish a stable allowlist for them.
# Auth is enforced by the Redshift admin password (Secrets Manager-managed).
resource "aws_security_group" "redshift" {
  name        = "${local.name_prefix}-redshift-sg"
  description = "LINA CI: Redshift Serverless inbound rules"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "Egress: anywhere"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-redshift-sg"
  }
}

resource "aws_security_group_rule" "redshift_from_anywhere" {
  type              = "ingress"
  from_port         = 5439
  to_port           = 5439
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.redshift.id
  description       = "GH Actions runners use rotating IPs - admin password gates auth"
}
