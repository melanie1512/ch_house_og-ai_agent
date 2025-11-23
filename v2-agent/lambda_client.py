"""
Lambda integration utility for invoking AWS Lambda functions.

This module provides functionality to invoke Lambda functions with both
synchronous and asynchronous invocation types, including error handling,
logging, and response parsing.
"""

import os
import json
import time
from typing import Dict, Any, Optional, Literal

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from logging_config import get_logger, log_error, log_aws_service_call

# Get logger for this module
logger = get_logger(__name__)


class LambdaInvocationError(Exception):
    """Custom exception for Lambda invocation errors."""
    pass


def get_lambda_client():
    """
    Create and return a boto3 Lambda client.
    
    Returns:
        boto3.client: Configured Lambda client
    """
    region = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
    return boto3.client('lambda', region_name=region)


def invoke_lambda(
    function_arn: str,
    payload: Dict[str, Any],
    invocation_type: Literal['RequestResponse', 'Event'] = 'RequestResponse'
) -> Dict[str, Any]:
    """
    Invoke an AWS Lambda function with the specified payload.
    
    Args:
        function_arn: ARN of the Lambda function to invoke. Can also be configured
                     via LAMBDA_FUNCTION_ARN environment variable.
        payload: Dictionary containing the payload to send to the Lambda function
        invocation_type: Type of invocation:
                        - 'RequestResponse' (default): Synchronous invocation
                        - 'Event': Asynchronous invocation
    
    Returns:
        Dict containing the response from the Lambda function:
        - For synchronous invocations: {'status_code': int, 'payload': dict}
        - For asynchronous invocations: {'status_code': int}
    
    Raises:
        LambdaInvocationError: If the Lambda invocation fails
        ValueError: If function_arn is not provided and not in environment
    
    Example:
        >>> result = invoke_lambda(
        ...     function_arn='arn:aws:lambda:us-east-1:123456789012:function:my-function',
        ...     payload={'key': 'value'},
        ...     invocation_type='RequestResponse'
        ... )
        >>> print(result['payload'])
    """
    # Validate invocation type
    if invocation_type not in ['RequestResponse', 'Event']:
        raise ValueError(
            f"Invalid invocation_type: {invocation_type}. "
            "Must be 'RequestResponse' or 'Event'"
        )
    
    # Get function ARN from parameter or environment variable
    if not function_arn:
        function_arn = os.getenv('LAMBDA_FUNCTION_ARN')
        if not function_arn:
            raise ValueError(
                "function_arn must be provided or set via LAMBDA_FUNCTION_ARN "
                "environment variable"
            )
    
    logger.info(
        f"Invoking Lambda function: {function_arn} "
        f"with invocation type: {invocation_type}"
    )
    
    try:
        # Get Lambda client
        lambda_client = get_lambda_client()
        
        # Invoke the Lambda function
        start_time = time.time()
        response = lambda_client.invoke(
            FunctionName=function_arn,
            InvocationType=invocation_type,
            Payload=json.dumps(payload)
        )
        duration_ms = (time.time() - start_time) * 1000
        
        status_code = response.get('StatusCode', 0)
        
        # Handle synchronous invocation
        if invocation_type == 'RequestResponse':
            # Read and parse the response payload
            response_payload = response.get('Payload')
            if response_payload:
                payload_str = response_payload.read()
                try:
                    parsed_payload = json.loads(payload_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Lambda response payload: {e}")
                    raise LambdaInvocationError(
                        f"Invalid JSON in Lambda response: {e}"
                    )
            else:
                parsed_payload = {}
            
            # Check for function errors
            function_error = response.get('FunctionError')
            if function_error:
                error_message = parsed_payload.get('errorMessage', 'Unknown error')
                
                # Log AWS service call failure
                log_aws_service_call(
                    logger,
                    service='lambda',
                    operation='invoke_function',
                    success=False,
                    duration_ms=duration_ms,
                    extra={
                        'function_arn': function_arn,
                        'invocation_type': invocation_type,
                        'function_error': function_error,
                        'error_message': error_message
                    }
                )
                
                raise LambdaInvocationError(
                    f"Lambda function error ({function_error}): {error_message}"
                )
            
            # Log successful AWS service call
            log_aws_service_call(
                logger,
                service='lambda',
                operation='invoke_function',
                success=True,
                duration_ms=duration_ms,
                extra={
                    'function_arn': function_arn,
                    'invocation_type': invocation_type,
                    'status_code': status_code
                }
            )
            
            return {
                'status_code': status_code,
                'payload': parsed_payload
            }
        
        # Handle asynchronous invocation
        else:  # invocation_type == 'Event'
            # Log successful async invocation
            log_aws_service_call(
                logger,
                service='lambda',
                operation='invoke_function',
                success=True,
                duration_ms=duration_ms,
                extra={
                    'function_arn': function_arn,
                    'invocation_type': invocation_type,
                    'status_code': status_code
                }
            )
            
            return {
                'status_code': status_code
            }
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        log_error(
            logger,
            e,
            "AWS ClientError invoking Lambda",
            extra={
                'function_arn': function_arn,
                'invocation_type': invocation_type,
                'error_code': error_code
            }
        )
        
        raise LambdaInvocationError(
            f"Failed to invoke Lambda function ({error_code}): {error_message}"
        )
    
    except BotoCoreError as e:
        log_error(
            logger,
            e,
            "BotoCoreError invoking Lambda",
            extra={
                'function_arn': function_arn,
                'invocation_type': invocation_type
            }
        )
        raise LambdaInvocationError(f"AWS SDK error: {str(e)}")
    
    except Exception as e:
        log_error(
            logger,
            e,
            "Unexpected error invoking Lambda",
            extra={
                'function_arn': function_arn,
                'invocation_type': invocation_type
            }
        )
        raise LambdaInvocationError(f"Unexpected error: {str(e)}")


def invoke_lambda_async(
    function_arn: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function for asynchronous Lambda invocation.
    
    Args:
        function_arn: ARN of the Lambda function to invoke
        payload: Dictionary containing the payload to send
    
    Returns:
        Dict containing the status code
    
    Example:
        >>> result = invoke_lambda_async(
        ...     function_arn='arn:aws:lambda:us-east-1:123456789012:function:my-function',
        ...     payload={'key': 'value'}
        ... )
    """
    return invoke_lambda(function_arn, payload, invocation_type='Event')


def invoke_lambda_sync(
    function_arn: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function for synchronous Lambda invocation.
    
    Args:
        function_arn: ARN of the Lambda function to invoke
        payload: Dictionary containing the payload to send
    
    Returns:
        Dict containing the status code and parsed payload
    
    Example:
        >>> result = invoke_lambda_sync(
        ...     function_arn='arn:aws:lambda:us-east-1:123456789012:function:my-function',
        ...     payload={'key': 'value'}
        ... )
        >>> print(result['payload'])
    """
    return invoke_lambda(function_arn, payload, invocation_type='RequestResponse')
