# Logging Configuration

This document describes the logging configuration for the Health Assistant API.

## Overview

The application uses structured JSON logging optimized for CloudWatch Logs. All logs include:
- Timestamp (ISO 8601 format with UTC timezone)
- Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Logger name (module name)
- Message
- Module, function, and line number
- Exception details (when applicable)
- Request context (user_id, request_id, endpoint when available)

## Configuration

### Environment Variables

- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
- `ENVIRONMENT`: Set environment (development, production). Default: development
  - In development: Human-readable console output
  - In production: Structured JSON output for CloudWatch

### Example Configuration

```bash
# Development
export LOG_LEVEL=DEBUG
export ENVIRONMENT=development

# Production
export LOG_LEVEL=INFO
export ENVIRONMENT=production
```

## Usage

### Basic Logging

```python
from logging_config import get_logger

logger = get_logger(__name__)

logger.info("Processing request")
logger.warning("Rate limit approaching")
logger.error("Failed to connect to database")
```

### Request-Scoped Logging

```python
from logging_config import get_request_logger

# Create logger with request context
logger = get_request_logger(
    __name__,
    user_id="user123",
    request_id="req-456",
    endpoint="/triage/interpret"
)

# All logs will include the context
logger.info("Processing triage request")  # Includes user_id, request_id, endpoint
```

### Error Logging

```python
from logging_config import log_error

try:
    risky_operation()
except Exception as e:
    log_error(
        logger,
        e,
        "Failed to process request",
        extra={"user_id": "123", "operation": "triage"}
    )
```

### AWS Service Call Logging

```python
from logging_config import log_aws_service_call
import time

start_time = time.time()
try:
    response = bedrock_client.invoke_model(...)
    duration_ms = (time.time() - start_time) * 1000
    
    log_aws_service_call(
        logger,
        service='bedrock',
        operation='invoke_model',
        success=True,
        duration_ms=duration_ms,
        extra={'model_id': 'claude-3'}
    )
except Exception as e:
    duration_ms = (time.time() - start_time) * 1000
    log_aws_service_call(
        logger,
        service='bedrock',
        operation='invoke_model',
        success=False,
        duration_ms=duration_ms,
        error=e
    )
```

### Request Lifecycle Logging

```python
from logging_config import log_request_start, log_request_end
import time

# Log request start
log_request_start(
    logger,
    endpoint="/doctors/interpret",
    user_id="user123",
    extra={"method": "POST"}
)

start_time = time.time()
# ... process request ...
duration_ms = (time.time() - start_time) * 1000

# Log request end
log_request_end(
    logger,
    endpoint="/doctors/interpret",
    status_code=200,
    duration_ms=duration_ms,
    user_id="user123"
)
```

## Log Levels

Use appropriate log levels for different scenarios:

- **DEBUG**: Detailed diagnostic information (disabled in production)
- **INFO**: General informational messages (request processing, successful operations)
- **WARNING**: Warning messages (rate limits, deprecated features, recoverable errors)
- **ERROR**: Error messages (failed operations, exceptions)
- **CRITICAL**: Critical errors (system failures, data corruption)

## CloudWatch Logs Integration

### Automatic Integration

When deployed to AWS App Runner, logs are automatically sent to CloudWatch Logs:
- Log Group: `/aws/apprunner/<service-name>/<service-id>/application`
- Structured JSON format enables CloudWatch Logs Insights queries

### Example CloudWatch Logs Insights Queries

**Find all errors for a specific user:**
```
fields @timestamp, message, error_type, error_message
| filter user_id = "user123" and level = "ERROR"
| sort @timestamp desc
```

**Track request latency:**
```
fields @timestamp, endpoint, duration_ms, status_code
| filter event = "request_end"
| stats avg(duration_ms), max(duration_ms), count() by endpoint
```

**Monitor AWS service calls:**
```
fields @timestamp, aws_service, operation, success, duration_ms
| filter aws_service = "bedrock"
| stats avg(duration_ms), count() by operation, success
```

**Find slow requests:**
```
fields @timestamp, endpoint, duration_ms, user_id
| filter event = "request_end" and duration_ms > 1000
| sort duration_ms desc
```

## Structured Log Format

Example structured log entry:

```json
{
  "timestamp": "2025-11-23T05:19:30.337037Z",
  "level": "INFO",
  "logger": "main",
  "message": "Processing triage request",
  "module": "main",
  "function": "triage_interpret",
  "line": 123,
  "user_id": "user123",
  "request_id": "req-456",
  "endpoint": "/triage/interpret",
  "extra_fields": {
    "capa": 2,
    "accion": "solicitar_medico_a_domicilio"
  }
}
```

Example error log entry:

```json
{
  "timestamp": "2025-11-23T05:19:30.337037Z",
  "level": "ERROR",
  "logger": "lambda_client",
  "message": "AWS ClientError invoking Lambda: AccessDeniedException",
  "module": "lambda_client",
  "function": "invoke_lambda",
  "line": 234,
  "exception": {
    "type": "ClientError",
    "message": "User is not authorized to perform: lambda:InvokeFunction",
    "traceback": ["...", "..."]
  },
  "extra_fields": {
    "function_arn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
    "invocation_type": "RequestResponse",
    "error_code": "AccessDeniedException"
  }
}
```

## Best Practices

1. **Use appropriate log levels**: Don't log everything as INFO or ERROR
2. **Include context**: Add user_id, request_id, and other relevant context
3. **Log at boundaries**: Log at API entry/exit points and external service calls
4. **Don't log sensitive data**: Never log passwords, tokens, or PII
5. **Use structured fields**: Add extra context as structured fields, not in message strings
6. **Log exceptions properly**: Use `log_error()` to capture full exception details
7. **Monitor performance**: Log timing information for slow operations
8. **Keep messages concise**: Log messages should be clear and actionable

## Troubleshooting

### Logs not appearing in CloudWatch

1. Check IAM role has CloudWatch Logs permissions:
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "logs:CreateLogGroup",
       "logs:CreateLogStream",
       "logs:PutLogEvents"
     ],
     "Resource": "*"
   }
   ```

2. Verify App Runner service is configured to send logs to CloudWatch

3. Check log level is not set too high (e.g., ERROR when you want INFO logs)

### Logs are not structured

1. Verify `ENVIRONMENT` is set to "production"
2. Check that `logging_config.setup_logging()` is called before any logging

### Missing context in logs

1. Use `get_request_logger()` instead of `get_logger()` for request-scoped logging
2. Pass `extra` parameter with additional context fields
3. Ensure middleware is properly configured to add request context

## Requirements Validation

This logging implementation satisfies:

- **Requirement 9.1**: CloudWatch Logs are enabled through App Runner's automatic integration
- **Requirement 9.3**: Errors are logged with appropriate severity levels using structured logging

All logs include:
- Timestamp
- Severity level
- Module/function/line information
- Exception details (when applicable)
- Request context (when available)
- Structured fields for CloudWatch Logs Insights queries
