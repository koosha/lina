# OpenSearch managed domain — single t3.small node is enough for the seed data.
resource "aws_opensearch_domain" "this" {
  domain_name    = local.name_prefix
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type            = "t3.small.search"
    instance_count           = 1
    dedicated_master_enabled = false
    zone_awareness_enabled   = false
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 10
    volume_type = "gp3"
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_security_options {
    enabled                        = false
    internal_user_database_enabled = false
  }
}

# The companion access policy "aws_opensearch_domain_policy" lives in
# lambda.tf so it can include the Lambda execution role principal without a
# forward declaration.
