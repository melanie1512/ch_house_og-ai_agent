"""
Configuration validation module for AWS App Runner deployment.

This module provides validation functions for:
- Environment variables (required vs optional)
- Health check configuration
- Auto-scaling configuration
- App Runner service configuration
"""

import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation check"""
    is_valid: bool
    errors: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# Required environment variables for the application
REQUIRED_ENV_VARS = [
    "AWS_REGION",
    "SESSION_TABLE_NAME",
]

# At least one of these Bedrock-related variables must be present
BEDROCK_ENV_VARS = [
    "BEDROCK_MODEL",
    "BEDROCK_INFERENCE_PROFILE_ARN",
]

# Optional environment variables
OPTIONAL_ENV_VARS = [
    "BEDROCK_REGION",
    "API_HOST",
    "API_PORT",
    "LAMBDA_FUNCTION_ARN",
    "ALLOWED_ORIGINS",
    "ENVIRONMENT",
]


def validate_environment_variables(env_vars: Optional[Dict[str, str]] = None) -> ValidationResult:
    """
    Validate that all required environment variables are present.
    
    Args:
        env_vars: Dictionary of environment variables. If None, uses os.environ
        
    Returns:
        ValidationResult with validation status and any errors
        
    Requirements: 3.1, 3.2, 3.3
    """
    if env_vars is None:
        env_vars = dict(os.environ)
    
    errors = []
    warnings = []
    
    # Check required environment variables
    for var in REQUIRED_ENV_VARS:
        if var not in env_vars or not env_vars[var]:
            errors.append(f"Required environment variable '{var}' is missing or empty")
    
    # Check that at least one Bedrock variable is present
    bedrock_vars_present = [var for var in BEDROCK_ENV_VARS if var in env_vars and env_vars[var]]
    if not bedrock_vars_present:
        errors.append(
            f"At least one of {BEDROCK_ENV_VARS} must be set for Bedrock configuration"
        )
    
    # Warn about optional variables that might be useful
    if "BEDROCK_REGION" not in env_vars and "AWS_REGION" in env_vars:
        warnings.append(
            "BEDROCK_REGION not set, will default to AWS_REGION"
        )
    
    if "ENVIRONMENT" not in env_vars:
        warnings.append(
            "ENVIRONMENT not set, will default to 'development'"
        )
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


@dataclass
class HealthCheckConfig:
    """Health check configuration for App Runner"""
    protocol: str = "HTTP"
    path: str = "/docs"
    interval: int = 10  # seconds
    timeout: int = 5    # seconds
    healthy_threshold: int = 1
    unhealthy_threshold: int = 5


def validate_health_check_configuration(config: HealthCheckConfig) -> ValidationResult:
    """
    Validate health check configuration.
    
    Args:
        config: HealthCheckConfig instance to validate
        
    Returns:
        ValidationResult with validation status and any errors
        
    Requirements: 5.1, 5.3, 5.5
    """
    errors = []
    warnings = []
    
    # Validate protocol
    valid_protocols = ["HTTP", "HTTPS", "TCP"]
    if config.protocol not in valid_protocols:
        errors.append(
            f"Invalid protocol '{config.protocol}'. Must be one of {valid_protocols}"
        )
    
    # Validate path
    if not config.path.startswith("/"):
        errors.append(
            f"Health check path '{config.path}' must start with '/'"
        )
    
    # Validate timeout < interval
    if config.timeout >= config.interval:
        errors.append(
            f"Health check timeout ({config.timeout}s) must be less than interval ({config.interval}s)"
        )
    
    # Validate positive values
    if config.interval <= 0:
        errors.append(f"Health check interval must be positive, got {config.interval}")
    
    if config.timeout <= 0:
        errors.append(f"Health check timeout must be positive, got {config.timeout}")
    
    if config.healthy_threshold <= 0:
        errors.append(f"Healthy threshold must be positive, got {config.healthy_threshold}")
    
    if config.unhealthy_threshold <= 0:
        errors.append(f"Unhealthy threshold must be positive, got {config.unhealthy_threshold}")
    
    # Warnings for unusual configurations
    if config.interval < 5:
        warnings.append(
            f"Health check interval of {config.interval}s is very short, may cause unnecessary load"
        )
    
    if config.timeout < 2:
        warnings.append(
            f"Health check timeout of {config.timeout}s is very short, may cause false negatives"
        )
    
    if config.unhealthy_threshold > 10:
        warnings.append(
            f"Unhealthy threshold of {config.unhealthy_threshold} is high, may delay instance replacement"
        )
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


@dataclass
class AutoScalingConfig:
    """Auto-scaling configuration for App Runner"""
    min_size: int = 1
    max_size: int = 10
    max_concurrency: int = 100


def validate_auto_scaling_configuration(config: AutoScalingConfig) -> ValidationResult:
    """
    Validate auto-scaling configuration.
    
    Args:
        config: AutoScalingConfig instance to validate
        
    Returns:
        ValidationResult with validation status and any errors
        
    Requirements: 6.1, 6.2
    """
    errors = []
    warnings = []
    
    # Validate min_size >= 1
    if config.min_size < 1:
        errors.append(
            f"Minimum instance count must be at least 1, got {config.min_size}"
        )
    
    # Validate max_size >= min_size
    if config.max_size < config.min_size:
        errors.append(
            f"Maximum instance count ({config.max_size}) must be >= minimum ({config.min_size})"
        )
    
    # Validate max_size <= 100 (App Runner limit)
    if config.max_size > 100:
        errors.append(
            f"Maximum instance count ({config.max_size}) exceeds App Runner limit of 100"
        )
    
    # Validate max_concurrency is positive
    if config.max_concurrency <= 0:
        errors.append(
            f"Max concurrency must be positive, got {config.max_concurrency}"
        )
    
    # Warnings for unusual configurations
    if config.min_size == config.max_size:
        warnings.append(
            f"Min and max instance counts are equal ({config.min_size}), auto-scaling is effectively disabled"
        )
    
    if config.max_concurrency < 10:
        warnings.append(
            f"Max concurrency of {config.max_concurrency} is very low, may cause frequent scaling"
        )
    
    if config.max_concurrency > 200:
        warnings.append(
            f"Max concurrency of {config.max_concurrency} is very high, ensure your application can handle it"
        )
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_all_configurations(
    env_vars: Optional[Dict[str, str]] = None,
    health_check: Optional[HealthCheckConfig] = None,
    auto_scaling: Optional[AutoScalingConfig] = None
) -> Tuple[bool, Dict[str, ValidationResult]]:
    """
    Validate all configuration aspects.
    
    Args:
        env_vars: Environment variables to validate (None = use os.environ)
        health_check: Health check configuration (None = use defaults)
        auto_scaling: Auto-scaling configuration (None = use defaults)
        
    Returns:
        Tuple of (all_valid, results_dict) where results_dict contains
        ValidationResult for each configuration aspect
    """
    results = {}
    
    # Validate environment variables
    results["environment"] = validate_environment_variables(env_vars)
    
    # Validate health check configuration
    if health_check is None:
        health_check = HealthCheckConfig()
    results["health_check"] = validate_health_check_configuration(health_check)
    
    # Validate auto-scaling configuration
    if auto_scaling is None:
        auto_scaling = AutoScalingConfig()
    results["auto_scaling"] = validate_auto_scaling_configuration(auto_scaling)
    
    # Check if all validations passed
    all_valid = all(result.is_valid for result in results.values())
    
    return all_valid, results


def print_validation_results(results: Dict[str, ValidationResult]) -> None:
    """
    Print validation results in a human-readable format.
    
    Args:
        results: Dictionary of validation results from validate_all_configurations
    """
    print("\n" + "="*60)
    print("Configuration Validation Results")
    print("="*60)
    
    for category, result in results.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        
        if result.is_valid:
            print("  ✓ Valid")
        else:
            print("  ✗ Invalid")
        
        if result.errors:
            print("\n  Errors:")
            for error in result.errors:
                print(f"    - {error}")
        
        if result.warnings:
            print("\n  Warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")
    
    print("\n" + "="*60)
