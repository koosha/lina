output "bucket_name" {
  description = "Name of the S3 bucket holding OpenTofu state for all downstream modules."
  value       = aws_s3_bucket.tofu_state.id
}

output "table_name" {
  description = "Name of the DynamoDB table used for OpenTofu state locking."
  value       = aws_dynamodb_table.tofu_locks.id
}
