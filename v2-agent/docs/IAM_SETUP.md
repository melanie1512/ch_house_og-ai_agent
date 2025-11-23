# IAM Setup for App Runner Deployment

This document describes how to set up the IAM role and policies required for deploying the Health Assistant API to AWS App Runner.

## Overview

The App Runner service requires an IAM instance role with permissions to access:
- **AWS Bedrock**: For Claude 3 model invocations
- **DynamoDB**: For accessing doctores, horarios_doctores, and user_sessions tables
- **AWS Lambda**: For invoking Lambda functions
- **CloudWatch Logs**: For application logging

## Files

- `iam-policy.json`: The permissions policy that grants access to AWS services
- `iam-trust-policy.json`: The trust policy that allows App Runner to assume the role

## Setup Instructions

### 1. Create the IAM Role

```bash
# Set your role name
ROLE_NAME="health-assistant-apprunner-role"

# Create the IAM role with the trust policy
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file://iam-trust-policy.json \
  --description "IAM role for Health Assistant API on App Runner"
```

### 2. Attach the Permissions Policy

You can either create a managed policy or attach an inline policy:

#### Option A: Create a Managed Policy (Recommended)

```bash
# Set your policy name
POLICY_NAME="health-assistant-apprunner-policy"

# Create the managed policy
aws iam create-policy \
  --policy-name $POLICY_NAME \
  --policy-document file://iam-policy.json \
  --description "Permissions for Health Assistant API on App Runner"

# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Attach the policy to the role
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/$POLICY_NAME
```

#### Option B: Attach as Inline Policy

```bash
# Attach the policy directly to the role
aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name health-assistant-permissions \
  --policy-document file://iam-policy.json
```

### 3. Get the Role ARN

```bash
# Get the role ARN (you'll need this for App Runner deployment)
aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text
```

Save this ARN - you'll need it when deploying to App Runner.

## Policy Details

### Bedrock Permissions

The policy grants access to:
- All Claude 3 foundation models (`anthropic.claude-3-*`)
- Inference profiles in the us-east-1 region

### DynamoDB Permissions

The policy grants Query, GetItem, PutItem, and UpdateItem access to:
- `doctores` table
- `horarios_doctores` table
- `user_sessions` table

It also grants Query access to any indexes on these tables.

### Lambda Permissions

The policy grants InvokeFunction access to all Lambda functions in the us-east-1 region within your account. You can restrict this further by specifying exact function ARNs if needed.

### CloudWatch Logs Permissions

The policy grants permissions to create log groups, streams, and put log events for App Runner services.

## Customization

### Restricting Lambda Access

To restrict Lambda access to specific functions, modify the Lambda statement in `iam-policy.json`:

```json
{
  "Sid": "LambdaInvokeFunction",
  "Effect": "Allow",
  "Action": ["lambda:InvokeFunction"],
  "Resource": [
    "arn:aws:lambda:us-east-1:297231942614:function:my-specific-function"
  ]
}
```

### Adding Additional Bedrock Models

To add access to other Bedrock models, add their ARNs to the Bedrock statement:

```json
{
  "Sid": "BedrockInvokeModel",
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
  "Resource": [
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-*",
    "arn:aws:bedrock:*::foundation-model/amazon.titan-*",
    "arn:aws:bedrock:us-east-1:297231942614:inference-profile/*"
  ]
}
```

### Multi-Region Support

If you need to deploy to multiple regions, update the region-specific ARNs in the policy. Consider using wildcards for the region:

```json
"Resource": [
  "arn:aws:dynamodb:*:297231942614:table/doctores"
]
```

## Verification

After creating the role, verify it has the correct permissions:

```bash
# List attached policies
aws iam list-attached-role-policies --role-name $ROLE_NAME

# Get inline policies
aws iam list-role-policies --role-name $ROLE_NAME

# View the trust policy
aws iam get-role --role-name $ROLE_NAME --query 'Role.AssumeRolePolicyDocument'
```

## Troubleshooting

### Access Denied Errors

If you encounter access denied errors:

1. Verify the role ARN is correctly configured in App Runner
2. Check that the resource ARNs in the policy match your actual resources
3. Ensure the trust policy allows `tasks.apprunner.amazonaws.com` to assume the role
4. Check CloudWatch Logs for detailed error messages

### Table Not Found Errors

If DynamoDB operations fail:

1. Verify the table names in the policy match your actual table names
2. Ensure the tables exist in the correct region
3. Check that the account ID in the ARNs is correct

## Security Best Practices

1. **Principle of Least Privilege**: Only grant the minimum permissions required
2. **Resource Scoping**: Use specific resource ARNs instead of wildcards when possible
3. **Regular Audits**: Periodically review and update the policy
4. **Separate Environments**: Use different roles for development, staging, and production
5. **Monitor Usage**: Use CloudTrail to monitor API calls made using this role

## Next Steps

After setting up the IAM role:

1. Note the Role ARN
2. Proceed to deploy the application to App Runner using the deployment script
3. Configure the Role ARN in your App Runner service configuration
