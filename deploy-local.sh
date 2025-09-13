#!/bin/bash

# Local Build and Deploy Script for Shared Notes API
# This script builds the Docker image and deploys it to ECS

set -e

# Configuration variables
PROJECT_NAME="shared-notes"
AWS_REGION="eu-central-1"
AWS_PROFILE="rabbagliettiandrea"

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
ECR_REPOSITORY="$PROJECT_NAME-api"

echo "🚀 Building and deploying Shared Notes API"
echo "📦 Project: $PROJECT_NAME"
echo "🌍 Region: $AWS_REGION"
echo "👤 AWS Profile: $AWS_PROFILE"
echo "🏦 Account ID: $ACCOUNT_ID"
echo "📦 ECR Registry: $ECR_REGISTRY"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✅ Docker is running"

# Login to ECR
echo "🔑 Logging in to Amazon ECR..."
aws ecr get-login-password --profile $AWS_PROFILE --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

echo "✅ Logged in to ECR"

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t $ECR_REPOSITORY:latest .

echo "✅ Docker image built"

# Tag image for ECR
echo "🏷️  Tagging image for ECR..."
docker tag $ECR_REPOSITORY:latest $ECR_REGISTRY/$ECR_REPOSITORY:latest

echo "✅ Image tagged"

# Push image to ECR
echo "📤 Pushing image to ECR..."
docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

echo "✅ Image pushed to ECR"

# Update ECS service
echo "🚀 Updating ECS service..."
aws ecs update-service \
    --cluster $PROJECT_NAME-cluster \
    --service $PROJECT_NAME-api-service \
    --force-new-deployment \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'service.serviceName' \
    --output text

echo "✅ ECS service updated"

# Wait for deployment to complete
echo "⏳ Waiting for deployment to complete..."
aws ecs wait services-stable \
    --cluster $PROJECT_NAME-cluster \
    --services $PROJECT_NAME-api-service \
    --profile $AWS_PROFILE \
    --region $AWS_REGION

echo "✅ Deployment completed"

# Get service URL
echo "🌐 Getting service URL..."
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --names $PROJECT_NAME-alb \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].DNSName' \
    --output text)

API_URL="http://$ALB_DNS"

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "🌐 API URL: $API_URL"
echo "🔍 Health Check: $API_URL/health"
echo "📊 API Docs: $API_URL/docs"
echo ""
echo "🧪 Testing API..."
if curl -f "$API_URL/health" > /dev/null 2>&1; then
    echo "✅ API is healthy and responding!"
else
    echo "⚠️  API might still be starting up. Try again in a few minutes."
fi
echo ""
echo "📊 Monitor your service:"
echo "   ECS Console: https://console.aws.amazon.com/ecs/home?region=$AWS_REGION#/clusters/$PROJECT_NAME-cluster/services"
echo "   CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups/log-group/\$252Fecs\$252F$PROJECT_NAME-api"
echo ""
echo "🔍 Useful commands:"
echo "   Check service status: aws ecs describe-services --cluster $PROJECT_NAME-cluster --services $PROJECT_NAME-api-service --profile $AWS_PROFILE --region $AWS_REGION"
echo "   View logs: aws logs tail /ecs/$PROJECT_NAME-api --follow --profile $AWS_PROFILE --region $AWS_REGION"
echo "   Scale service: aws ecs update-service --cluster $PROJECT_NAME-cluster --service $PROJECT_NAME-api-service --desired-count 3 --profile $AWS_PROFILE --region $AWS_REGION"
