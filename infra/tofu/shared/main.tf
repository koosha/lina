terraform {
  required_version = ">= 1.11"

  backend "s3" {
    bucket         = "lina-tofu-state-417811547857"
    key            = "shared/terraform.tfstate"
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
      Environment = "shared"
      ManagedBy   = "opentofu"
      Owner       = "koosha"
    }
  }
}

variable "aws_region" {
  description = "AWS region for shared resources."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS profile name (must exist in ~/.aws/credentials)."
  type        = string
  default     = "lina-sandbox"
}

variable "aws_account_id" {
  description = "AWS account ID owning the role and CI backends."
  type        = string
  default     = "417811547857"
}

variable "aws_region_for_resources" {
  description = "Region the CI backends live in (used in resource ARNs)."
  type        = string
  default     = "us-east-1"
}

variable "github_repo" {
  description = "GitHub owner/repo allowed to assume the CI runner role via OIDC."
  type        = string
  default     = "koosha/lina"
}
