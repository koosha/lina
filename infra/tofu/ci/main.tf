terraform {
  required_version = ">= 1.11"

  backend "s3" {
    bucket         = "lina-tofu-state-417811547857"
    key            = "ci/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "lina-tofu-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "LINA"
      Environment = "ci"
      ManagedBy   = "opentofu"
      Owner       = "koosha"
    }
  }
}

variable "aws_region" {
  description = "AWS region for the CI backends."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS profile name (must exist in ~/.aws/credentials)."
  type        = string
  default     = "lina-sandbox"
}

variable "redshift_admin_username" {
  description = "Admin username for the Redshift Serverless namespace."
  type        = string
  default     = "lina_admin"
}

# Pull the CI runner role ARN from the shared module's remote state so the
# OpenSearch domain access policy can grant it on apply.
data "terraform_remote_state" "shared" {
  backend = "s3"

  config = {
    bucket  = "lina-tofu-state-417811547857"
    key     = "shared/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
    profile = var.aws_profile
  }
}

locals {
  name_prefix = "lina-ci"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}
