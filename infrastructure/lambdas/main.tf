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
        "${aws_s3_bucket.gamesearch_data_bucket.arn}",
        "${aws_s3_bucket.gamesearch_data_bucket.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_s3_policy.arn
}

resource "aws_s3_bucket" "gamesearch_data_bucket" {
  bucket = var.s3_data_bucket_name
}

resource "aws_s3_bucket" "gamesearch_lambda_package_bucket" {
  bucket = var.s3_lambda_package_bucket_name
}

resource "null_resource" "extract_lambda_build" {
  triggers = {
    source_code = filesha256("${path.root}/lambdas/gamesearch-extract/main.go")
    go_mod      = filesha256("${path.root}/lambdas/gamesearch-extract/go.mod")
  }

  provisioner "local-exec" {
    command = <<EOT
            cd ${path.root}/lambdas/gamesearch-extract && \
            GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -tags lambda.norpc -o bootstrap main.go 
        EOT
  }
}

data "archive_file" "extract_lambda_zip" {
  type        = "zip"
  source_file = "${path.root}/lambdas/gamesearch-extract/bootstrap"
  output_path = "${path.root}/lambdas/gamesearch-extract/lambda.zip"
  depends_on  = [null_resource.extract_lambda_build]
}


resource "aws_s3_object" "upload_extract_lambda_package" {
  bucket      = aws_s3_bucket.gamesearch_lambda_package_bucket.id
  key         = "extract/lambda.zip"
  source      = data.archive_file.extract_lambda_zip.output_path
  source_hash = data.archive_file.extract_lambda_zip.output_md5
  depends_on  = [data.archive_file.extract_lambda_zip]
}

resource "aws_lambda_function" "extract_lambda" {
  function_name = "gamesearch_extract"
  # filename      = data.archive_file.extract_lambda_zip.output_path
  role          = aws_iam_role.lambda_exec_role.arn
  s3_bucket     = aws_s3_bucket.gamesearch_lambda_package_bucket.id
  s3_key        = aws_s3_object.upload_extract_lambda_package.key
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
      S3_BUCKET     = aws_s3_bucket.gamesearch_data_bucket.id
    }
  }

  depends_on = [aws_s3_object.upload_extract_lambda_package]

}

resource "null_resource" "transform_lambda_dependencies" {
  triggers = {
    source_code  = filesha256("${path.root}/lambdas/gamesearch-transform/lambda_function.py")
    requirements = filesha256("${path.root}/lambdas/gamesearch-transform/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<EOT
      rm -r ${path.root}/lambdas/gamesearch-transform/package/; mkdir -p ${path.root}/lambdas/gamesearch-transform/package/ && \
      cp ${path.root}/lambdas/gamesearch-transform/lambda_function.py ${path.root}/lambdas/gamesearch-transform/package/ && \
      pip install -r ${path.root}/lambdas/gamesearch-transform/requirements.txt --target ${path.root}/lambdas/gamesearch-transform/package/ --no-cache
    EOT
  }
}

data "archive_file" "transform_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.root}/lambdas/gamesearch-transform/package/"
  output_path = "${path.root}/lambdas/gamesearch-transform/lambda.zip"
  depends_on  = [null_resource.transform_lambda_dependencies]
}

resource "aws_s3_object" "upload_transform_lambda_package" {
  bucket      = aws_s3_bucket.gamesearch_lambda_package_bucket.id
  key         = "transform/lambda.zip"
  source      = data.archive_file.transform_lambda_zip.output_path
  source_hash = data.archive_file.transform_lambda_zip.output_md5
  depends_on  = [data.archive_file.transform_lambda_zip]
}

resource "aws_lambda_function" "transform_lambda" {
  function_name    = "gamesearch_transform"
  role             = aws_iam_role.lambda_exec_role.arn
  s3_bucket        = aws_s3_bucket.gamesearch_lambda_package_bucket.id
  s3_key           = aws_s3_object.upload_transform_lambda_package.key
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 420
  memory_size      = 2048
  source_code_hash = data.archive_file.transform_lambda_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET          = aws_s3_bucket.gamesearch_data_bucket.id
      MONGODB_BASE_URI   = var.mongodbatlas_connection_uri_base
      MONGODB_USER       = var.mongodbatlas_dbuser_user
      MONGODB_PASSWORD   = var.mongodbatlas_dbuser_password
      MONGODB_DATABASE   = var.mongodbatlas_database
      MONGODB_COLLECTION = "games"
    }
  }

  depends_on = [aws_s3_object.upload_transform_lambda_package]
}

resource "aws_cloudwatch_event_rule" "extract_completed" {
  name        = "gamesearch_extract_completed"
  description = "Capture when the gamesearch extract lambda finishes"

  event_pattern = jsonencode({
    source      = ["aws.lambda"],
    detail-type = ["Lambda Function Invocation Result - Success"],
    detail = {
      "function-name" = [aws_lambda_function.extract_lambda.function_name]
    }
  })
}

resource "aws_cloudwatch_event_target" "transform_lambda_target" {
  rule      = aws_cloudwatch_event_rule.extract_completed.name
  target_id = "TransformLambda"
  arn       = aws_lambda_function.transform_lambda.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.transform_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.extract_completed.arn
}