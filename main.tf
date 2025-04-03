provider "aws" {
  region = var.aws_region
}

resource "aws_iam_role" "lambda_exec_role" {
  name = "gamesearch_lambda_exec_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "lambda_s3_policy" {
  name        = "gamesearch_lambda_s3_policy"
  description = "Policy to allow Gamesearch lambda to access S3"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      Effect = "Allow",
      Resource = [
        "${aws_s3_bucket.game_data_bucket.arn}",
        "${aws_s3_bucket.game_data_bucket.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_s3_policy.arn
}

resource "aws_s3_bucket" "game_data_bucket" {
  bucket = var.s3_bucket_name
}

resource "null_resource" "extract_lambda_build" {
  triggers = {
    source_code = filesha256("${path.module}/lambdas/gamesearch-extract/main.go")
    go_mod      = filesha256("${path.module}/lambdas/gamesearch-extract/go.mod")
  }

  provisioner "local-exec" {
    command = <<EOT
            cd ${path.module}/lambdas/gamesearch-extract && \
            GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -tags lambda.norpc -o bootstrap main.go 
        EOT
  }
}

data "archive_file" "extract_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambdas/gamesearch-extract/bootstrap"
  output_path = "${path.module}/lambdas/gamesearch-extract/lambda.zip"
  depends_on  = [null_resource.extract_lambda_build]
}


resource "aws_lambda_function" "gamesearch_extract" {
  function_name = "gamesearch_extract"
  filename      = data.archive_file.extract_lambda_zip.output_path
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "bootstrap"
  runtime       = "provided.al2023"
  architectures = ["arm64"]
  timeout       = 300
  memory_size   = 2048

  source_code_hash = data.archive_file.extract_lambda_zip.output_base64sha256

  environment {
    variables = {
      CLIENT_ID     = var.igdb_client_id
      CLIENT_SECRET = var.igdb_client_secret
      S3_BUCKET     = aws_s3_bucket.game_data_bucket.id
    }
  }

}