provider "aws" {
  region = var.aws_region
}

resource "aws_ecr_repository" "gamesearch_lambda_repo" {
  name                 = "gamesearch-lambdas"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "gamesearch_lambda_repo_policy" {
  repository = aws_ecr_repository.gamesearch_lambda_repo.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1,
        description  = "Keep last 10 images",
        selection = {
          tagStatus   = "any",
          countType   = "imageCountMoreThan",
          countNumber = 10
        },
        action = {
          type = "expire"
        }
      }
    ]
  })
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

resource "aws_lambda_function" "extract_lambda" {
  function_name = "gamesearch_extract"
  role          = aws_iam_role.lambda_exec_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.gamesearch_lambda_repo.repository_url}:extract-latest"
  architectures = ["arm64"]
  timeout       = 500
  memory_size   = 2048

  environment {
    variables = {
      CLIENT_ID     = var.igdb_client_id
      CLIENT_SECRET = var.igdb_client_secret
      S3_BUCKET     = aws_s3_bucket.gamesearch_data_bucket.id
    }
  }
}

resource "aws_lambda_function" "transform_lambda" {
  function_name = "gamesearch_transform"
  role          = aws_iam_role.lambda_exec_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.gamesearch_lambda_repo.repository_url}:transform-latest"
  timeout       = 420
  memory_size   = 2048

  environment {
    variables = {
      S3_BUCKET          = aws_s3_bucket.gamesearch_data_bucket.id
      MONGODB_BASE_URI   = var.mongodbatlas_connection_uri_base
      MONGODB_USER       = var.mongodbatlas_dbuser_user
      MONGODB_PASSWORD   = var.mongodbatlas_dbuser_password
      MONGODB_DATABASE   = var.mongodbatlas_database
      MONGODB_COLLECTION = "games"
      VOYAGEAI_API_KEY   = var.voyageai_api_key
    }
  }
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
