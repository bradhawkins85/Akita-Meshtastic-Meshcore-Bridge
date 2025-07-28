# tests/test_config_handler.py
"""
Tests for the ammb.config_handler module.
"""

import pytest
import os
import configparser

# Modules to test
from ammb.config_handler import load_config, BridgeConfig, CONFIG_FILE, DEFAULT_CONFIG, VALID_LOG_LEVELS

def test_load_config_success(temp_config_file):
    """Test loading a valid configuration file."""
    config = load_config(temp_config_file)
    assert config is not None
    assert isinstance(config, BridgeConfig)
    # Check if values match the ones written in the fixture
    assert config.meshtastic_port == '/dev/test_meshtastic'
    assert config.meshtastic_tcp_host == '192.168.1.1'
    assert config.meshtastic_tcp_port == 4403
    assert config.meshcore_port == '/dev/test_meshcore'
    assert config.meshcore_baud == 19200
    assert config.meshcore_protocol == 'json_newline'
    assert config.meshcore_network_id == 'test_net'
    assert config.bridge_node_id == '!test_bridge'
    assert config.queue_size == 50
    assert config.log_level == 'DEBUG'

def test_load_config_file_not_found():
    """Test loading when the config file does not exist."""
    config = load_config("non_existent_file.ini")
    assert config is None

def test_load_config_missing_section(tmp_path):
    """Test loading a config file without the [DEFAULT] section."""
    config_path = tmp_path / "bad_config.ini"
    with open(config_path, "w") as f:
        f.write("[OTHER_SECTION]\nkey=value\n")
    config = load_config(str(config_path))
    assert config is None

def test_load_config_invalid_integer(tmp_path):
    """Test loading with an invalid integer value."""
    config_path = tmp_path / "bad_config.ini"
    parser = configparser.ConfigParser()
    # Use defaults but override one value incorrectly
    parser['DEFAULT'] = DEFAULT_CONFIG.copy()
    parser['DEFAULT']['MESSAGE_QUEUE_SIZE'] = 'not_an_integer'
    with open(config_path, 'w') as f:
        parser.write(f)
    config = load_config(str(config_path))
    assert config is None

def test_load_config_invalid_log_level(tmp_path):
    """Test loading with an invalid LOG_LEVEL choice."""
    config_path = tmp_path / "bad_config.ini"
    parser = configparser.ConfigParser()
    parser['DEFAULT'] = DEFAULT_CONFIG.copy()
    parser['DEFAULT']['LOG_LEVEL'] = 'INVALID_LEVEL'
    with open(config_path, 'w') as f:
        parser.write(f)
    config = load_config(str(config_path))
    assert config is None # Strict validation should fail

def test_load_config_uses_defaults(tmp_path):
    """Test that defaults are used for missing values."""
    config_path = tmp_path / "partial_config.ini"
    parser = configparser.ConfigParser()
    # Only provide a few values
    parser['DEFAULT'] = {
        'MESHTASTIC_SERIAL_PORT': '/dev/partial_meshtastic',
        'LOG_LEVEL': 'WARNING',
    }
    with open(config_path, 'w') as f:
        parser.write(f)

    config = load_config(str(config_path))
    assert config is not None
    assert config.meshtastic_port == '/dev/partial_meshtastic' # Overridden
    assert config.log_level == 'WARNING' # Overridden
    # Check a default value
    assert config.meshtastic_tcp_host == DEFAULT_CONFIG['MESHTASTIC_TCP_HOST']
    assert config.meshtastic_tcp_port == int(DEFAULT_CONFIG['MESHTASTIC_TCP_PORT'])
    assert config.meshcore_port == DEFAULT_CONFIG['MESHCORE_SERIAL_PORT']
    assert config.meshcore_baud == int(DEFAULT_CONFIG['MESHCORE_BAUD_RATE'])
    assert config.meshcore_protocol == DEFAULT_CONFIG['MESHCORE_PROTOCOL']

# Add more tests for edge cases, different invalid values, etc.

