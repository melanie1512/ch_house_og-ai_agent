"""
Logging configuration and utilities for the Health Assistant API.

This module provides structured logging with appropriate severity levels,
CloudWatch Logs integration, and consistent formatting across the application.

Requirements: 9.1, 9.3
"""

import logging
import sys
import json
import os
from typing import Any, Dict, Optional
from datetime import datetime
import traceback


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs for CloudWatch.
    
    This format is optimized for CloudWatch Logs Insights queries and
    provides consistent structure across all log entries.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: LogRecord to format
            
        Returns:
            JSON string with structured log data
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Add user_id if present (for request tracking)
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        # Add request_id if present (for request tracking)
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        # Add endpoint if present
        if hasattr(record, 'endpoint'):
            log_data['endpoint'] = record.endpoint
        
        return json.dumps(log_data)


class HumanReadableFormatter(logging.Formatter):
    """
    Formatter for human-readable console output during development.
    """
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(
    log_level: Optional[str] = None,
    enable_cloudwatch: bool = True,
    structured: bool = True
) -> None:
    """
    Configure application-wide logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  Defaults to LOG_LEVEL env var or INFO.
        enable_cloudwatch: Whether to enable CloudWatch-optimized logging.
                          Defaults to True in production.
        structured: Whether to use structured JSON logging.
                   Defaults to True in production, False in development.
    
    Requirements: 9.1
    """
    # Determine log level
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Determine environment
    environment = os.getenv('ENVIRONMENT', 'development').lower()
    
    # Use structured logging in production, human-readable in development
    if structured is None:
        structured = environment == 'production'
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Set formatter based on environment
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Log startup message
    root_logger.info(
        f"Logging configured: level={log_level}, "
        f"environment={environment}, structured={structured}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the logger (typically __name__)
        
    Returns:
        Configured logger instance
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request")
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter that adds contextual information to log records.
    
    This adapter allows adding request-specific context (user_id, request_id, etc.)
    to all log messages within a request scope.
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """
        Process log message and add extra context.
        
        Args:
            msg: Log message
            kwargs: Additional keyword arguments
            
        Returns:
            Tuple of (message, kwargs) with added context
        """
        # Add extra fields from adapter context
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        # Merge adapter context into extra fields
        for key, value in self.extra.items():
            if key not in kwargs['extra']:
                kwargs['extra'][key] = value
        
        return msg, kwargs


def get_request_logger(
    name: str,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None
) -> LoggerAdapter:
    """
    Get a logger with request-specific context.
    
    Args:
        name: Logger name
        user_id: User ID for the request
        request_id: Unique request identifier
        endpoint: API endpoint being called
        
    Returns:
        LoggerAdapter with request context
        
    Example:
        >>> logger = get_request_logger(__name__, user_id="user123", endpoint="/triage")
        >>> logger.info("Processing triage request")
    """
    base_logger = get_logger(name)
    
    context = {}
    if user_id:
        context['user_id'] = user_id
    if request_id:
        context['request_id'] = request_id
    if endpoint:
        context['endpoint'] = endpoint
    
    return LoggerAdapter(base_logger, context)


def log_error(
    logger: logging.Logger,
    error: Exception,
    message: str,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error with full exception details and context.
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        message: Human-readable error message
        extra: Additional context to include in log
        
    Requirements: 9.3
        
    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_error(logger, e, "Failed to process request", {"user_id": "123"})
    """
    log_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
    }
    
    if extra:
        log_data.update(extra)
    
    logger.error(
        f"{message}: {str(error)}",
        exc_info=True,
        extra={'extra_fields': log_data}
    )


def log_aws_service_call(
    logger: logging.Logger,
    service: str,
    operation: str,
    success: bool,
    duration_ms: Optional[float] = None,
    error: Optional[Exception] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log AWS service API calls with timing and status.
    
    Args:
        logger: Logger instance
        service: AWS service name (e.g., 'bedrock', 'dynamodb', 'lambda')
        operation: Operation name (e.g., 'invoke_model', 'query', 'invoke_function')
        success: Whether the call succeeded
        duration_ms: Call duration in milliseconds
        error: Exception if call failed
        extra: Additional context
        
    Example:
        >>> log_aws_service_call(
        ...     logger, 'bedrock', 'invoke_model', True, 
        ...     duration_ms=250.5, extra={'model_id': 'claude-3'}
        ... )
    """
    log_data = {
        'aws_service': service,
        'operation': operation,
        'success': success,
    }
    
    if duration_ms is not None:
        log_data['duration_ms'] = duration_ms
    
    if error:
        log_data['error_type'] = type(error).__name__
        log_data['error_message'] = str(error)
    
    if extra:
        log_data.update(extra)
    
    level = logging.INFO if success else logging.ERROR
    message = f"AWS {service}.{operation}: {'success' if success else 'failed'}"
    
    if duration_ms is not None:
        message += f" ({duration_ms:.2f}ms)"
    
    logger.log(
        level,
        message,
        extra={'extra_fields': log_data},
        exc_info=error if error else None
    )


def log_request_start(
    logger: logging.Logger,
    endpoint: str,
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log the start of an API request.
    
    Args:
        logger: Logger instance
        endpoint: API endpoint
        user_id: User making the request
        extra: Additional context
    """
    log_data = {
        'endpoint': endpoint,
        'event': 'request_start'
    }
    
    if user_id:
        log_data['user_id'] = user_id
    
    if extra:
        log_data.update(extra)
    
    logger.info(
        f"Request started: {endpoint}",
        extra={'extra_fields': log_data}
    )


def log_request_end(
    logger: logging.Logger,
    endpoint: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log the completion of an API request.
    
    Args:
        logger: Logger instance
        endpoint: API endpoint
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        user_id: User making the request
        extra: Additional context
    """
    log_data = {
        'endpoint': endpoint,
        'status_code': status_code,
        'duration_ms': duration_ms,
        'event': 'request_end'
    }
    
    if user_id:
        log_data['user_id'] = user_id
    
    if extra:
        log_data.update(extra)
    
    # Use appropriate log level based on status code
    if status_code >= 500:
        level = logging.ERROR
    elif status_code >= 400:
        level = logging.WARNING
    else:
        level = logging.INFO
    
    logger.log(
        level,
        f"Request completed: {endpoint} - {status_code} ({duration_ms:.2f}ms)",
        extra={'extra_fields': log_data}
    )


# Initialize logging on module import
# This ensures logging is configured before any other code runs
if not logging.getLogger().handlers:
    setup_logging()
