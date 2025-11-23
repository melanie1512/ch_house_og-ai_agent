# AWS App Runner Deployment Guide

This guide provides step-by-step instructions for deploying the Health Assistant API v2 to AWS App Runner.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Pre-Deployment Setup](#pre-deployment-setup)
- [Deployment Methods](#deployment-methods)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Cost Estimation](#cost-estimation)

## Overview

AWS App Runner is a fully managed service that makes it easy to deploy containerized web applications and APIs at scale. This deployment uses App Runner's source code deployment feature, which automatically builds and deploys your application from the repository.

**Architecture:**
```
Source Code → App Runner Build → Container → HTTPS Endpoint
                                    ↓
                            IAM Instance Role
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
                Bedrock         DynamoDB         Lambda
```

## Prerequisites

### Required Tools

1. **AWS CLI** (version 2.x or higher)
   ```bash
   # Check if installed
   aws --version
   
   # Install on macOS
   brew install awscli
   
   # Install on Linux
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   ```

2. **Python 3.9+** (for local testing and table setup)
   ```bash
   python3 --version
   ```

3. **Git** (for source code management)
   ```bash
   git --version
   ```

### AWS Account Requirements

1. **AWS Account** with appropriate permissions
2. **IAM Permissions** to create and manage:
   - App Runner services
   - IAM roles and policies
   - DynamoDB tables
   - CloudWatch Logs
   - (Optional) Lambda functions

3. **Bedrock Model Access**
   - Access to Claude 3 models in your region
   - Go to AWS Console → Bedrock → Model access
   - Request access to `anthropic.claude-3-haiku` or `anthropic.claude-3-sonnet`

### AWS Credentials Configuration

Configure your AWS credentials:

```bash
# Option 1: Using AWS CLI configure
aws configure

# Option 2: Set environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"

# Option 3: Use AWS credentials file (~/.aws/credentials)
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key
region = us-east-1
```

## Pre-Deployment Setup

### Step 1: Configure Environment Variables

Create or update your `.env` file in the `v2-agent` directory:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Bedrock Configuration (choose one)
# Option 1: Use foundation model directly
BEDROCK_MODEL=us.anthropic.claude-3-haiku-20240307-v1:0

# Option 2: Use inference profile (recommended for production)
# BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:us-east-1:123456789012:inference-profile/your-profile

# Bedrock Region (optional, defaults to AWS_REGION)
BEDROCK_REGION=us-east-1

# DynamoDB Configuration
SESSION_TABLE_NAME=user_sessions

# Application Configuration
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO

# CORS Configuration (comma-separated origins)
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Lambda Configuration (optional)
# LAMBDA_FUNCTION_ARN=arn:aws:lambda:us-east-1:123456789012:function:your-function
```

**Important Notes:**
- For `BEDROCK_MODEL`, add the `us.` prefix for cross-region inference profiles
- `ALLOWED_ORIGINS` should list specific domains in production (no wildcards)
- Never commit `.env` files with real credentials to version control

### Step 2: Validate Configuration

Run the configuration validator to ensure all required settings are present:

```bash
cd v2-agent
python3 -c "from config_validator import validate_all_configurations, print_validation_results; \
    all_valid, results = validate_all_configurations(); \
    print_validation_results(results); \
    exit(0 if all_valid else 1)"
```

This will check:
- ✓ Required environment variables are set
- ✓ Health check configuration is valid
- ✓ Auto-scaling configuration is valid

### Step 3: Create DynamoDB Tables

Before deploying, ensure all required DynamoDB tables exist:

```bash
cd v2-agent

# Validate that tables exist
python3 setup_tables.py --validate

# If tables don't exist, create them
python3 setup_tables.py --region us-east-1

# Force recreation (if needed)
python3 setup_tables.py --region us-east-1 --force
```

This creates three tables:
- **doctores**: Doctor information with specialty indexing
- **horarios_doctores**: Doctor schedules
- **user_sessions**: User session data with TTL (1 hour expiration)

All tables use `PAY_PER_REQUEST` billing mode for cost efficiency.

### Step 4: Set Up IAM Role

The deployment script will automatically create the IAM role, but you can also create it manually:

#### Automatic (Recommended)

The `deploy.sh` script handles IAM role creation automatically. Skip to [Deployment Methods](#deployment-methods).

#### Manual Setup

If you prefer manual setup, follow the instructions in [IAM_SETUP.md](IAM_SETUP.md):

```bash
# Create IAM role
aws iam create-role \
  --role-name health-assistant-apprunner-role \
  --assume-role-policy-document file://iam-trust-policy.json

# Attach permissions policy
aws iam put-role-policy \
  --role-name health-assistant-apprunner-role \
  --policy-name health-assistant-permissions \
  --policy-document file://iam-policy.json

# Get the role ARN (save this for deployment)
aws iam get-role \
  --role-name health-assistant-apprunner-role \
  --query 'Role.Arn' \
  --output text
```

## Deployment Methods

### Method 1: Using Deployment Script (Recommended)

The `deploy.sh` script automates the entire deployment process.

#### Create New Service

```bash
cd v2-agent

# Make script executable
chmod +x deploy.sh

# Create service with default settings
./deploy.sh create

# Create service with custom settings
./deploy.sh create \
  --service-name my-health-api \
  --region us-west-2 \
  --role-name my-custom-role
```

The script will:
1. ✓ Validate AWS CLI is installed
2. ✓ Check required files exist
3. ✓ Create or update IAM role
4. ✓ Load environment variables from `.env`
5. ✓ Create App Runner service
6. ✓ Wait for service to become healthy
7. ✓ Display service URL

#### Update Existing Service

```bash
# Update service with latest code and configuration
./deploy.sh update --service-name health-assistant-api

# Update with custom region
./deploy.sh update --service-name my-api --region us-west-2
```

#### Check Service Status

```bash
# Check status of your service
./deploy.sh status --service-name health-assistant-api
```

Output includes:
- Service status (RUNNING, CREATE_FAILED, etc.)
- Service URL
- Creation timestamp
- Region

#### Delete Service

```bash
# Delete service (requires confirmation)
./deploy.sh delete --service-name health-assistant-api
```

### Method 2: Manual Deployment via AWS Console

1. **Navigate to App Runner**
   - Go to AWS Console → App Runner
   - Click "Create service"

2. **Configure Source**
   - Source: "Source code repository"
   - Connect to your repository (GitHub, Bitbucket, etc.)
   - Or use "ECR" if you have a container image

3. **Configure Build**
   - Runtime: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port 8000`
   - Port: 8000

4. **Configure Service**
   - Service name: `health-assistant-api`
   - Virtual CPU: 1 vCPU
   - Memory: 2 GB
   - Instance role: Select the IAM role created earlier

5. **Configure Environment Variables**
   Add all variables from your `.env` file:
   - AWS_REGION
   - BEDROCK_MODEL (or BEDROCK_INFERENCE_PROFILE_ARN)
   - SESSION_TABLE_NAME
   - ENVIRONMENT
   - ALLOWED_ORIGINS
   - etc.

6. **Configure Auto-scaling**
   - Min instances: 1
   - Max instances: 10
   - Max concurrency: 100

7. **Configure Health Check**
   - Protocol: HTTP
   - Path: `/docs`
   - Interval: 10 seconds
   - Timeout: 5 seconds
   - Healthy threshold: 1
   - Unhealthy threshold: 5

8. **Review and Create**
   - Review all settings
   - Click "Create & deploy"
   - Wait for deployment to complete (~5-10 minutes)

### Method 3: Using AWS CLI Directly

```bash
# Set variables
SERVICE_NAME="health-assistant-api"
REGION="us-east-1"
ROLE_ARN="arn:aws:iam::123456789012:role/health-assistant-apprunner-role"

# Create service
aws apprunner create-service \
  --service-name $SERVICE_NAME \
  --region $REGION \
  --source-configuration file://apprunner-source-config.json \
  --instance-configuration "{
    \"Cpu\": \"1 vCPU\",
    \"Memory\": \"2 GB\",
    \"InstanceRoleArn\": \"$ROLE_ARN\"
  }" \
  --health-check-configuration "{
    \"Protocol\": \"HTTP\",
    \"Path\": \"/docs\",
    \"Interval\": 10,
    \"Timeout\": 5,
    \"HealthyThreshold\": 1,
    \"UnhealthyThreshold\": 5
  }"
```

## Post-Deployment Configuration

### Configure Custom Domain (Optional)

1. **Add Custom Domain**
   ```bash
   aws apprunner associate-custom-domain \
     --service-arn <your-service-arn> \
     --domain-name api.yourdomain.com
   ```

2. **Update DNS Records**
   - Add CNAME records as instructed by App Runner
   - Wait for DNS propagation (~5-60 minutes)

3. **Verify Domain**
   ```bash
   aws apprunner describe-custom-domains \
     --service-arn <your-service-arn>
   ```

### Configure Auto-Scaling (Advanced)

Create a custom auto-scaling configuration:

```bash
aws apprunner create-auto-scaling-configuration \
  --auto-scaling-configuration-name health-api-scaling \
  --max-concurrency 100 \
  --min-size 1 \
  --max-size 25

# Update service to use custom configuration
aws apprunner update-service \
  --service-arn <your-service-arn> \
  --auto-scaling-configuration-arn <config-arn>
```

### Enable Observability Features

1. **CloudWatch Logs** (enabled by default)
   - View logs: AWS Console → CloudWatch → Log groups
   - Log group: `/aws/apprunner/<service-name>/application`

2. **X-Ray Tracing** (optional)
   ```bash
   aws apprunner update-service \
     --service-arn <your-service-arn> \
     --observability-configuration "{
       \"ObservabilityEnabled\": true,
       \"ObservabilityConfigurationArn\": \"<xray-config-arn>\"
     }"
   ```

## Verification

### Step 1: Check Service Health

```bash
# Using deployment script
./deploy.sh status --service-name health-assistant-api

# Using AWS CLI
aws apprunner describe-service \
  --service-arn <your-service-arn> \
  --query 'Service.Status' \
  --output text
```

Expected status: `RUNNING`

### Step 2: Test API Endpoints

```bash
# Get service URL
SERVICE_URL=$(aws apprunner describe-service \
  --service-arn <your-service-arn> \
  --query 'Service.ServiceUrl' \
  --output text)

# Test health endpoint
curl https://$SERVICE_URL/docs

# Test main router endpoint
curl -X POST https://$SERVICE_URL/agent/route \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "message": "Me duele la cabeza desde hace 2 días"
  }'
```

Expected response:
```json
{
  "endpoint": "triage/interpret",
  "confidence": 0.95,
  "reasoning": "El usuario describe síntomas médicos",
  "message": "...",
  "response": {
    "capa": 2,
    "especialidad_sugerida": "Medicina General",
    ...
  }
}
```

### Step 3: Verify AWS Service Integration

1. **Check Bedrock Access**
   ```bash
   # View CloudWatch logs for Bedrock API calls
   aws logs tail /aws/apprunner/health-assistant-api/application --follow
   ```

2. **Check DynamoDB Access**
   ```bash
   # Verify session data is being written
   aws dynamodb scan \
     --table-name user_sessions \
     --limit 5
   ```

3. **Check IAM Role**
   ```bash
   # Verify role is attached to service
   aws apprunner describe-service \
     --service-arn <your-service-arn> \
     --query 'Service.InstanceConfiguration.InstanceRoleArn'
   ```

### Step 4: Load Testing (Optional)

```bash
# Install Apache Bench
brew install httpd  # macOS
sudo apt-get install apache2-utils  # Linux

# Run load test
ab -n 1000 -c 10 -p request.json -T application/json \
  https://$SERVICE_URL/agent/route
```

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Service Fails to Start

**Symptoms:**
- Service status: `CREATE_FAILED` or `UPDATE_FAILED`
- Health checks failing

**Solutions:**

1. **Check CloudWatch Logs**
   ```bash
   aws logs tail /aws/apprunner/health-assistant-api/application --follow
   ```
   Look for:
   - Python import errors
   - Missing dependencies
   - Environment variable errors

2. **Verify apprunner.yaml**
   ```bash
   # Validate YAML syntax
   python3 -c "import yaml; yaml.safe_load(open('apprunner.yaml'))"
   ```

3. **Check Build Command**
   - Ensure `requirements.txt` is present
   - Verify all dependencies are installable
   - Test locally: `pip install -r requirements.txt`

4. **Verify Start Command**
   - Test locally: `uvicorn main:app --host 0.0.0.0 --port 8000`
   - Check that `main.py` exists and has `app` variable

#### Issue 2: Access Denied Errors

**Symptoms:**
- Bedrock API calls fail with `AccessDeniedException`
- DynamoDB operations fail with `AccessDeniedException`

**Solutions:**

1. **Verify IAM Role is Attached**
   ```bash
   aws apprunner describe-service \
     --service-arn <your-service-arn> \
     --query 'Service.InstanceConfiguration.InstanceRoleArn'
   ```

2. **Check IAM Policy**
   ```bash
   # List role policies
   aws iam list-role-policies --role-name health-assistant-apprunner-role
   
   # Get policy document
   aws iam get-role-policy \
     --role-name health-assistant-apprunner-role \
     --policy-name health-assistant-permissions
   ```

3. **Verify Trust Policy**
   ```bash
   aws iam get-role \
     --role-name health-assistant-apprunner-role \
     --query 'Role.AssumeRolePolicyDocument'
   ```
   
   Ensure it allows `tasks.apprunner.amazonaws.com` to assume the role.

4. **Check Resource ARNs**
   - Verify table names in IAM policy match actual table names
   - Verify Bedrock model ARNs are correct
   - Verify AWS account ID in ARNs is correct

#### Issue 3: DynamoDB Table Not Found

**Symptoms:**
- `ResourceNotFoundException` for DynamoDB tables
- Application fails to start or crashes on first request

**Solutions:**

1. **Verify Tables Exist**
   ```bash
   python3 setup_tables.py --validate --region us-east-1
   ```

2. **Check Table Names**
   - Verify `SESSION_TABLE_NAME` environment variable matches actual table name
   - Default table names: `doctores`, `horarios_doctores`, `user_sessions`

3. **Check Region**
   - Ensure tables are in the same region as App Runner service
   - Verify `AWS_REGION` environment variable is correct

4. **Create Missing Tables**
   ```bash
   python3 setup_tables.py --region us-east-1
   ```

#### Issue 4: CORS Errors

**Symptoms:**
- Browser console shows CORS errors
- Preflight OPTIONS requests fail

**Solutions:**

1. **Check ALLOWED_ORIGINS**
   ```bash
   # Verify environment variable is set
   aws apprunner describe-service \
     --service-arn <your-service-arn> \
     --query 'Service.SourceConfiguration.CodeRepository.CodeConfiguration.CodeConfigurationValues.RuntimeEnvironmentVariables'
   ```

2. **Update CORS Configuration**
   - Edit `.env` file
   - Update `ALLOWED_ORIGINS` with your frontend domain
   - Redeploy: `./deploy.sh update`

3. **Test CORS Headers**
   ```bash
   curl -H "Origin: https://yourdomain.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://$SERVICE_URL/agent/route -v
   ```

#### Issue 5: High Latency or Timeouts

**Symptoms:**
- Requests take > 30 seconds
- Gateway timeout errors (504)

**Solutions:**

1. **Check Bedrock Model**
   - Haiku models are faster than Sonnet
   - Use inference profiles for better performance
   - Consider caching responses

2. **Optimize DynamoDB Queries**
   - Use indexes for common queries
   - Avoid full table scans
   - Consider using batch operations

3. **Increase Instance Size**
   ```bash
   aws apprunner update-service \
     --service-arn <your-service-arn> \
     --instance-configuration "{
       \"Cpu\": \"2 vCPU\",
       \"Memory\": \"4 GB\"
     }"
   ```

4. **Scale Out**
   - Increase max instances in auto-scaling configuration
   - Reduce max concurrency to trigger scaling earlier

#### Issue 6: Environment Variables Not Loading

**Symptoms:**
- Application uses default values instead of configured values
- `KeyError` or `None` values for environment variables

**Solutions:**

1. **Verify Variables in Service**
   ```bash
   aws apprunner describe-service \
     --service-arn <your-service-arn> \
     --query 'Service.SourceConfiguration.CodeRepository.CodeConfiguration.CodeConfigurationValues.RuntimeEnvironmentVariables'
   ```

2. **Update Environment Variables**
   ```bash
   # Edit .env file
   # Then update service
   ./deploy.sh update --service-name health-assistant-api
   ```

3. **Check Variable Names**
   - Ensure no typos in variable names
   - Environment variables are case-sensitive
   - No spaces around `=` in `.env` file

### Getting Help

If you continue to experience issues:

1. **Check CloudWatch Logs**
   - Application logs: `/aws/apprunner/<service-name>/application`
   - Service logs: `/aws/apprunner/<service-name>/service`

2. **Enable Debug Logging**
   - Set `LOG_LEVEL=DEBUG` in environment variables
   - Redeploy service
   - Check logs for detailed error messages

3. **AWS Support**
   - Open a support case in AWS Console
   - Include service ARN and error messages
   - Attach relevant CloudWatch logs

4. **Community Resources**
   - AWS App Runner documentation
   - AWS re:Post community forums
   - Stack Overflow (tag: aws-app-runner)

## Monitoring and Maintenance

### CloudWatch Metrics

Key metrics to monitor:

1. **Request Metrics**
   - `2xxStatusResponses`: Successful requests
   - `4xxStatusResponses`: Client errors
   - `5xxStatusResponses`: Server errors
   - `RequestCount`: Total requests

2. **Performance Metrics**
   - `RequestLatency`: Response time
   - `ActiveInstances`: Number of running instances
   - `CPUUtilization`: CPU usage
   - `MemoryUtilization`: Memory usage

### Setting Up Alarms

```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name health-api-high-error-rate \
  --alarm-description "Alert when 5xx error rate is high" \
  --metric-name 5xxStatusResponses \
  --namespace AWS/AppRunner \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=health-assistant-api

# Create alarm for high latency
aws cloudwatch put-metric-alarm \
  --alarm-name health-api-high-latency \
  --alarm-description "Alert when latency is high" \
  --metric-name RequestLatency \
  --namespace AWS/AppRunner \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=health-assistant-api
```

### Log Analysis

Use CloudWatch Logs Insights to query logs:

```sql
-- Find all errors in the last hour
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100

-- Analyze request latency
fields @timestamp, @message
| filter @message like /Request completed/
| parse @message /duration: (?<duration>\d+)ms/
| stats avg(duration), max(duration), min(duration) by bin(5m)

-- Count requests by endpoint
fields @timestamp, @message
| filter @message like /POST/
| parse @message /POST (?<endpoint>\/[^ ]+)/
| stats count() by endpoint
```

### Regular Maintenance Tasks

1. **Weekly**
   - Review CloudWatch metrics and alarms
   - Check for any failed deployments
   - Review error logs for patterns

2. **Monthly**
   - Review and optimize DynamoDB usage
   - Analyze cost and usage reports
   - Update dependencies in `requirements.txt`
   - Review and update IAM policies

3. **Quarterly**
   - Load testing and performance optimization
   - Security audit of IAM roles and policies
   - Review and update Bedrock model versions
   - Disaster recovery testing

### Backup and Disaster Recovery

1. **DynamoDB Backups**
   ```bash
   # Enable point-in-time recovery
   aws dynamodb update-continuous-backups \
     --table-name user_sessions \
     --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
   
   # Create on-demand backup
   aws dynamodb create-backup \
     --table-name user_sessions \
     --backup-name user-sessions-backup-$(date +%Y%m%d)
   ```

2. **Configuration Backups**
   - Keep `apprunner.yaml`, `iam-policy.json`, and `iam-trust-policy.json` in version control
   - Document environment variables in a secure location
   - Export service configuration periodically

3. **Disaster Recovery Plan**
   - Document steps to recreate service in another region
   - Test recovery procedures quarterly
   - Maintain list of all dependencies and their versions

## Cost Estimation

### App Runner Costs

**Pricing Model:**
- Provisioned container instances: $0.007/hour per GB memory
- Active requests: $0.10 per GB of data processed

**Example Calculation:**

For a service with:
- 2 GB memory per instance
- 2 instances running 24/7
- 1 million requests/month
- Average 10 KB per request

```
Compute: 2 GB × 2 instances × 730 hours × $0.007 = $20.44/month
Requests: 1M requests × 10 KB × $0.10/GB = $1.00/month
Total App Runner: ~$21.44/month
```

### Additional AWS Service Costs

1. **Bedrock (Claude 3 Haiku)**
   - Input: $0.00025 per 1K tokens
   - Output: $0.00125 per 1K tokens
   - Estimate: $10-50/month depending on usage

2. **DynamoDB (PAY_PER_REQUEST)**
   - Read: $0.25 per million requests
   - Write: $1.25 per million requests
   - Storage: $0.25 per GB-month
   - Estimate: $5-20/month

3. **CloudWatch Logs**
   - Ingestion: $0.50 per GB
   - Storage: $0.03 per GB-month
   - Estimate: $2-10/month

4. **Data Transfer**
   - First 100 GB/month: Free
   - Next 10 TB/month: $0.09 per GB
   - Estimate: $0-20/month

**Total Estimated Monthly Cost: $40-120**

### Cost Optimization Tips

1. **Right-size Instances**
   - Start with 1 vCPU / 2 GB
   - Monitor CPU and memory usage
   - Scale up only if needed

2. **Optimize Auto-Scaling**
   - Set appropriate min/max instances
   - Adjust max concurrency based on actual load
   - Use scheduled scaling for predictable traffic patterns

3. **Optimize Bedrock Usage**
   - Use Haiku instead of Sonnet when possible
   - Implement response caching
   - Optimize prompts to reduce token usage

4. **DynamoDB Optimization**
   - Use PAY_PER_REQUEST for variable workloads
   - Consider provisioned capacity for consistent high traffic
   - Enable auto-scaling for provisioned capacity
   - Use TTL to automatically delete old data

5. **Reduce Logging Costs**
   - Set appropriate log retention periods
   - Filter logs to reduce volume
   - Use log sampling for high-volume endpoints

## Additional Resources

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [IAM Setup Guide](IAM_SETUP.md)
- [Table Setup Guide](README_TABLES.md)
- [Logging Configuration](LOGGING.md)

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review CloudWatch logs
3. Consult AWS documentation
4. Open an issue in the project repository
