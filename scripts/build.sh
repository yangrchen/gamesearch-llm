#!/bin/bash
set -e

# Function to show usage
show_usage() {
    echo "Usage: $0 [--all | extract | transform | backend]"
    echo ""
    echo "Options:"
    echo "  --all       Build and push all components"
    echo "  extract     Build and push only the extract lambda"
    echo "  transform   Build and push only the transform container"
    echo "  backend     Build and push only the backend container"
    echo ""
    echo "If no argument is provided, --all is assumed."
    exit 1
}

# Parse command line arguments
COMPONENT=""
if [ $# -eq 0 ]; then
    COMPONENT="all"
elif [ $# -eq 1 ]; then
    case $1 in
        --all)
            COMPONENT="all"
            ;;
        extract|transform|backend)
            COMPONENT="$1"
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            echo "Error: Invalid argument '$1'"
            show_usage
            ;;
    esac
else
    echo "Error: Too many arguments"
    show_usage
fi

# Get AWS creds
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

setup_ecr() {
    local ecr_repo="${1:-gamesearch-lambdas}"
    ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ecr_repo}"
    echo "Logging into ECR..."
    aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URI}
}
push_image() {
    local image_path="$1"
    local tag="$2"
    local orig_path=$(pwd)

    cd $1
    docker build --platform linux/amd64 --provenance false -t ${ECR_URI}:${tag} .
    docker push ${ECR_URI}:${tag}
    cd ${orig_path}
}

# Build based on component selection
case $COMPONENT in
    all)
        setup_ecr
        echo "Building all components..."
        push_image etl/gamesearch-extract extract-latest
        push_image etl/gamesearch-transform transform-latest
        setup_ecr gamesearch-backend
        push_image backend/ latest
        echo "Build and push completed successfully for all components!"
        ;;
    extract)
        setup_ecr
        echo "Building extract component only..."
        push_image etl/gamesearch-extract extract-latest
        echo "Build and push completed successfully for extract!"
        ;;
    transform)
        setup_ecr
        echo "Building transform component only..."
        push_image etl/gamesearch-transform transform-latest
        echo "Build and push completed successfully for transform!"
        ;;
    backend)
        setup_ecr gamesearch-backend
        echo "Building backend component only..."
        push_image backend/ latest
        echo "Build and push completed successfully for backend!"
        ;;
esac
