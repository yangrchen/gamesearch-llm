variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "mongodbatlas_connection_uri_base" {
  description = "MongoDB base connection string for app"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_dbuser_user" {
  description = "Username for MongoDB database user"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_dbuser_password" {
  description = "Password for MongoDB database user"
  type        = string
  sensitive   = true
}

variable "voyageai_api_key" {
  description = "API key for Voyage AI embedding service"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "API key for Anthropic LLMs"
  type        = string
  sensitive   = true
}

variable "allowed_origins" {
  description = "Allowed origins for the backend"
  type        = string
  sensitive   = true
}
