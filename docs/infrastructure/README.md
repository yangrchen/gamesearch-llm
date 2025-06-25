# Infrastructure Documentation

## Overview

The infrastructure is managed using Terraform and deployed on AWS.

## Prerequisites

- Terraform == 1.12.1
- AWS CLI
- MongoDB Atlas account

## Project Structure

```
infrastructure/
├── main.tf                  # Root project infrastructure
├── variables.tf             # Root project variables
├── outputs.tf               # Root project outputs
├── app/                     # Main application module
│   ├── main.tf              # Core resources for backend
│   ├── variables.tf         # Input variables
│   └── outputs.tf           # Output values
├── mongodb/                 # MongoDB Atlas module
│   ├── main.tf              # Core resources
│   ├── variables.tf         # Input variables
│   └── outputs.tf           # Output values
│── etl/                     # ETL module
│   ├── main.tf              # Core resources
│   └── variables.tf         # Input variables
```

## Resources Created

### AWS Resources

- VPC with public/private subnets
- ECS cluster, services, and tasks
- Application Load Balancer
- CloudFront distribution
- Route53 hosted zone
- S3 buckets
- ECR repository

### MongoDB Atlas

- Flex cluster
- Database user
- IP access list

## Deployment

```bash
# Initialize Terraform
terraform init

# Plan changes
terraform plan

# Apply changes
terraform apply
```

## Variables

Key variables that need to be set:

- `aws_region`: AWS region for deployment
- `s3_data_bucket_name`: S3 bucket to store raw game data
- `igdb_client_id`: IGDB API client ID
- `igdb_client_secret`: IGDB API client secret
- `mongodbatlas_public_key`: MongoDB public key
- `mongodbatlas_private_key`: MongoDB private key
- `mongodbatlas_org_id`: MongoDB organization ID
- `mongodbatlas_database`: Gamesearch database name
- `mongodbatlas_dbuser_user`: MongoDB database user username
- `mongodbatlas_dbuser_password`: MongoDB database user password
- `voyageai_api_key`: Voyage AI API key
- `anthropic_api_key`: Anthropic API key
- `gamesearch_secret_key`: Gamesearch backend secret key
