#!/usr/bin/env python3
"""
DynamoDB Table Setup Script

Creates all required DynamoDB tables for the Health Assistant API:
- doctores: Stores doctor information with specialty indexing
- horarios_doctores: Stores doctor schedules
- user_sessions: Stores user session data with TTL

All tables use PAY_PER_REQUEST billing mode for cost efficiency.
"""

import boto3
import sys
import os
from botocore.exceptions import ClientError
from typing import List, Dict, Any

from logging_config import setup_logging, get_logger, log_error

# Initialize logging
setup_logging()
logger = get_logger(__name__)


def get_dynamodb_client(region: str = None):
    """
    Get DynamoDB client for the specified region.
    
    Args:
        region: AWS region (defaults to AWS_REGION env var or us-east-1)
    
    Returns:
        boto3 DynamoDB client
    """
    if region is None:
        region = os.getenv('AWS_REGION', 'us-east-1')
    
    return boto3.client('dynamodb', region_name=region)


def table_exists(client, table_name: str) -> bool:
    """
    Check if a DynamoDB table exists.
    
    Args:
        client: boto3 DynamoDB client
        table_name: Name of the table to check
    
    Returns:
        True if table exists, False otherwise
    """
    try:
        client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return False
        raise


def create_doctores_table(client, table_name: str = 'doctores') -> Dict[str, Any]:
    """
    Create the doctores table with specialty index.
    
    Schema:
    - Partition Key: doctor_id (S)
    - GSI: especialidad-index on especialidad attribute
    
    Args:
        client: boto3 DynamoDB client
        table_name: Name of the table (default: doctores)
    
    Returns:
        Response from create_table API call
    """
    logger.info(f"Creating table: {table_name}")
    print(f"Creating table: {table_name}")
    
    response = client.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': 'doctor_id',
                'KeyType': 'HASH'  # Partition key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'doctor_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'especialidad',
                'AttributeType': 'S'
            }
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'especialidad-index',
                'KeySchema': [
                    {
                        'AttributeName': 'especialidad',
                        'KeyType': 'HASH'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
            }
        ],
        BillingMode='PAY_PER_REQUEST',
        Tags=[
            {
                'Key': 'Application',
                'Value': 'HealthAssistantAPI'
            },
            {
                'Key': 'Environment',
                'Value': os.getenv('ENVIRONMENT', 'development')
            }
        ]
    )
    
    logger.info(f"Table {table_name} created successfully")
    print(f"✓ Table {table_name} created successfully")
    return response


def create_horarios_doctores_table(client, table_name: str = 'horarios_doctores') -> Dict[str, Any]:
    """
    Create the horarios_doctores table.
    
    Schema:
    - Partition Key: doctor_id (S)
    - Sort Key: fecha_hora (S) - ISO format datetime string
    
    Args:
        client: boto3 DynamoDB client
        table_name: Name of the table (default: horarios_doctores)
    
    Returns:
        Response from create_table API call
    """
    print(f"Creating table: {table_name}")
    
    response = client.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': 'doctor_id',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'fecha_hora',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'doctor_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'fecha_hora',
                'AttributeType': 'S'
            }
        ],
        BillingMode='PAY_PER_REQUEST',
        Tags=[
            {
                'Key': 'Application',
                'Value': 'HealthAssistantAPI'
            },
            {
                'Key': 'Environment',
                'Value': os.getenv('ENVIRONMENT', 'development')
            }
        ]
    )
    
    print(f"✓ Table {table_name} created successfully")
    return response


def create_user_sessions_table(client, table_name: str = 'user_sessions') -> Dict[str, Any]:
    """
    Create the user_sessions table with TTL enabled.
    
    Schema:
    - Partition Key: user_id (S)
    - TTL Attribute: ttl (N) - Unix timestamp
    
    Args:
        client: boto3 DynamoDB client
        table_name: Name of the table (default: user_sessions)
    
    Returns:
        Response from create_table API call
    """
    print(f"Creating table: {table_name}")
    
    response = client.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': 'user_id',
                'KeyType': 'HASH'  # Partition key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'user_id',
                'AttributeType': 'S'
            }
        ],
        BillingMode='PAY_PER_REQUEST',
        Tags=[
            {
                'Key': 'Application',
                'Value': 'HealthAssistantAPI'
            },
            {
                'Key': 'Environment',
                'Value': os.getenv('ENVIRONMENT', 'development')
            }
        ]
    )
    
    print(f"✓ Table {table_name} created successfully")
    
    # Enable TTL on the ttl attribute
    print(f"Enabling TTL on {table_name}...")
    client.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={
            'Enabled': True,
            'AttributeName': 'ttl'
        }
    )
    print(f"✓ TTL enabled on {table_name}")
    
    return response


