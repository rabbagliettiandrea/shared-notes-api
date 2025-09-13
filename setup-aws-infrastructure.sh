#!/bin/bash

# AWS ECS Infrastructure Setup Script for Shared Notes API
# This script creates the complete infrastructure: VPC, RDS, ElastiCache, ECS, ALB

set -e

# Configuration variables
PROJECT_NAME="shared-notes"
AWS_REGION="eu-central-1"
AWS_PROFILE="rabbagliettiandrea"
ENVIRONMENT="prod"

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)

echo "🚀 Setting up AWS ECS Infrastructure for Shared Notes API"
echo "📦 Project: $PROJECT_NAME"
echo "🌍 Region: $AWS_REGION"
echo "👤 AWS Profile: $AWS_PROFILE"
echo "🏦 Account ID: $ACCOUNT_ID"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first:"
    echo "   https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Check AWS credentials
echo "🔐 Checking AWS credentials..."
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" &> /dev/null; then
    echo "❌ AWS credentials not configured for profile '$AWS_PROFILE'"
    echo "   Run: aws configure --profile $AWS_PROFILE"
    exit 1
fi

echo "✅ AWS credentials verified"
echo ""

# Create ECR repository
echo "📦 Creating ECR repository..."
aws ecr create-repository \
    --repository-name $PROJECT_NAME-api \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true \
    || echo "⚠️  ECR repository already exists"

# Get ECR login token
echo "🔑 Getting ECR login token..."
aws ecr get-login-password --profile $AWS_PROFILE --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Use default VPC
echo "🌐 Using default VPC..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --profile $AWS_PROFILE --region $AWS_REGION --query 'Vpcs[0].VpcId' --output text)

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    echo "❌ No default VPC found in region $AWS_REGION"
    echo "   Please create a default VPC or specify a custom VPC ID"
    exit 1
fi

echo "✅ Using default VPC: $VPC_ID"

# Get Internet Gateway (should already exist for default VPC)
echo "🌍 Getting Internet Gateway for default VPC..."
IGW_ID=$(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --profile $AWS_PROFILE --region $AWS_REGION --query 'InternetGateways[0].InternetGatewayId' --output text)

if [ "$IGW_ID" = "None" ] || [ -z "$IGW_ID" ]; then
    echo "❌ No Internet Gateway found for default VPC"
    echo "   Default VPC should have an Internet Gateway. Please check your AWS setup."
    exit 1
fi

echo "✅ Internet Gateway found: $IGW_ID"

# Use existing subnets from default VPC
echo "🏗️  Using existing subnets from default VPC..."

# Get first two subnets from default VPC (they should be public by default)
SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --profile $AWS_PROFILE --region $AWS_REGION --query 'Subnets[].SubnetId' --output text)

# Convert to array and get first two subnets
SUBNET_ARRAY=($SUBNETS)
PUBLIC_SUBNET_1=${SUBNET_ARRAY[0]}
PUBLIC_SUBNET_2=${SUBNET_ARRAY[1]}

if [ -z "$PUBLIC_SUBNET_1" ] || [ -z "$PUBLIC_SUBNET_2" ]; then
    echo "❌ Not enough subnets found in default VPC"
    echo "   Default VPC should have at least 2 subnets. Please check your AWS setup."
    exit 1
fi

# For simplicity, we'll use the same subnets for private resources
# In a production environment, you might want to create dedicated private subnets
PRIVATE_SUBNET_1=$PUBLIC_SUBNET_1
PRIVATE_SUBNET_2=$PUBLIC_SUBNET_2

echo "✅ Using existing subnets:"
echo "   Subnet 1: $PUBLIC_SUBNET_1"
echo "   Subnet 2: $PUBLIC_SUBNET_2"

# Use existing route table from default VPC
echo "🗺️  Using existing route table from default VPC..."
ROUTE_TABLE_ID=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" "Name=association.main,Values=true" --profile $AWS_PROFILE --region $AWS_REGION --query 'RouteTables[0].RouteTableId' --output text)

