#!/bin/bash

set -e

# Variable configuration
REGION="${AWS_REGION:-us-east-1}"
ECR_REPO_NAME="gamesearch-lambdas"
EXTRACT_TAG="${GAMESEARCH_EXTRACT_TAG:-latest}"
TRANSFORM_TAG="${GAMESEARCH_TRANSFORM_TAG:-latest}"

# Get AWS creds
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"

# Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Build and push extract lambda
echo "Building extract lambda..."
cd etl/gamesearch-extract
docker build --platform linux/amd64 --provenance false -t ${ECR_URI}:extract-${EXTRACT_TAG} .
echo "Pushing extract lambda..."
docker push ${ECR_URI}:extract-${EXTRACT_TAG}
cd ../..

# Build and push transform container
echo "Building transform container for ECS Fargate..."
cd etl/gamesearch-transform
docker build --platform linux/amd64 --provenance false -t ${ECR_URI}:transform-${TRANSFORM_TAG} .
echo "Pushing transform container..."
docker push ${ECR_URI}:transform-${TRANSFORM_TAG}
cd ../..

echo "Build and push completed successfully!"
echo "Extract image: ${ECR_URI}:extract-${EXTRACT_TAG}"
echo "Transform image: ${ECR_URI}:transform-${TRANSFORM_TAG}"
