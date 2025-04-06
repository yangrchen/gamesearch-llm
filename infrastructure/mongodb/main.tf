terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas",
      version = "~> 1.31.0"
    }
  }
}
provider "mongodbatlas" {
  public_key  = var.mongodbatlas_public_key
  private_key = var.mongodbatlas_private_key
}

data "mongodbatlas_project" "gamesearch_project" {
  name = "Gamesearch API"
}

resource "mongodbatlas_advanced_cluster" "gamesearch_cluster" {
  project_id   = data.mongodbatlas_project.gamesearch_project.id
  name         = "gamesearch-cluster"
  cluster_type = "REPLICASET"

  replication_specs {
    region_configs {
      electable_specs {
        instance_size = "M0"
      }
      provider_name         = "TENANT"
      backing_provider_name = "AWS"
      region_name           = "US_EAST_1"
      priority              = 7
    }
  }
}

resource "mongodbatlas_database_user" "gamesearch_user" {
  username           = var.mongodbatlas_dbuser_user
  password           = var.mongodbatlas_dbuser_password
  project_id         = data.mongodbatlas_project.gamesearch_project.id
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = var.mongodbatlas_database
  }
}

resource "mongodbatlas_project_ip_access_list" "gamesearch_ip_list" {
  project_id = data.mongodbatlas_project.gamesearch_project.id
  cidr_block = "0.0.0.0/0"
  comment    = "Allow access from all for development"
}

output "mongodbatlas_connection_uri_base" {
  value     = mongodbatlas_advanced_cluster.gamesearch_cluster.connection_strings[0].standard_srv
  sensitive = true
}