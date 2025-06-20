# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# ECR Repository for backend
resource "aws_ecr_repository" "backend_repo" {
  name                 = "gamesearch-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name    = "gamesearch-backend-repo"
    Project = "gamesearch"
  }
}

resource "aws_ecr_lifecycle_policy" "backend_repo_policy" {
  repository = aws_ecr_repository.backend_repo.name

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

# VPC with optimized CIDR for small applications
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/20" # 4,096 IPs - optimized for small apps
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name    = "gamesearch-vpc"
    Project = "gamesearch"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name    = "gamesearch-igw"
    Project = "gamesearch"
  }
}

# Public subnets (using /24 for optimal sizing)
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index}.0/24" # 10.0.0.0/24, 10.0.1.0/24
  availability_zone = data.aws_availability_zones.available.names[count.index]

  map_public_ip_on_launch = true

  tags = {
    Name    = "gamesearch-public-subnet-${count.index + 1}"
    Project = "gamesearch"
  }
}

# Private subnets for future use (databases, caches)
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 8}.0/24" # 10.0.8.0/24, 10.0.9.0/24
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name    = "gamesearch-private-subnet-${count.index + 1}"
    Project = "gamesearch"
  }
}

# Route table for public subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name    = "gamesearch-public-rt"
    Project = "gamesearch"
  }
}

# Associate public subnets with route table
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Security group for Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "gamesearch-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "gamesearch-alb-sg"
    Project = "gamesearch"
  }
}

# Security group for Fargate tasks
resource "aws_security_group" "fargate" {
  name        = "gamesearch-fargate-sg"
  description = "Security group for Fargate tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTP from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "gamesearch-fargate-sg"
    Project = "gamesearch"
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "gamesearch-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false

  tags = {
    Name    = "gamesearch-alb"
    Project = "gamesearch"
  }
}

# Target group for backend service
resource "aws_lb_target_group" "backend" {
  name        = "gamesearch-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name    = "gamesearch-backend-tg"
    Project = "gamesearch"
  }
}

# Route53 Hosted Zone
resource "aws_route53_zone" "main" {
  name = var.domain_name

  tags = {
    Name    = "gamesearch-app-zone"
    Project = "gamesearch"
  }
}

# ACM Certificate for SSL/TLS
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name    = "gamesearch-app-cert"
    Project = "gamesearch"
  }
}

# Route53 records for ACM certificate validation
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

# ACM certificate validation
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]

  timeouts {
    create = "5m"
  }
}

# Route53 A record for api.gamesearch.app pointing to ALB
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "${var.api_subdomain}.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# S3 bucket for frontend static website
resource "aws_s3_bucket" "frontend" {
  bucket = var.domain_name

  tags = {
    Name    = "gamesearch-frontend"
    Project = "gamesearch"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "gamesearch-frontend-oac"
  description                       = "Origin Access Control for Gamesearch frontend S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html" # For SPA routing
  }
}

# S3 bucket policy - only allow CloudFront access
resource "aws_s3_bucket_policy" "frontend" {
  bucket     = aws_s3_bucket.frontend.id
  depends_on = [aws_s3_bucket_public_access_block.frontend]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
          }
        }
      }
    ]
  })
}

# CloudFront distribution for frontend
resource "aws_cloudfront_distribution" "frontend" {
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-${var.domain_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  aliases = [var.domain_name, "www.${var.domain_name}"]

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${var.domain_name}"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # AWS Managed CachingDisabled policy
  }

  # SPA routing - handle all routes with index.html
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  price_class = "PriceClass_100" # Use only North America and Europe edge locations

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name    = "gamesearch-frontend-distribution"
    Project = "gamesearch"
  }

  depends_on = [aws_acm_certificate_validation.main]
}

# Route53 record for root domain (points to CloudFront)
resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# Route53 record for www subdomain (points to CloudFront)
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# HTTP Listener (redirects to HTTPS)
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS Listener for ALB
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "gamesearch-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name    = "gamesearch-cluster"
    Project = "gamesearch"
  }
}

# IAM role for ECS task execution
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "gamesearch-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "gamesearch-ecs-execution-role"
    Project = "gamesearch"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# CloudWatch log group for backend
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/gamesearch-backend"
  retention_in_days = 7

  tags = {
    Name    = "gamesearch-backend-logs"
    Project = "gamesearch"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "gamesearch-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name  = "gamesearch-backend"
      image = "${aws_ecr_repository.backend_repo.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
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
          name  = "VOYAGEAI_API_KEY"
          value = var.voyageai_api_key
        },
        {
          name  = "ANTHROPIC_API_KEY"
          value = var.anthropic_api_key
        },
        {
          name  = "GAMESEARCH_SECRET_KEY"
          value = var.gamesearch_secret_key
        },
        {
          name  = "ALLOWED_ORIGINS"
          value = "https://${var.domain_name},https://www.${var.domain_name},https://${var.api_subdomain}.${var.domain_name}"
        },
        {
          name  = "ENVIRONMENT"
          value = "production"
        },
        {
          name  = "PORT"
          value = "8000"
        },
        {
          name  = "HOST"
          value = "0.0.0.0"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }

      essential = true
    }
  ])

  tags = {
    Name    = "gamesearch-backend-task"
    Project = "gamesearch"
  }
}

# ECS Service
resource "aws_ecs_service" "backend" {
  name            = "gamesearch-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.fargate.id]
    subnets          = aws_subnet.public[*].id
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "gamesearch-backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https, aws_lb_listener.http_redirect]

  tags = {
    Name    = "gamesearch-backend-service"
    Project = "gamesearch"
  }
}
