module "lambdas" {
  source = "./infrastructure/lambdas"

  aws_region                    = var.aws_region
  s3_data_bucket_name           = var.s3_data_bucket_name
  s3_lambda_package_bucket_name = var.s3_lambda_package_bucket_name
  igdb_client_id                = var.igdb_client_id
  igdb_client_secret            = var.igdb_client_secret

  mongodbatlas_connection_uri_base = module.mongodb.mongodbatlas_connection_uri_base
  mongodbatlas_database            = var.mongodbatlas_database
  mongodbatlas_dbuser_user         = var.mongodbatlas_dbuser_user
  mongodbatlas_dbuser_password     = var.mongodbatlas_dbuser_password
}

module "mongodb" {
  source = "./infrastructure/mongodb"

  mongodbatlas_public_key      = var.mongodbatlas_public_key
  mongodbatlas_private_key     = var.mongodbatlas_private_key
  mongodbatlas_org_id          = var.mongodbatlas_org_id
  mongodbatlas_database        = var.mongodbatlas_database
  mongodbatlas_dbuser_user     = var.mongodbatlas_dbuser_user
  mongodbatlas_dbuser_password = var.mongodbatlas_dbuser_password
}