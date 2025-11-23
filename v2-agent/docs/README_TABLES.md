# DynamoDB Table Setup

This document describes how to set up the required DynamoDB tables for the Health Assistant API.

## Required Tables

The application requires three DynamoDB tables:

1. **doctores** - Stores doctor information with specialty indexing
2. **horarios_doctores** - Stores doctor schedules
3. **user_sessions** - Stores user session data with TTL

## Table Schemas

### doctores
- **Partition Key**: `doctor_id` (String)
- **Global Secondary Index**: `especialidad-index` on `especialidad` attribute
- **Billing Mode**: PAY_PER_REQUEST

### horarios_doctores
- **Partition Key**: `doctor_id` (String)
- **Sort Key**: `fecha_hora` (String) - ISO format datetime
- **Billing Mode**: PAY_PER_REQUEST

### user_sessions
- **Partition Key**: `user_id` (String)
- **TTL Attribute**: `ttl` (Number) - Unix timestamp
- **Billing Mode**: PAY_PER_REQUEST

## Usage

### Create All Tables

To create all required tables:

```bash
cd v2-agent
python3 setup_tables.py
```

By default, the script will skip tables that already exist.

### Validate Tables Exist

To check if all required tables exist without creating them:

```bash
python3 setup_tables.py --validate
```

This will exit with code 0 if all tables exist, or code 1 if any are missing.

### Force Recreation

To attempt to create tables even if they exist (will fail if they exist):

```bash
python3 setup_tables.py --force
```

### Specify Region

To create tables in a specific AWS region:

```bash
python3 setup_tables.py --region us-west-2
```

If not specified, the script uses the `AWS_REGION` environment variable or defaults to `us-east-1`.

## Prerequisites

- AWS credentials configured (via environment variables, AWS CLI, or IAM role)
- Permissions to create DynamoDB tables and enable TTL
- Python 3.9 or higher
- boto3 library installed

## IAM Permissions Required

The AWS credentials used must have the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:TagResource"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/*"
    }
  ]
}
```

## Testing

Unit tests for the table setup script are available:

```bash
python3 -m pytest tests/test_setup_tables.py -v
```

## Troubleshooting

### "Unable to locate credentials"

Ensure AWS credentials are configured. You can:
- Set environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Configure AWS CLI: `aws configure`
- Use IAM roles (when running on EC2/ECS/Lambda)

### "ResourceInUseException"

The table already exists. Use `--validate` to check table status, or remove the table first if you need to recreate it.

### "AccessDeniedException"

Your AWS credentials don't have sufficient permissions. Ensure the IAM user/role has the required DynamoDB permissions listed above.

## Notes

- All tables use PAY_PER_REQUEST billing mode for cost efficiency with variable workloads
- The `user_sessions` table has TTL enabled to automatically expire old sessions
- Tables are tagged with `Application: HealthAssistantAPI` and `Environment` (from env var)