if [ "$ROUTE_TABLE_ID" = "None" ] || [ -z "$ROUTE_TABLE_ID" ]; then
    echo "❌ No main route table found for default VPC"
    echo "   Default VPC should have a main route table. Please check your AWS setup."
    exit 1
fi

echo "✅ Using existing route table: $ROUTE_TABLE_ID"

# Create Security Groups
echo "🔒 Creating security groups..."

# ALB Security Group
ALB_SG_ID=$(aws ec2 create-security-group \
    --group-name $PROJECT_NAME-alb-sg \
    --description "Security group for Application Load Balancer" \
    --vpc-id $VPC_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'GroupId' \
    --output text 2>/dev/null || aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-alb-sg" --profile $AWS_PROFILE --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text)

# Allow HTTP and HTTPS from anywhere
aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Rule already exists"

aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Rule already exists"

# ECS Security Group
ECS_SG_ID=$(aws ec2 create-security-group \
    --group-name $PROJECT_NAME-ecs-sg \
    --description "Security group for ECS tasks" \
    --vpc-id $VPC_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'GroupId' \
    --output text 2>/dev/null || aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-ecs-sg" --profile $AWS_PROFILE --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text)

# Allow traffic from ALB
aws ec2 authorize-security-group-ingress \
    --group-id $ECS_SG_ID \
    --protocol tcp \
    --port 8000 \
    --source-group $ALB_SG_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Rule already exists"

# RDS Security Group
RDS_SG_ID=$(aws ec2 create-security-group \
    --group-name $PROJECT_NAME-rds-sg \
    --description "Security group for RDS PostgreSQL" \
    --vpc-id $VPC_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'GroupId' \
    --output text 2>/dev/null || aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-rds-sg" --profile $AWS_PROFILE --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text)

# Allow PostgreSQL from ECS
aws ec2 authorize-security-group-ingress \
    --group-id $RDS_SG_ID \
    --protocol tcp \
    --port 5432 \
    --source-group $ECS_SG_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Rule already exists"

# ElastiCache Security Group
CACHE_SG_ID=$(aws ec2 create-security-group \
    --group-name $PROJECT_NAME-cache-sg \
    --description "Security group for ElastiCache Redis" \
    --vpc-id $VPC_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'GroupId' \
    --output text 2>/dev/null || aws ec2 describe-security-groups --filters "Name=group-name,Values=$PROJECT_NAME-cache-sg" --profile $AWS_PROFILE --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text)

# Allow Redis from ECS
aws ec2 authorize-security-group-ingress \
    --group-id $CACHE_SG_ID \
    --protocol tcp \
    --port 6379 \
    --source-group $ECS_SG_ID \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Rule already exists"

echo "✅ Security groups created"

# Create DB Subnet Group
echo "🗄️  Creating DB subnet group..."
aws rds create-db-subnet-group \
    --db-subnet-group-name $PROJECT_NAME-db-subnet-group \
    --db-subnet-group-description "Subnet group for RDS PostgreSQL" \
    --subnet-ids $PRIVATE_SUBNET_1 $PRIVATE_SUBNET_2 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  DB subnet group already exists"

# Create ElastiCache Subnet Group
echo "🔄 Creating ElastiCache subnet group..."
aws elasticache create-cache-subnet-group \
    --cache-subnet-group-name $PROJECT_NAME-cache-subnet-group \
    --cache-subnet-group-description "Subnet group for ElastiCache Redis" \
    --subnet-ids $PRIVATE_SUBNET_1 $PRIVATE_SUBNET_2 \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  ElastiCache subnet group already exists"

# Create RDS PostgreSQL instance
echo "🐘 Creating RDS PostgreSQL instance..."
# Generate a password that's compatible with RDS (no /, @, ", or spaces)
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '/@\" ' | head -c 32)

# Check if RDS instance already exists
if aws rds describe-db-instances --db-instance-identifier $PROJECT_NAME-postgres --profile $AWS_PROFILE --region $AWS_REGION &> /dev/null; then
    echo "⚠️  RDS instance already exists, getting endpoint..."
    DB_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier $PROJECT_NAME-postgres --profile $AWS_PROFILE --region $AWS_REGION --query 'DBInstances[0].Endpoint.Address' --output text)
else
    echo "🔄 Creating new RDS instance..."
    aws rds create-db-instance \
        --db-instance-identifier $PROJECT_NAME-postgres \
        --db-instance-class db.t3.micro \
        --engine postgres \
        --master-username postgres \
        --master-user-password $DB_PASSWORD \
        --allocated-storage 20 \
        --storage-type gp2 \
        --db-name shared_notes \
        --vpc-security-group-ids $RDS_SG_ID \
        --db-subnet-group-name $PROJECT_NAME-db-subnet-group \
        --backup-retention-period 7 \
        --multi-az \
        --publicly-accessible \
        --storage-encrypted \
        --profile $AWS_PROFILE \
        --region $AWS_REGION
    
    echo "⏳ RDS instance is being created. This may take 5-10 minutes..."
    echo "   You can check the status in AWS Console: https://console.aws.amazon.com/rds/home?region=$AWS_REGION#databases"
    
    # For now, we'll use a placeholder. The actual endpoint will be available later
    DB_ENDPOINT="pending-creation"
fi

echo "✅ RDS PostgreSQL instance: $DB_ENDPOINT"

# Create ElastiCache Valkey cluster (single node using replication group)
echo "🔴 Creating ElastiCache Valkey cluster (single node)..."

# Check if ElastiCache cluster already exists
if aws elasticache describe-replication-groups --replication-group-id $PROJECT_NAME-valkey --profile $AWS_PROFILE --region $AWS_REGION &> /dev/null; then
    echo "⚠️  ElastiCache Valkey cluster already exists, getting endpoint..."
    CACHE_ENDPOINT=$(aws elasticache describe-replication-groups --replication-group-id $PROJECT_NAME-valkey --profile $AWS_PROFILE --region $AWS_REGION --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address' --output text)
else
    echo "🔄 Creating new ElastiCache Valkey cluster..."
    aws elasticache create-replication-group \
        --replication-group-id $PROJECT_NAME-valkey \
        --replication-group-description "Valkey cluster for Shared Notes API" \
        --cache-node-type cache.t3.micro \
        --engine valkey \
        --num-cache-clusters 1 \
        --cache-subnet-group-name $PROJECT_NAME-cache-subnet-group \
        --security-group-ids $CACHE_SG_ID \
        --port 6379 \
        --transit-encryption-enabled \
        --profile $AWS_PROFILE \
        --region $AWS_REGION
    
    echo "⏳ ElastiCache Valkey cluster is being created. This may take 5-10 minutes..."
    echo "   You can check the status in AWS Console: https://console.aws.amazon.com/elasticache/home?region=$AWS_REGION#/redis"
    
    # For now, we'll use a placeholder. The actual endpoint will be available later
    CACHE_ENDPOINT="pending-creation"
fi

echo "✅ ElastiCache Valkey cluster: $CACHE_ENDPOINT"

# Store secrets in AWS Secrets Manager
echo "🔐 Storing secrets in AWS Secrets Manager..."
SECRET_KEY=$(openssl rand -base64 32)

# Only store secrets if endpoints are available
if [ "$DB_ENDPOINT" != "pending-creation" ]; then
    DATABASE_URL="postgresql://postgres:$DB_PASSWORD@$DB_ENDPOINT:5432/shared_notes"
    
    aws secretsmanager create-secret \
        --name shared-notes/database-url \
        --description "Database URL for Shared Notes API" \
        --secret-string "$DATABASE_URL" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        || aws secretsmanager update-secret \
            --secret-id shared-notes/database-url \
            --secret-string "$DATABASE_URL" \
            --profile $AWS_PROFILE \
            --region $AWS_REGION
    
    echo "✅ Database URL stored in Secrets Manager"
else
    echo "⚠️  Database URL not stored - RDS instance is still being created"
fi

if [ "$CACHE_ENDPOINT" != "pending-creation" ]; then
    VALKEY_URL="valkey://$CACHE_ENDPOINT:6379"
    
    aws secretsmanager create-secret \
        --name shared-notes/valkey-url \
        --description "Valkey URL for Shared Notes API" \
        --secret-string "$VALKEY_URL" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        || aws secretsmanager update-secret \
            --secret-id shared-notes/valkey-url \
            --secret-string "$VALKEY_URL" \
            --profile $AWS_PROFILE \
            --region $AWS_REGION
    
    echo "✅ Valkey URL stored in Secrets Manager"
else
    echo "⚠️  Valkey URL not stored - ElastiCache cluster is still being created"
fi

# Always store the secret key
aws secretsmanager create-secret \
    --name shared-notes/secret-key \
    --description "JWT Secret Key for Shared Notes API" \
    --secret-string "$SECRET_KEY" \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || aws secretsmanager update-secret \
        --secret-id shared-notes/secret-key \
        --secret-string "$SECRET_KEY" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION

echo "✅ Secret key stored in AWS Secrets Manager"

# Create CloudWatch Log Group
echo "📊 Creating CloudWatch log group..."
aws logs create-log-group \
    --log-group-name /ecs/$PROJECT_NAME-api \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    || echo "⚠️  Log group already exists"

echo "✅ CloudWatch log group created"

echo ""
echo "🎉 Infrastructure setup completed successfully!"
echo ""

if [ "$DB_ENDPOINT" = "pending-creation" ] || [ "$CACHE_ENDPOINT" = "pending-creation" ]; then
    echo "⏳ IMPORTANT: Some resources are still being created:"
    if [ "$DB_ENDPOINT" = "pending-creation" ]; then
        echo "   - RDS PostgreSQL instance is being created (5-10 minutes)"
    fi
    if [ "$CACHE_ENDPOINT" = "pending-creation" ]; then
        echo "   - ElastiCache Valkey cluster is being created (5-10 minutes)"
    fi
    echo ""
    echo "📋 Next steps:"
    echo "1. ⏳ Wait for RDS and ElastiCache to be available"
    echo "2. 🔄 Run this script again to update secrets with actual endpoints"
    echo "3. 🚀 Run ./setup-ecs-service.sh to create ECS cluster and ALB"
    echo "4. 🔧 Configure GitHub Actions for deployment"
    echo ""
    echo "🔍 Monitor progress:"
    echo "   RDS: https://console.aws.amazon.com/rds/home?region=$AWS_REGION#databases"
    echo "   ElastiCache: https://console.aws.amazon.com/elasticache/home?region=$AWS_REGION#/redis"
else
    echo "📋 Next steps:"
    echo "1. 🚀 Run ./setup-ecs-service.sh to create ECS cluster and ALB"
    echo "2. 🔧 Configure GitHub Actions for deployment"
fi

echo ""
echo "🔗 Resources created:"
echo "   Database: $DB_ENDPOINT"
echo "   Valkey: $CACHE_ENDPOINT"
echo "   ECR: $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME-api"
echo ""
echo "🔐 Secrets stored:"
echo "   - shared-notes/secret-key ✅"
if [ "$DB_ENDPOINT" != "pending-creation" ]; then
    echo "   - shared-notes/database-url ✅"
else
    echo "   - shared-notes/database-url ⏳ (will be updated when RDS is ready)"
fi
if [ "$CACHE_ENDPOINT" != "pending-creation" ]; then
    echo "   - shared-notes/valkey-url ✅"
else
    echo "   - shared-notes/valkey-url ⏳ (will be updated when ElastiCache is ready)"
fi
