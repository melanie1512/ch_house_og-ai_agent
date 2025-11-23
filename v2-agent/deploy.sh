#!/bin/bash

# AWS App Runner Deployment Script
# Manages deployment of Health Assistant API to AWS App Runner

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_SERVICE_NAME="health-assistant-api"
DEFAULT_REGION="us-east-1"
DEFAULT_IAM_ROLE_NAME="apprunner-health-api-role"
DEFAULT_IAM_POLICY_NAME="apprunner-health-api-policy"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 <command> [options]

Commands:
    create      Create a new App Runner service
    update      Update an existing App Runner service
    delete      Delete an App Runner service
    status      Check status of an App Runner service

Options:
    --service-name <name>       Name of the App Runner service (default: $DEFAULT_SERVICE_NAME)
    --region <region>           AWS region (default: $DEFAULT_REGION)
    --role-name <name>          IAM role name (default: $DEFAULT_IAM_ROLE_NAME)
    --source-dir <path>         Source code directory (default: current directory)
    --help                      Show this help message

Examples:
    $0 create --service-name my-api --region us-west-2
    $0 update --service-name my-api
    $0 status --service-name my-api
    $0 delete --service-name my-api

EOF
}

# Function to validate AWS CLI is installed
validate_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
}

# Function to validate required files exist
validate_required_files() {
    local source_dir=$1
    
    if [ ! -f "$source_dir/apprunner.yaml" ]; then
        print_error "apprunner.yaml not found in $source_dir"
        exit 1
    fi
    
    if [ ! -f "$source_dir/requirements.txt" ]; then
        print_error "requirements.txt not found in $source_dir"
        exit 1
    fi
    
    if [ ! -f "$source_dir/main.py" ]; then
        print_error "main.py not found in $source_dir"
        exit 1
    fi
    
    print_success "All required files found"
}

# Function to get AWS account ID
get_account_id() {
    aws sts get-caller-identity --query Account --output text 2>/dev/null || {
        print_error "Failed to get AWS account ID. Check your AWS credentials."
        exit 1
    }
}

# Function to create or update IAM role
setup_iam_role() {
    local role_name=$1
    local policy_name=$2
    local region=$3
    local account_id=$4
    
    print_info "Setting up IAM role: $role_name" >&2
    
    # Check if role exists
    if aws iam get-role --role-name "$role_name" &>/dev/null; then
        print_info "IAM role already exists" >&2
    else
        print_info "Creating IAM role..." >&2
        
        # Create role with trust policy
        if [ ! -f "iam-trust-policy.json" ]; then
            print_error "iam-trust-policy.json not found" >&2
            exit 1
        fi
        
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file://iam-trust-policy.json \
            --description "IAM role for App Runner Health Assistant API" \
            &>/dev/null
        
        print_success "IAM role created" >&2
        sleep 5  # Wait for role to propagate
    fi
    
    # Update or create inline policy
    print_info "Updating IAM policy..." >&2
    
    if [ ! -f "iam-policy.json" ]; then
        print_error "iam-policy.json not found" >&2
        exit 1
    fi
    
    aws iam put-role-policy \
        --role-name "$role_name" \
        --policy-name "$policy_name" \
        --policy-document file://iam-policy.json \
        &>/dev/null
    
    print_success "IAM policy updated" >&2
    
    # Return role ARN (only to stdout)
    echo "arn:aws:iam::${account_id}:role/${role_name}"
}

# Function to load environment variables from .env file
load_env_vars() {
    local env_file=".env"
    
    if [ ! -f "$env_file" ]; then
        print_warning ".env file not found, using defaults"
        return
    fi
    
    # Export variables for use in script
    export $(grep -v '^#' "$env_file" | grep -v '^$' | xargs)
    print_success "Environment variables loaded from .env"
}

