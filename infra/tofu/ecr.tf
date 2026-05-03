resource "aws_ecr_repository" "this" {
  name                 = "${local.name_prefix}-chat"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}
