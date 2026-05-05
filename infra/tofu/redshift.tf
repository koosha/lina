# Redshift Serverless — namespace + workgroup. Auto-pause keeps idle bill ~$0.
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

  # AWS layers in defaults for `auto_mv`, `enable_user_activity_logging`,
  # `require_ssl`, `datestyle`, etc. that Tofu otherwise wants to delete
  # on every apply. These are AWS-managed defaults — letting them drift
  # freely keeps the workgroup stable across applies.
  lifecycle {
    ignore_changes = [config_parameter]
  }
}
