"""
Property-based tests for App Runner configuration validation.
"""
import yaml
from pathlib import Path
from hypothesis import given, strategies as st
import pytest


# Feature: app-runner-deployment, Property 1: apprunner.yaml completeness
def test_apprunner_yaml_completeness():
    """
    Property 1: apprunner.yaml completeness
    For any generated apprunner.yaml file, it should contain all required fields:
    version, runtime, build.commands, run.command, and run.network.port
    
    Validates: Requirements 1.1
    """
    # Load the actual apprunner.yaml file
    apprunner_path = Path(__file__).parent.parent / "apprunner.yaml"
    
    with open(apprunner_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Check required top-level fields
    assert 'version' in config, "apprunner.yaml must contain 'version' field"
    assert 'runtime' in config, "apprunner.yaml must contain 'runtime' field"
    assert 'build' in config, "apprunner.yaml must contain 'build' field"
    assert 'run' in config, "apprunner.yaml must contain 'run' field"
    
    # Check build.commands structure
    assert 'commands' in config['build'], "build section must contain 'commands' field"
    
    # Check run section required fields
    assert 'command' in config['run'], "run section must contain 'command' field"
    assert 'network' in config['run'], "run section must contain 'network' field"
    assert 'port' in config['run']['network'], "run.network section must contain 'port' field"


@given(st.dictionaries(
    keys=st.sampled_from(['version', 'runtime', 'build', 'run', 'extra_field']),
    values=st.one_of(
        st.text(max_size=20),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=3)
    ),
    min_size=0,
    max_size=6
))
def test_apprunner_yaml_completeness_property(config):
    """
    Property-based test: Generate random configurations and verify validation logic.
    A valid configuration must have all required fields.
    
    Validates: Requirements 1.1
    """
    def validate_apprunner_config(cfg):
        """Validate that a configuration has all required fields."""
        required_fields = ['version', 'runtime', 'build', 'run']
        
        # Check top-level required fields
        for field in required_fields:
            if field not in cfg:
                return False
        
        # Check build.commands
        if not isinstance(cfg.get('build'), dict):
            return False
        if 'commands' not in cfg['build']:
            return False
        
        # Check run section
        if not isinstance(cfg.get('run'), dict):
            return False
        if 'command' not in cfg['run']:
            return False
        if 'network' not in cfg['run']:
            return False
        if not isinstance(cfg['run'].get('network'), dict):
            return False
        if 'port' not in cfg['run']['network']:
            return False
        
        return True
    
    # The property: if a config has all required fields, validation should pass
    has_all_required = (
        'version' in config and
        'runtime' in config and
        'build' in config and
        isinstance(config.get('build'), dict) and
        'commands' in config.get('build', {}) and
        'run' in config and
        isinstance(config.get('run'), dict) and
        'command' in config.get('run', {}) and
        'network' in config.get('run', {}) and
        isinstance(config.get('run', {}).get('network'), dict) and
        'port' in config.get('run', {}).get('network', {})
    )
    
    result = validate_apprunner_config(config)
    
    # Property: validation result should match whether all required fields are present
    assert result == has_all_required, \
        f"Validation mismatch: has_all_required={has_all_required}, result={result}, config={config}"
