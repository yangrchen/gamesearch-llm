variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}
variable "s3_data_bucket_name" {
  description = "Name of the S3 bucket to store raw game data"
  type        = string
}

variable "s3_lambda_package_bucket_name" {
  description = "Name of the S3 bucket to store lambda packages"
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