# Function to build environment variables JSON for App Runner
build_env_vars_json() {
    local region=$1
    local temp_file=$(mktemp)
    
    # Start JSON object (not array)
    echo '{' > "$temp_file"
    
    # Add required environment variables
    cat >> "$temp_file" << EOF
  "AWS_REGION": "$region",
  "BEDROCK_REGION": "$region",
  "API_HOST": "0.0.0.0",
  "API_PORT": "8000"
EOF
    
    # Add BEDROCK_MODEL if set
    if [ -n "$BEDROCK_MODEL" ]; then
        cat >> "$temp_file" << EOF
,
  "BEDROCK_MODEL": "$BEDROCK_MODEL"
EOF
    fi
    
    # Add SESSION_TABLE_NAME if set, otherwise use default
    local session_table="${SESSION_TABLE_NAME:-user_sessions}"
    cat >> "$temp_file" << EOF
,
  "SESSION_TABLE_NAME": "$session_table"
EOF
    
    # Add LOG_LEVEL if set, otherwise use INFO
    local log_level="${LOG_LEVEL:-INFO}"
    cat >> "$temp_file" << EOF
,
  "LOG_LEVEL": "$log_level"
EOF
    
    # Add ENVIRONMENT if set, otherwise use production
    local environment="${ENVIRONMENT:-production}"
    cat >> "$temp_file" << EOF
,
  "ENVIRONMENT": "$environment"
EOF
    
    # Add ALLOWED_ORIGINS if set
    if [ -n "$ALLOWED_ORIGINS" ]; then
        cat >> "$temp_file" << EOF
,
  "ALLOWED_ORIGINS": "$ALLOWED_ORIGINS"
EOF
    fi
    
    # Add LAMBDA_FUNCTION_ARN if set
    if [ -n "$LAMBDA_FUNCTION_ARN" ]; then
        cat >> "$temp_file" << EOF
,
  "LAMBDA_FUNCTION_ARN": "$LAMBDA_FUNCTION_ARN"
EOF
    fi
    
    # Close JSON object
    echo '}' >> "$temp_file"
    
    echo "$temp_file"
}

# Function to get or create GitHub connection
get_github_connection() {
    local region=$1
    
    # List existing connections
    local connection_arn=$(aws apprunner list-connections \
        --region "$region" \
        --query "ConnectionSummaryList[?Status=='AVAILABLE'].ConnectionArn | [0]" \
        --output text 2>/dev/null)
    
    if [ "$connection_arn" != "None" ] && [ -n "$connection_arn" ]; then
        echo "$connection_arn"
        return 0
    fi
    
    # No available connection found
    print_error "No GitHub connection found. Please create one first:"
    print_info "1. Go to AWS Console > App Runner > GitHub connections"
    print_info "2. Create a new connection and authorize GitHub"
    print_info "3. Or run: aws apprunner create-connection --connection-name github-connection --provider-type GITHUB --region $region"
    exit 1
}

