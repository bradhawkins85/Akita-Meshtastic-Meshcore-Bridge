# tests/conftest.py
"""
Pytest configuration and fixtures for the AMMB test suite.
"""

import pytest
import os
import configparser
from typing import Generator

# Example fixture to create a temporary config file for testing config_handler
@pytest.fixture(scope="function") # 'function' scope runs fixture for each test
def temp_config_file(tmp_path) -> Generator[str, None, None]:
    """Creates a temporary config.ini file and returns its path."""
    config_path = tmp_path / "config.ini"
    parser = configparser.ConfigParser()
    parser['DEFAULT'] = {
        'MESHTASTIC_SERIAL_PORT': '/dev/test_meshtastic',
        'MESHTASTIC_TCP_HOST': '192.168.1.1',
        'MESHTASTIC_TCP_PORT': '4403',
        'MESHCORE_SERIAL_PORT': '/dev/test_meshcore',
        'MESHCORE_BAUD_RATE': '19200',
        'MESHCORE_PROTOCOL': 'json_newline',
        'MESHCORE_NETWORK_ID': 'test_net',
        'BRIDGE_NODE_ID': '!test_bridge',
        'MESSAGE_QUEUE_SIZE': '50',
        'LOG_LEVEL': 'DEBUG',
    }
    with open(config_path, 'w') as f:
        parser.write(f)

    yield str(config_path) # Provide path to the test function

    # Teardown (optional, tmp_path handles file deletion)
    # os.remove(config_path)

# Add other fixtures here as needed, e.g., mock serial ports, mock queues etc.
# Example using pytest-mock (if installed):
#
# @pytest.fixture
# def mock_serial(mocker):
#     """Mocks the serial.Serial class."""
#     mock_serial_instance = mocker.MagicMock(spec=serial.Serial)
#     mock_serial_instance.is_open = True
#     mock_serial_instance.readline.return_value = b'' # Default empty read
#     mock_serial_instance.write.return_value = None
#     mock_serial_instance.close.return_value = None
#     mocker.patch('serial.Serial', return_value=mock_serial_instance)
#     return mock_serial_instance

