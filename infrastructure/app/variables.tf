# infrastructure/fargate/variables.tf

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "mongodbatlas_connection_uri_base" {
  description = "MongoDB Atlas connection URI base"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_dbuser_user" {
  description = "MongoDB Atlas database user username"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_dbuser_password" {
  description = "MongoDB Atlas database user password"
  type        = string
  sensitive   = true
}

variable "voyageai_api_key" {
  description = "VoyageAI API key"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
}

variable "gamesearch_secret_key" {
  description = "Secret key for Gamesearch backend"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "The domain name for the application"
  type        = string
  default     = "gamesearch.app"
}

variable "api_subdomain" {
  description = "The API subdomain"
  type        = string
  default     = "api"
}
