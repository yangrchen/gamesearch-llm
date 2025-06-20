variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}
variable "s3_data_bucket_name" {
  description = "Name of the S3 bucket to store raw game data"
  type        = string
}

variable "igdb_client_id" {
  description = "IGDB API Client ID"
  type        = string
  sensitive   = true
}

variable "igdb_client_secret" {
  description = "IGDB API Client Secret"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_public_key" {
  description = "MongoDB Public Key"
  type        = string
}

variable "mongodbatlas_private_key" {
  description = "MongoDB Private Key"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_org_id" {
  description = "Organization ID"
  type        = string
  sensitive   = true
}

variable "mongodbatlas_database" {
  description = "Gamesearch Database Name"
  type        = string
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

variable "gamesearch_secret_key" {
  description = "Secret key for Gamesearch backend"
  type        = string
  sensitive   = true
}
