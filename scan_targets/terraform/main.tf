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

resource "aws_security_group" "open_ssh" {
  name        = "open-ssh-sg"
  description = "Security group with SSH open to the world"
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