# Function to create App Runner service
create_service() {
    local service_name=$1
    local region=$2
    local role_arn=$3
    local source_dir=$4
    
    print_info "Creating App Runner service: $service_name"
    
    # Check if service already exists
    if aws apprunner list-services --region "$region" --query "ServiceSummaryList[?ServiceName=='$service_name'].ServiceArn" --output text 2>/dev/null | grep -q .; then
        print_error "Service $service_name already exists. Use 'update' command instead."
        exit 1
    fi
    
    # Get GitHub connection
    print_info "Getting GitHub connection..."
    local connection_arn=$(get_github_connection "$region")
    print_success "Using connection: $connection_arn"
    
    # Build environment variables
    local env_vars_file=$(build_env_vars_json "$region")
    
    # Create service configuration
    print_info "Deploying service from GitHub repository..."
    print_info "Repository: https://github.com/melanie1512/ch_house_og-ai_agent.git"
    print_info "Branch: main"
    print_info "Source directory: v2-agent"
    print_info "Using API configuration with environment variables"
    
    # Create the service using AWS CLI
    local service_arn=$(aws apprunner create-service \
        --service-name "$service_name" \
        --region "$region" \
        --source-configuration "{
            \"AuthenticationConfiguration\": {
                \"ConnectionArn\": \"$connection_arn\"
            },
            \"CodeRepository\": {
                \"RepositoryUrl\": \"https://github.com/melanie1512/ch_house_og-ai_agent\",
                \"SourceCodeVersion\": {
                    \"Type\": \"BRANCH\",
                    \"Value\": \"main\"
                },
                \"SourceDirectory\": \"v2-agent\",
                \"CodeConfiguration\": {
                    \"ConfigurationSource\": \"API\",
                    \"CodeConfigurationValues\": {
                        \"Runtime\": \"PYTHON_311\",
                        \"BuildCommand\": \"python3 -m pip install --upgrade pip && python3 -m pip install -r requirements.txt && chmod +x start.sh\",
                        \"StartCommand\": \"./start.sh\",
                        \"Port\": \"8000\",
                        \"RuntimeEnvironmentVariables\": $(cat "$env_vars_file")
                    }
                }
            }
        }" \
        --instance-configuration "{
            \"Cpu\": \"1 vCPU\",
            \"Memory\": \"2 GB\",
            \"InstanceRoleArn\": \"$role_arn\"
        }" \
        --health-check-configuration "{
            \"Protocol\": \"HTTP\",
            \"Path\": \"/docs\",
            \"Interval\": 10,
            \"Timeout\": 5,
            \"HealthyThreshold\": 1,
            \"UnhealthyThreshold\": 5
        }" \
        --query 'Service.ServiceArn' \
        --output text 2>&1)
    
    # Clean up temp file
    rm -f "$env_vars_file"
    
    if echo "$service_arn" | grep -q "^arn:aws:apprunner"; then
        print_success "Service created successfully"
        print_info "Service ARN: $service_arn"
        print_info "Waiting for service to become available..."
        print_info "This may take 5-10 minutes for the first deployment..."
        
        # Wait for service to be running
        aws apprunner wait service-running \
            --service-arn "$service_arn" \
            --region "$region" 2>/dev/null || true
        
        # Get service URL
        local service_url=$(aws apprunner describe-service \
            --service-arn "$service_arn" \
            --region "$region" \
            --query 'Service.ServiceUrl' \
            --output text 2>/dev/null)
        
        print_success "Service is running!"
        print_info "Service URL: https://$service_url"
    else
        print_error "Failed to create service"
        print_error "$service_arn"
        exit 1
    fi
}

# Function to update App Runner service
update_service() {
    local service_name=$1
    local region=$2
    local role_arn=$3
    
    print_info "Updating App Runner service: $service_name"
    
    # Get service ARN
    local service_arn=$(aws apprunner list-services \
        --region "$region" \
        --query "ServiceSummaryList[?ServiceName=='$service_name'].ServiceArn" \
        --output text 2>/dev/null)
    
    if [ -z "$service_arn" ]; then
        print_error "Service $service_name not found. Use 'create' command instead."
        exit 1
    fi
    
    print_info "Found service: $service_arn"
    
    # Build environment variables
    local env_vars_file=$(build_env_vars_json "$region")
    
    # Update the service
    print_info "Updating service configuration..."
    
    aws apprunner update-service \
        --service-arn "$service_arn" \
        --region "$region" \
        --source-configuration "{
            \"CodeRepository\": {
                \"CodeConfiguration\": {
                    \"ConfigurationSource\": \"API\",
                    \"CodeConfigurationValues\": {
                        \"RuntimeEnvironmentVariables\": $(cat "$env_vars_file")
                    }
                }
            }
        }" \
        --instance-configuration "{
            \"InstanceRoleArn\": \"$role_arn\"
        }" \
        --health-check-configuration "{
            \"Protocol\": \"HTTP\",
            \"Path\": \"/docs\",
            \"Interval\": 10,
            \"Timeout\": 5,
            \"HealthyThreshold\": 1,
            \"UnhealthyThreshold\": 5
        }" \
        &>/dev/null
    
    # Clean up temp file
    rm -f "$env_vars_file"
    
    if [ $? -eq 0 ]; then
        print_success "Service update initiated"
        print_info "Waiting for service to complete update..."
        
        # Wait for service to be running
        aws apprunner wait service-running \
            --service-arn "$service_arn" \
            --region "$region" 2>/dev/null || true
        
        print_success "Service updated successfully"
    else
        print_error "Failed to update service"
        exit 1
    fi
}

