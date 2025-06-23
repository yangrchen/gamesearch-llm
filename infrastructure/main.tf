terraform {
  backend "s3" {
    bucket       = "gamesearch-terraform-state"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project = "gamesearch"
    }
  }
}

module "etl" {
  source = "./etl"

  aws_region          = var.aws_region
  s3_data_bucket_name = var.s3_data_bucket_name
  igdb_client_id      = var.igdb_client_id
  igdb_client_secret  = var.igdb_client_secret

  mongodbatlas_connection_uri_base = module.mongodb.mongodbatlas_connection_uri_base
  mongodbatlas_database            = var.mongodbatlas_database
  mongodbatlas_dbuser_user         = var.mongodbatlas_dbuser_user
  mongodbatlas_dbuser_password     = var.mongodbatlas_dbuser_password
  voyageai_api_key                 = var.voyageai_api_key
}

module "app" {
  source = "./app"

  aws_region                       = var.aws_region
  mongodbatlas_connection_uri_base = module.mongodb.mongodbatlas_connection_uri_base
  mongodbatlas_dbuser_user         = var.mongodbatlas_dbuser_user
  mongodbatlas_dbuser_password     = var.mongodbatlas_dbuser_password
  voyageai_api_key                 = var.voyageai_api_key
  anthropic_api_key                = var.anthropic_api_key
  gamesearch_secret_key            = var.gamesearch_secret_key
}

module "mongodb" {
  source = "./mongodb"

  mongodbatlas_public_key      = var.mongodbatlas_public_key
  mongodbatlas_private_key     = var.mongodbatlas_private_key
  mongodbatlas_org_id          = var.mongodbatlas_org_id
  mongodbatlas_database        = var.mongodbatlas_database
  mongodbatlas_dbuser_user     = var.mongodbatlas_dbuser_user
  mongodbatlas_dbuser_password = var.mongodbatlas_dbuser_password
}
