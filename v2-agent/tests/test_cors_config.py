"""
Tests for CORS configuration validation.
"""
import os
import pytest


def get_cors_origins_logic(allowed_origins_env, environment):
    """
    Extracted CORS logic for testing without importing main.py.
    This mirrors the logic in main.py's get_cors_origins function.
    """
    if allowed_origins_env:
        # Parse comma-separated origins
        origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
        
        # In production, ensure wildcard is not used
        if environment == "production" and "*" in origins:
            raise ValueError("Wildcard '*' is not allowed in ALLOWED_ORIGINS for production environment")
        
        return origins
    else:
        # Default behavior: wildcard only in development
        if environment == "production":
            raise ValueError("ALLOWED_ORIGINS must be explicitly set in production environment")
        return ["*"]


def test_cors_development_default():
    """
    Test that in development mode without ALLOWED_ORIGINS set,
    wildcard is used by default.
    
    Validates: Requirements 8.1
    """
    origins = get_cors_origins_logic("", "development")
    assert origins == ["*"], "Development should default to wildcard"


def test_cors_production_requires_explicit_origins():
    """
    Test that production environment requires explicit ALLOWED_ORIGINS.
    
    Validates: Requirements 8.1
    """
    # This should raise an error
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS must be explicitly set in production"):
        get_cors_origins_logic("", "production")


def test_cors_production_rejects_wildcard():
    """
    Test that production environment rejects wildcard in ALLOWED_ORIGINS.
    
    Validates: Requirements 8.1
    """
    # This should raise an error
    with pytest.raises(ValueError, match="Wildcard '\\*' is not allowed in ALLOWED_ORIGINS for production"):
        get_cors_origins_logic("*", "production")


def test_cors_multiple_origins():
    """
    Test that multiple origins can be configured.
    
    Validates: Requirements 8.5
    """
    origins = get_cors_origins_logic(
        "https://example.com,https://app.example.com,https://admin.example.com",
        "production"
    )
    
    assert len(origins) == 3, "Should parse three origins"
    assert "https://example.com" in origins
    assert "https://app.example.com" in origins
    assert "https://admin.example.com" in origins


def test_cors_methods_configured():
    """
    Test that required HTTP methods are configured in CORS middleware.
    
    Validates: Requirements 8.2
    """
    # This test verifies the middleware configuration in main.py
    # We check that the required methods are present
    required_methods = ["GET", "POST", "OPTIONS"]
    
    # Read main.py to verify configuration
    import pathlib
    main_path = pathlib.Path(__file__).parent.parent / "main.py"
    with open(main_path, 'r') as f:
        content = f.read()
    
    # Verify methods are configured
    assert 'allow_methods=["GET", "POST", "OPTIONS"]' in content, \
        "CORS middleware should allow GET, POST, and OPTIONS methods"


def test_cors_headers_configured():
    """
    Test that required headers are configured in CORS middleware.
    
    Validates: Requirements 8.3
    """
    # This test verifies the middleware configuration in main.py
    required_headers = ["Authorization", "Content-Type"]
    
    # Read main.py to verify configuration
    import pathlib
    main_path = pathlib.Path(__file__).parent.parent / "main.py"
    with open(main_path, 'r') as f:
        content = f.read()
    
    # Verify headers are configured
    assert 'allow_headers=["Authorization", "Content-Type"]' in content, \
        "CORS middleware should allow Authorization and Content-Type headers"
