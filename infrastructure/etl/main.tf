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

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "gamesearch_ecs_task_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task_role" {
  name = "gamesearch_ecs_task_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
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
resource "aws_iam_policy" "ecs_s3_policy" {
  name        = "gamesearch_ecs_s3_policy"
  description = "Policy to allow Gamesearch ECS task to access S3"

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

resource "aws_iam_role_policy_attachment" "ecs_s3" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.ecs_s3_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_s3_bucket" "gamesearch_data_bucket" {
  bucket = var.s3_data_bucket_name
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "ecs_task_sg" {
  name        = "gamesearch-ecs-task-sg"
  description = "Security group for Gamesearch ECS Fargate task"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "gamesearch-ecs-task-sg"
  }
}

resource "aws_ecs_cluster" "gamesearch_cluster" {
  name = "gamesearch-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "ecs_log_group" {
  name              = "/ecs/gamesearch-transform"
  retention_in_days = 7
}

resource "aws_ecs_task_definition" "transform_task" {
  family                   = "gamesearch-transform"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "2048"  # 2 vCPU
  memory                   = "10240" # 10 GB RAM
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "gamesearch-transform"
      image = "${aws_ecr_repository.gamesearch_lambda_repo.repository_url}:transform-latest"

      essential = true

      environment = [
        {
          name  = "S3_BUCKET"
          value = aws_s3_bucket.gamesearch_data_bucket.id
        },
        {
          name  = "MONGODB_BASE_URI"
          value = var.mongodbatlas_connection_uri_base
        },
        {
          name  = "MONGODB_USER"
          value = var.mongodbatlas_dbuser_user
        },
        {
          name  = "MONGODB_PASSWORD"
          value = var.mongodbatlas_dbuser_password
        },
        {
          name  = "MONGODB_DATABASE"
          value = var.mongodbatlas_database
        },
        {
          name  = "MONGODB_COLLECTION"
          value = "games"
        },
        {
          name  = "VOYAGEAI_API_KEY"
          value = var.voyageai_api_key
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_log_group.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
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

resource "aws_iam_role" "eventbridge_ecs_role" {
  name = "gamesearch_eventbridge_ecs_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "events.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_iam_policy" "eventbridge_ecs_policy" {
  name        = "gamesearch_eventbridge_ecs_policy"
  description = "Policy to allow EventBridge to run ECS tasks"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ecs:RunTask"
        ],
        Resource = [
          aws_ecs_task_definition.transform_task.arn
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "iam:PassRole"
        ],
        Resource = [
          aws_iam_role.ecs_task_execution_role.arn,
          aws_iam_role.ecs_task_role.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "eventbridge_ecs" {
  role       = aws_iam_role.eventbridge_ecs_role.name
  policy_arn = aws_iam_policy.eventbridge_ecs_policy.arn
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

resource "aws_cloudwatch_event_target" "transform_ecs_target" {
  rule      = aws_cloudwatch_event_rule.extract_completed.name
  target_id = "TransformECSTask"
  arn       = aws_ecs_cluster.gamesearch_cluster.arn
  role_arn  = aws_iam_role.eventbridge_ecs_role.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.transform_task.arn
    launch_type         = "FARGATE"
    platform_version    = "LATEST"

    network_configuration {
      subnets          = data.aws_subnets.default.ids
      security_groups  = [aws_security_group.ecs_task_sg.id]
      assign_public_ip = true
    }
  }
}
