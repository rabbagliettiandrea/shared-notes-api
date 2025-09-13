#!/bin/bash

# AWS ECS Service Setup Script for Shared Notes API
# This script creates ECS cluster, task definition, and service with ALB

set -e

# Configuration variables
PROJECT_NAME="shared-notes"
AWS_REGION="eu-central-1"
AWS_PROFILE="rabbagliettiandrea"

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)

echo "🚀 Setting up ECS Service for Shared Notes API"
echo "📦 Project: $PROJECT_NAME"
echo "🌍 Region: $AWS_REGION"
echo "👤 AWS Profile: $AWS_PROFILE"
echo "🏦 Account ID: $ACCOUNT_ID"
echo ""

# Get infrastructure details from default VPC
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --profile $AWS_PROFILE --region $AWS_REGION --query 'Vpcs[0].VpcId' --output text)
SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --profile $AWS_PROFILE --region $AWS_REGION --query 'Subnets[].SubnetId' --output text)
SUBNET_ARRAY=($SUBNETS)
PUBLIC_SUBNET_1=${SUBNET_ARRAY[0]}
PUBLIC_SUBNET_2=${SUBNET_ARRAY[1]}
ALB_SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-alb-sg" --profile $AWS_PROFILE --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text)
ECS_SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-ecs-sg" --profile $AWS_PROFILE --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text)

# Validate infrastructure
if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    echo "❌ No default VPC found in region $AWS_REGION"
    echo "   Please run setup-aws-infrastructure.sh first"
    exit 1
fi

if [ -z "$PUBLIC_SUBNET_1" ] || [ -z "$PUBLIC_SUBNET_2" ]; then
    echo "❌ Not enough subnets found in default VPC"
    echo "   Please run setup-aws-infrastructure.sh first"
    exit 1
fi

if [ "$ALB_SG_ID" = "None" ] || [ -z "$ALB_SG_ID" ]; then
    echo "❌ ALB Security Group not found"
    echo "   Please run setup-aws-infrastructure.sh first"
    exit 1
fi

if [ "$ECS_SG_ID" = "None" ] || [ -z "$ECS_SG_ID" ]; then
    echo "❌ ECS Security Group not found"
    echo "   Please run setup-aws-infrastructure.sh first"
    exit 1
fi

echo "📋 Infrastructure details:"
echo "   VPC: $VPC_ID"
echo "   Public Subnets: $PUBLIC_SUBNET_1, $PUBLIC_SUBNET_2"
echo "   ALB Security Group: $ALB_SG_ID"
echo "   ECS Security Group: $ECS_SG_ID"
echo ""

# Create Application Load Balancer
echo "⚖️  Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name $PROJECT_NAME-alb \
    --subnets $PUBLIC_SUBNET_1 $PUBLIC_SUBNET_2 \
    --security-groups $ALB_SG_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].LoadBalancerArn' \
    --output text 2>/dev/null || aws elbv2 describe-load-balancers --names $PROJECT_NAME-alb --profile $AWS_PROFILE --region $AWS_REGION --query 'LoadBalancers[0].LoadBalancerArn' --output text)

echo "✅ ALB created: $ALB_ARN"

# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns $ALB_ARN --profile $AWS_PROFILE --region $AWS_REGION --query 'LoadBalancers[0].DNSName' --output text)
echo "🌐 ALB DNS: $ALB_DNS"

# Create Target Group
echo "🎯 Creating target group..."
TARGET_GROUP_ARN=$(aws elbv2 create-target-group \
    --name $PROJECT_NAME-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text 2>/dev/null || aws elbv2 describe-target-groups --names $PROJECT_NAME-tg --profile $AWS_PROFILE --region $AWS_REGION --query 'TargetGroups[0].TargetGroupArn' --output text)

echo "✅ Target group created: $TARGET_GROUP_ARN"

# Create ALB Listener
echo "👂 Creating ALB listener..."
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Listener already exists"

echo "✅ ALB listener created"

# Create ECS Cluster
echo "🏗️  Creating ECS cluster..."
aws ecs create-cluster \
    --cluster-name $PROJECT_NAME-cluster \
    --capacity-providers FARGATE \
    --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  ECS cluster already exists"

echo "✅ ECS cluster created"

# Update task definition with actual values
echo "📝 Updating task definition..."
sed "s/ACCOUNT_ID/$ACCOUNT_ID/g; s/REGION/$AWS_REGION/g" ecs-task-definition.json > ecs-task-definition-updated.json

# Register task definition
echo "📋 Registering task definition..."
TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://ecs-task-definition-updated.json \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "✅ Task definition registered: $TASK_DEFINITION_ARN"

# Create ECS Service
echo "🚀 Creating ECS service..."
aws ecs create-service \
    --cluster $PROJECT_NAME-cluster \
    --service-name $PROJECT_NAME-api-service \
    --task-definition $TASK_DEFINITION_ARN \
    --desired-count 2 \
    --launch-type FARGATE \
    --platform-version LATEST \
    --network-configuration "awsvpcConfiguration={subnets=[$PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$TARGET_GROUP_ARN,containerName=shared-notes-api,containerPort=8000" \
    --health-check-grace-period-seconds 300 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  ECS service already exists"

echo "✅ ECS service created"

# Clean up temporary file
rm -f ecs-task-definition-updated.json

echo ""
echo "🎉 ECS Service setup completed successfully!"
echo ""
echo "🌐 Your API will be available at:"
echo "   http://$ALB_DNS"
echo ""
echo "📊 Monitor your service:"
echo "   ECS Console: https://console.aws.amazon.com/ecs/home?region=$AWS_REGION#/clusters/$PROJECT_NAME-cluster/services"
echo "   ALB Console: https://console.aws.amazon.com/ec2/home?region=$AWS_REGION#LoadBalancers:search=$PROJECT_NAME-alb"
echo ""
echo "🔍 Check service status:"
echo "   aws ecs describe-services --cluster $PROJECT_NAME-cluster --services $PROJECT_NAME-api-service --profile $AWS_PROFILE --region $AWS_REGION"
echo ""
echo "📝 Next steps:"
echo "1. Build and push Docker image to ECR"
echo "2. Update ECS service to use new image"
echo "3. Test the API endpoints"
echo "4. Set up GitHub Actions for CI/CD"
