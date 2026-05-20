terraform {
  required_version = ">= 1.11"

  backend "s3" {
    bucket         = "lina-tofu-state-417811547857"
    key            = "sandbox/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "lina-tofu-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "LINA"
      Environment = "sandbox"
      ManagedBy   = "opentofu"
      Owner       = "koosha"
    }
  }
}

# Auto-detect the current public IP when var.operator_ip is null. Operators
# should set TF_VAR_operator_ip explicitly for stable allowlisting; the
# wrapper script (scripts/sandbox.sh) does this via a multi-service
# fallback chain. `count` makes this data source skip the API call entirely
# when var.operator_ip is provided — a single ipify outage would otherwise
# block every apply/destroy (hit in practice on 2026-05-20).
data "http" "myip" {
  count = var.operator_ip == null ? 1 : 0
  url   = "https://api.ipify.org"
}

locals {
  operator_cidr = var.operator_ip != null ? var.operator_ip : "${chomp(data.http.myip[0].response_body)}/32"
  name_prefix   = "lina-sandbox"
}

data "aws_caller_identity" "current" {}
