# Default VPC + subnets — sandbox uses public network + IP allowlists.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security group for the Redshift Serverless workgroup. Allows port 5439 from
# the operator IP and from the Lambda function's security group.
resource "aws_security_group" "redshift" {
  name        = "${local.name_prefix}-redshift-sg"
  description = "LINA sandbox: Redshift Serverless inbound rules"
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

resource "aws_security_group_rule" "redshift_from_operator" {
  type              = "ingress"
  from_port         = 5439
  to_port           = 5439
  protocol          = "tcp"
  cidr_blocks       = [local.operator_cidr]
  security_group_id = aws_security_group.redshift.id
  description       = "Operator laptop access for psql/lina-redshift CLI"
}

# The companion ingress rule "redshift_from_lambda" lives in lambda.tf so it
# can reference aws_security_group.lambda without a forward declaration.
