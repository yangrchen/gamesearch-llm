module "lambdas" {
  source = "./infrastructure/lambdas"

  aws_region                    = var.aws_region
  s3_data_bucket_name           = var.s3_data_bucket_name
  s3_lambda_package_bucket_name = var.s3_lambda_package_bucket_name
  igdb_client_id                = var.igdb_client_id
  igdb_client_secret            = var.igdb_client_secret
}

module "mongodb" {
  source = "./infrastructure/mongodb"

  mongodbatlas_public_key  = var.mongodbatlas_public_key
  mongodbatlas_private_key = var.mongodbatlas_private_key
}