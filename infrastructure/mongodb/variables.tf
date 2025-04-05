variable "mongodbatlas_public_key" {
  description = "MongoDB Public Key"
  type        = string
}

variable "mongodbatlas_private_key" {
  description = "MongoDB Private Key"
  type        = string
  sensitive   = true
}