# Function to delete App Runner service
delete_service() {
    local service_name=$1
    local region=$2
    
    print_warning "Deleting App Runner service: $service_name"
    
    # Get service ARN
    local service_arn=$(aws apprunner list-services \
        --region "$region" \
        --query "ServiceSummaryList[?ServiceName=='$service_name'].ServiceArn" \
        --output text 2>/dev/null)
    
    if [ -z "$service_arn" ]; then
        print_error "Service $service_name not found"
        exit 1
    fi
    
    # Confirm deletion
    read -p "Are you sure you want to delete $service_name? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Deletion cancelled"
        exit 0
    fi
    
    print_info "Deleting service..."
    
    aws apprunner delete-service \
        --service-arn "$service_arn" \
        --region "$region" \
        &>/dev/null
    
    if [ $? -eq 0 ]; then
        print_success "Service deletion initiated"
        print_info "Service will be deleted in a few minutes"
    else
        print_error "Failed to delete service"
        exit 1
    fi
}

# Function to check service status
check_status() {
    local service_name=$1
    local region=$2
    
    print_info "Checking status of: $service_name"
    
    # Get service ARN
    local service_arn=$(aws apprunner list-services \
        --region "$region" \
        --query "ServiceSummaryList[?ServiceName=='$service_name'].ServiceArn" \
        --output text 2>/dev/null)
    
    if [ -z "$service_arn" ]; then
        print_error "Service $service_name not found"
        exit 1
    fi
    
    # Get service details
    local service_info=$(aws apprunner describe-service \
        --service-arn "$service_arn" \
        --region "$region" \
        --output json 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        print_error "Failed to get service status"
        exit 1
    fi
    
    # Parse and display status
    local status=$(echo "$service_info" | grep -o '"Status": "[^"]*"' | head -1 | cut -d'"' -f4)
    local service_url=$(echo "$service_info" | grep -o '"ServiceUrl": "[^"]*"' | cut -d'"' -f4)
    local created_at=$(echo "$service_info" | grep -o '"CreatedAt": "[^"]*"' | cut -d'"' -f4)
    
    echo ""
    echo "Service Status Report"
    echo "===================="
    echo "Service Name: $service_name"
    echo "Service ARN: $service_arn"
    echo "Status: $status"
    echo "Service URL: https://$service_url"
    echo "Created At: $created_at"
    echo "Region: $region"
    echo ""
    
    if [ "$status" == "RUNNING" ]; then
        print_success "Service is healthy and running"
    elif [ "$status" == "CREATE_FAILED" ] || [ "$status" == "UPDATE_FAILED" ]; then
        print_error "Service is in failed state"
    else
        print_warning "Service is in transitional state: $status"
    fi
}

# Main script logic
main() {
    # Parse command
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    # Check for help flag first
    if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
        show_usage
        exit 0
    fi
    
    local command=$1
    shift
    
    # Parse options
    local service_name=$DEFAULT_SERVICE_NAME
    local region=$DEFAULT_REGION
    local role_name=$DEFAULT_IAM_ROLE_NAME
    local policy_name=$DEFAULT_IAM_POLICY_NAME
    local source_dir="."
    
    while [ $# -gt 0 ]; do
        case $1 in
            --service-name)
                service_name=$2
                shift 2
                ;;
            --region)
                region=$2
                shift 2
                ;;
            --role-name)
                role_name=$2
                shift 2
                ;;
            --source-dir)
                source_dir=$2
                shift 2
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Validate AWS CLI
    validate_aws_cli
    
    # Get AWS account ID
    local account_id=$(get_account_id)
    print_info "AWS Account ID: $account_id"
    print_info "Region: $region"
    
    # Load environment variables
    load_env_vars
    
    # Execute command
    case $command in
        create)
            validate_required_files "$source_dir"
            local role_arn=$(setup_iam_role "$role_name" "$policy_name" "$region" "$account_id")
            print_info "IAM Role ARN: $role_arn"
            create_service "$service_name" "$region" "$role_arn" "$source_dir"
            ;;
        update)
            local role_arn=$(setup_iam_role "$role_name" "$policy_name" "$region" "$account_id")
            print_info "IAM Role ARN: $role_arn"
            update_service "$service_name" "$region" "$role_arn"
            ;;
        delete)
            delete_service "$service_name" "$region"
            ;;
        status)
            check_status "$service_name" "$region"
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
