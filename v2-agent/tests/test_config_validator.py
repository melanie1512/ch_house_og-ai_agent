"""
Unit tests for configuration validation module.
"""
import pytest
from config_validator import (
    validate_environment_variables,
    validate_health_check_configuration,
    validate_auto_scaling_configuration,
    validate_all_configurations,
    HealthCheckConfig,
    AutoScalingConfig,
    ValidationResult,
)


class TestEnvironmentVariableValidation:
    """Tests for environment variable validation"""
    
    def test_valid_environment_variables_with_bedrock_model(self):
        """Test validation passes with all required variables including BEDROCK_MODEL"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_valid_environment_variables_with_inference_profile(self):
        """Test validation passes with BEDROCK_INFERENCE_PROFILE_ARN instead of BEDROCK_MODEL"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_INFERENCE_PROFILE_ARN": "arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_missing_aws_region(self):
        """Test validation fails when AWS_REGION is missing"""
        env_vars = {
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert not result.is_valid
        assert any("AWS_REGION" in error for error in result.errors)
    
    def test_missing_session_table_name(self):
        """Test validation fails when SESSION_TABLE_NAME is missing"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert not result.is_valid
        assert any("SESSION_TABLE_NAME" in error for error in result.errors)
    
    def test_missing_bedrock_configuration(self):
        """Test validation fails when neither BEDROCK_MODEL nor BEDROCK_INFERENCE_PROFILE_ARN is set"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "SESSION_TABLE_NAME": "user_sessions",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert not result.is_valid
        assert any("BEDROCK" in error for error in result.errors)
    
    def test_empty_required_variable(self):
        """Test validation fails when required variable is empty string"""
        env_vars = {
            "AWS_REGION": "",
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert not result.is_valid
        assert any("AWS_REGION" in error for error in result.errors)
    
    def test_warnings_for_optional_variables(self):
        """Test that warnings are generated for missing optional but useful variables"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        result = validate_environment_variables(env_vars)
        
        assert result.is_valid
        # Should have warnings about BEDROCK_REGION and ENVIRONMENT
        assert len(result.warnings) > 0


class TestHealthCheckValidation:
    """Tests for health check configuration validation"""
    
    def test_valid_health_check_config(self):
        """Test validation passes with valid health check configuration"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/docs",
            interval=10,
            timeout=5,
            healthy_threshold=1,
            unhealthy_threshold=5
        )
        
        result = validate_health_check_configuration(config)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_timeout_greater_than_interval(self):
        """Test validation fails when timeout >= interval"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/docs",
            interval=5,
            timeout=10,  # Invalid: timeout > interval
        )
        
        result = validate_health_check_configuration(config)
        
        assert not result.is_valid
        assert any("timeout" in error.lower() and "interval" in error.lower() for error in result.errors)
    
    def test_timeout_equal_to_interval(self):
        """Test validation fails when timeout == interval"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/docs",
            interval=5,
            timeout=5,  # Invalid: timeout == interval
        )
        
        result = validate_health_check_configuration(config)
        
        assert not result.is_valid
        assert any("timeout" in error.lower() and "interval" in error.lower() for error in result.errors)
    
    def test_invalid_path_without_leading_slash(self):
        """Test validation fails when path doesn't start with /"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="docs",  # Invalid: missing leading /
            interval=10,
            timeout=5,
        )
        
        result = validate_health_check_configuration(config)
        
        assert not result.is_valid
        assert any("path" in error.lower() and "/" in error for error in result.errors)
    
    def test_invalid_protocol(self):
        """Test validation fails with invalid protocol"""
        config = HealthCheckConfig(
            protocol="FTP",  # Invalid protocol
            path="/docs",
            interval=10,
            timeout=5,
        )
        
        result = validate_health_check_configuration(config)
        
        assert not result.is_valid
        assert any("protocol" in error.lower() for error in result.errors)
    
    def test_negative_interval(self):
        """Test validation fails with negative interval"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/docs",
            interval=-5,  # Invalid: negative
            timeout=2,
        )
        
        result = validate_health_check_configuration(config)
        
        assert not result.is_valid
        assert any("interval" in error.lower() and "positive" in error.lower() for error in result.errors)
    
    def test_zero_timeout(self):
        """Test validation fails with zero timeout"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/docs",
            interval=10,
            timeout=0,  # Invalid: zero
        )
        
        result = validate_health_check_configuration(config)
        
        assert not result.is_valid
        assert any("timeout" in error.lower() and "positive" in error.lower() for error in result.errors)
    
    def test_valid_custom_path(self):
        """Test validation passes with custom health check path"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/health",
            interval=10,
            timeout=5,
        )
        
        result = validate_health_check_configuration(config)
        
        assert result.is_valid
    
    def test_valid_root_path(self):
        """Test validation passes with root path"""
        config = HealthCheckConfig(
            protocol="HTTP",
            path="/",
            interval=10,
            timeout=5,
        )
        
        result = validate_health_check_configuration(config)
        
        assert result.is_valid


