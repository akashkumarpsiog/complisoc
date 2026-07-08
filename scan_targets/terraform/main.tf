resource "aws_s3_bucket" "public_bucket" {
  bucket = "my-public-bucket"
}

resource "aws_s3_bucket_public_access_block" "bad" {
  bucket = aws_s3_bucket.public_bucket.id

  block_public_acls   = false
  block_public_policy = false
  ignore_public_acls  = false
  restrict_public_buckets = false
}

resource "aws_iam_policy" "over_permissive" {
  name = "over-permissive-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "*"
        Resource = "*"
      }
    ]
  })
}