def wait_for_table_active(client, table_name: str, max_attempts: int = 30):
    """
    Wait for a table to become active.
    
    Args:
        client: boto3 DynamoDB client
        table_name: Name of the table
        max_attempts: Maximum number of attempts (default: 30)
    """
    print(f"Waiting for {table_name} to become active...")
    waiter = client.get_waiter('table_exists')
    waiter.wait(
        TableName=table_name,
        WaiterConfig={
            'Delay': 2,
            'MaxAttempts': max_attempts
        }
    )
    print(f"✓ Table {table_name} is active")


def validate_required_tables(client, required_tables: List[str]) -> Dict[str, bool]:
    """
    Validate that all required tables exist.
    
    Args:
        client: boto3 DynamoDB client
        required_tables: List of required table names
    
    Returns:
        Dictionary mapping table names to existence status
    """
    results = {}
    for table_name in required_tables:
        exists = table_exists(client, table_name)
        results[table_name] = exists
        status = "✓ EXISTS" if exists else "✗ MISSING"
        print(f"{status}: {table_name}")
    
    return results


def setup_all_tables(region: str = None, skip_existing: bool = True):
    """
    Create all required DynamoDB tables.
    
    Args:
        region: AWS region (defaults to AWS_REGION env var or us-east-1)
        skip_existing: If True, skip tables that already exist (default: True)
    """
    client = get_dynamodb_client(region)
    
    tables_to_create = [
        ('doctores', create_doctores_table),
        ('horarios_doctores', create_horarios_doctores_table),
        ('user_sessions', create_user_sessions_table)
    ]
    
    print("=" * 60)
    print("DynamoDB Table Setup")
    print("=" * 60)
    print(f"Region: {region or os.getenv('AWS_REGION', 'us-east-1')}")
    print(f"Skip existing: {skip_existing}")
    print()
    
    created_tables = []
    skipped_tables = []
    
    for table_name, create_func in tables_to_create:
        if skip_existing and table_exists(client, table_name):
            print(f"⊘ Table {table_name} already exists, skipping...")
            skipped_tables.append(table_name)
            continue
        
        try:
            create_func(client, table_name)
            created_tables.append(table_name)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"⊘ Table {table_name} already exists")
                skipped_tables.append(table_name)
            else:
                print(f"✗ Error creating table {table_name}: {str(e)}")
                raise
    
    # Wait for all created tables to become active
    if created_tables:
        print()
        print("Waiting for tables to become active...")
        for table_name in created_tables:
            wait_for_table_active(client, table_name)
    
    print()
    print("=" * 60)
    print("Setup Summary")
    print("=" * 60)
    print(f"Created: {len(created_tables)} table(s)")
    if created_tables:
        for table in created_tables:
            print(f"  ✓ {table}")
    
    print(f"Skipped: {len(skipped_tables)} table(s)")
    if skipped_tables:
        for table in skipped_tables:
            print(f"  ⊘ {table}")
    
    print()
    print("✓ Setup complete!")


def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create DynamoDB tables for Health Assistant API'
    )
    parser.add_argument(
        '--region',
        help='AWS region (default: AWS_REGION env var or us-east-1)',
        default=None
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Attempt to create tables even if they exist (will fail if they exist)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Only validate that required tables exist, do not create'
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting DynamoDB table setup script")
    logger.info(f"Region: {args.region or os.getenv('AWS_REGION', 'us-east-1')}")
    logger.info(f"Validate mode: {args.validate}")
    logger.info(f"Force mode: {args.force}")
    
    try:
        if args.validate:
            # Validation mode
            client = get_dynamodb_client(args.region)
            required_tables = ['doctores', 'horarios_doctores', 'user_sessions']
            
            print("=" * 60)
            print("Validating Required Tables")
            print("=" * 60)
            print(f"Region: {args.region or os.getenv('AWS_REGION', 'us-east-1')}")
            print()
            
            results = validate_required_tables(client, required_tables)
            
            print()
            all_exist = all(results.values())
            if all_exist:
                print("✓ All required tables exist")
                sys.exit(0)
            else:
                missing = [name for name, exists in results.items() if not exists]
                print(f"✗ Missing tables: {', '.join(missing)}")
                print()
                print("Run without --validate to create missing tables")
                sys.exit(1)
        else:
            # Creation mode
            setup_all_tables(region=args.region, skip_existing=not args.force)
            logger.info("Table setup completed successfully")
            sys.exit(0)
    
    except Exception as e:
        log_error(logger, e, "Failed to setup DynamoDB tables")
        print(f"\n✗ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
