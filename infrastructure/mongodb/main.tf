terraform {
    required_providers {
        mongodbatlas = {
            source = "mongodb/mongodbatlas",
            version = "~> 1.31.0"
        }
    }
}
provider "mongodbatlas" {
  public_key  = var.mongodbatlas_public_key
  private_key = var.mongodbatlas_private_key
}