class TestAutoScalingValidation:
    """Tests for auto-scaling configuration validation"""
    
    def test_valid_auto_scaling_config(self):
        """Test validation passes with valid auto-scaling configuration"""
        config = AutoScalingConfig(
            min_size=1,
            max_size=10,
            max_concurrency=100
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_min_size_less_than_one(self):
        """Test validation fails when min_size < 1"""
        config = AutoScalingConfig(
            min_size=0,  # Invalid: must be >= 1
            max_size=10,
            max_concurrency=100
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert not result.is_valid
        assert any("minimum" in error.lower() and "1" in error for error in result.errors)
    
    def test_max_size_less_than_min_size(self):
        """Test validation fails when max_size < min_size"""
        config = AutoScalingConfig(
            min_size=5,
            max_size=3,  # Invalid: max < min
            max_concurrency=100
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert not result.is_valid
        assert any("maximum" in error.lower() and "minimum" in error.lower() for error in result.errors)
    
    def test_max_size_exceeds_limit(self):
        """Test validation fails when max_size > 100"""
        config = AutoScalingConfig(
            min_size=1,
            max_size=150,  # Invalid: exceeds App Runner limit
            max_concurrency=100
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert not result.is_valid
        assert any("100" in error and "limit" in error.lower() for error in result.errors)
    
    def test_negative_max_concurrency(self):
        """Test validation fails with negative max_concurrency"""
        config = AutoScalingConfig(
            min_size=1,
            max_size=10,
            max_concurrency=-50  # Invalid: negative
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert not result.is_valid
        assert any("concurrency" in error.lower() and "positive" in error.lower() for error in result.errors)
    
    def test_zero_max_concurrency(self):
        """Test validation fails with zero max_concurrency"""
        config = AutoScalingConfig(
            min_size=1,
            max_size=10,
            max_concurrency=0  # Invalid: zero
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert not result.is_valid
        assert any("concurrency" in error.lower() and "positive" in error.lower() for error in result.errors)
    
    def test_warning_when_min_equals_max(self):
        """Test warning is generated when min_size == max_size (no auto-scaling)"""
        config = AutoScalingConfig(
            min_size=5,
            max_size=5,  # Same as min: auto-scaling disabled
            max_concurrency=100
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("equal" in warning.lower() for warning in result.warnings)
    
    def test_valid_single_instance_config(self):
        """Test validation passes with single instance (min=max=1)"""
        config = AutoScalingConfig(
            min_size=1,
            max_size=1,
            max_concurrency=100
        )
        
        result = validate_auto_scaling_configuration(config)
        
        assert result.is_valid


class TestValidateAllConfigurations:
    """Tests for combined validation"""
    
    def test_all_valid_configurations(self):
        """Test that all validations pass with valid configurations"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        health_check = HealthCheckConfig()
        auto_scaling = AutoScalingConfig()
        
        all_valid, results = validate_all_configurations(env_vars, health_check, auto_scaling)
        
        assert all_valid
        assert all(result.is_valid for result in results.values())
    
    def test_one_invalid_configuration_fails_all(self):
        """Test that one invalid configuration causes overall validation to fail"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            # Missing SESSION_TABLE_NAME
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        health_check = HealthCheckConfig()
        auto_scaling = AutoScalingConfig()
        
        all_valid, results = validate_all_configurations(env_vars, health_check, auto_scaling)
        
        assert not all_valid
        assert not results["environment"].is_valid
        assert results["health_check"].is_valid
        assert results["auto_scaling"].is_valid
    
    def test_multiple_invalid_configurations(self):
        """Test that multiple invalid configurations are all reported"""
        env_vars = {
            # Missing AWS_REGION and SESSION_TABLE_NAME
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        health_check = HealthCheckConfig(
            interval=5,
            timeout=10,  # Invalid: timeout > interval
        )
        auto_scaling = AutoScalingConfig(
            min_size=0,  # Invalid: must be >= 1
            max_size=10,
        )
        
        all_valid, results = validate_all_configurations(env_vars, health_check, auto_scaling)
        
        assert not all_valid
        assert not results["environment"].is_valid
        assert not results["health_check"].is_valid
        assert not results["auto_scaling"].is_valid
    
    def test_default_configurations_when_none_provided(self):
        """Test that default configurations are used when None is provided"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "SESSION_TABLE_NAME": "user_sessions",
            "BEDROCK_MODEL": "anthropic.claude-3-haiku-20240307-v1:0",
        }
        
        all_valid, results = validate_all_configurations(env_vars, None, None)
        
        # Should use default health_check and auto_scaling configs
        assert "health_check" in results
        assert "auto_scaling" in results
        assert results["health_check"].is_valid
        assert results["auto_scaling"].is_valid
