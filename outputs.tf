# App Infrastructure Outputs
output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = module.app.ecr_repository_url
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.app.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.app.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.app.private_subnet_ids
}

output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = module.app.alb_dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the load balancer"
  value       = module.app.alb_zone_id
}

output "alb_arn" {
  description = "ARN of the load balancer"
  value       = module.app.alb_arn
}

output "route53_zone_id" {
  description = "Route53 zone ID for the domain"
  value       = module.app.route53_zone_id
}

output "route53_name_servers" {
  description = "Name servers for the Route53 zone - UPDATE THESE AT NAMECHEAP"
  value       = module.app.route53_name_servers
}

output "certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = module.app.certificate_arn
}

output "api_url" {
  description = "URL of the API"
  value       = module.app.api_url
}

output "root_url" {
  description = "URL of the root domain"
  value       = module.app.root_url
}

output "s3_frontend_bucket_name" {
  description = "Name of the S3 bucket for frontend"
  value       = module.app.s3_frontend_bucket_name
}

output "s3_frontend_bucket_arn" {
  description = "ARN of the S3 bucket for frontend"
  value       = module.app.s3_frontend_bucket_arn
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for frontend"
  value       = module.app.cloudfront_distribution_id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.app.cloudfront_domain_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.app.ecs_cluster_name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.app.ecs_service_name
}

# MongoDB Outputs
output "mongodbatlas_connection_uri_base" {
  description = "MongoDB Atlas connection URI (sensitive)"
  value       = module.mongodb.mongodbatlas_connection_uri_base
  sensitive   = true
}
