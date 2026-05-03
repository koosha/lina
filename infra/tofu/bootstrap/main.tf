terraform {
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

# Bootstrap state stays local (no chicken-and-egg with the bucket it creates).
# All other modules use the S3 backend referencing resources defined here.

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
  description = "AWS region for the state bucket and lock table."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS profile name (must exist in ~/.aws/credentials)."
  type        = string
  default     = "lina-sandbox"
}

variable "state_bucket_name" {
  description = "Name of the S3 bucket that holds OpenTofu state for every other module."
  type        = string
  default     = "lina-tofu-state-417811547857"
}

variable "lock_table_name" {
  description = "Name of the DynamoDB table used for OpenTofu state locking."
  type        = string
  default     = "lina-tofu-locks"
}

resource "aws_s3_bucket" "tofu_state" {
  bucket = var.state_bucket_name

  tags = {
    Name = var.state_bucket_name
  }
}

resource "aws_s3_bucket_versioning" "tofu_state" {
  bucket = aws_s3_bucket.tofu_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tofu_state" {
  bucket = aws_s3_bucket.tofu_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tofu_state" {
  bucket = aws_s3_bucket.tofu_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tofu_locks" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name = var.lock_table_name
  }
}
