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