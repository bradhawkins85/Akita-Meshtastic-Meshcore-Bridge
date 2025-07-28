# ammb/config_handler.py
"""
Handles loading, validation, and access for the bridge configuration (`config.ini`).
"""

import configparser
import logging
import os
from typing import NamedTuple, Optional

# Define the structure for the configuration using NamedTuple for immutability and clarity
class BridgeConfig(NamedTuple):
    """Stores all configuration settings for the bridge."""
    meshtastic_port: str
    meshtastic_tcp_host: str
    meshtastic_tcp_port: int
    meshcore_port: str
    meshcore_baud: int
    meshcore_protocol: str
    meshcore_network_id: str
    bridge_node_id: str
    queue_size: int
    log_level: str

# --- Constants ---
CONFIG_FILE = "config.ini" # Default config filename

# Default values used if a setting is missing from config.ini
DEFAULT_CONFIG = {
    'MESHTASTIC_SERIAL_PORT': '/dev/ttyUSB0', # Example for Linux
    # 'MESHTASTIC_SERIAL_PORT': 'COM3',      # Example for Windows
    'MESHTASTIC_TCP_HOST': '127.0.0.1',       # Default host for TCP connection
    'MESHTASTIC_TCP_PORT': '4403',            # Default port for TCP connection
    'MESHCORE_SERIAL_PORT': '/dev/ttyS0',    # Example for Linux
    # 'MESHCORE_SERIAL_PORT': 'COM4',        # Example for Windows
    'MESHCORE_BAUD_RATE': '9600',            # Common baud rate, adjust as needed
    'MESHCORE_PROTOCOL': 'json_newline',     # Default protocol handler
    'MESHCORE_NETWORK_ID': 'ammb_default_net', # Conceptual ID
    'BRIDGE_NODE_ID': '!ammb_bridge',        # Default bridge ID, recommend user sets explicitly
    'MESSAGE_QUEUE_SIZE': '100',             # Default queue size
    'LOG_LEVEL': 'INFO',                     # Default logging level
}

# Valid options for settings requiring specific choices
VALID_LOG_LEVELS = {'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'}
VALID_MESHCORE_PROTOCOLS = {'json_newline'} # Add more as they are implemented

# --- Functions ---
def load_config(config_path: str = CONFIG_FILE) -> Optional[BridgeConfig]:
    """
    Loads and validates configuration from the specified INI file.

    Reads the configuration file, applies defaults for missing values,
    validates data types and choices, and returns a BridgeConfig object
    or None if loading or validation fails.

    Args:
        config_path: The path to the configuration file.

    Returns:
        A BridgeConfig named tuple containing the settings, or None if an error occurs.
    """
    logger = logging.getLogger(__name__) # Get logger for this module
    config = configparser.ConfigParser()

    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        logger.error("Please copy 'examples/config.ini.example' to 'config.ini' and configure it.")
        return None

    try:
        logger.info(f"Reading configuration from: {config_path}")
        config.read(config_path)

        # Use the [DEFAULT] section for all settings

        if not config.defaults():
             logger.error(f"Configuration file '{config_path}' is missing the required [DEFAULT] section.")
             return None
        cfg_section = config['DEFAULT']

        # --- Get and Validate Settings ---
        # Helper function to get value or default
        def get_setting(key: str) -> str:
            return cfg_section.get(key, DEFAULT_CONFIG[key])

        meshtastic_port = get_setting('MESHTASTIC_SERIAL_PORT')
        meshtastic_tcp_host = get_setting('MESHTASTIC_TCP_HOST')
        meshtastic_tcp_port_str = get_setting('MESHTASTIC_TCP_PORT')
        meshcore_port = get_setting('MESHCORE_SERIAL_PORT')
        meshcore_network_id = get_setting('MESHCORE_NETWORK_ID')
        bridge_node_id = get_setting('BRIDGE_NODE_ID')

        # Validate Integer settings
        try:
            meshcore_baud = int(get_setting('MESHCORE_BAUD_RATE'))
            queue_size = int(get_setting('MESSAGE_QUEUE_SIZE'))
            meshtastic_tcp_port = int(meshtastic_tcp_port_str)
            if meshtastic_tcp_port <= 0 or meshtastic_tcp_port > 65535:
                raise ValueError('MESHTASTIC_TCP_PORT must be between 1 and 65535')
            if meshcore_baud <= 0 or queue_size <= 0:
                 raise ValueError("Baud rate and queue size must be positive integers.")
        except ValueError as e:
            logger.error(f"Invalid integer value in configuration: {e}")
            return None

        # Validate Choice settings
        log_level = get_setting('LOG_LEVEL').upper()
        if log_level not in VALID_LOG_LEVELS:
            logger.error(f"Invalid LOG_LEVEL '{log_level}'. Must be one of: {VALID_LOG_LEVELS}")
            return None

        meshcore_protocol = get_setting('MESHCORE_PROTOCOL').lower()
        if meshcore_protocol not in VALID_MESHCORE_PROTOCOLS:
            # Log a warning but proceed using the default, in case user adds custom protocol later
            logger.warning(
                f"Unrecognized MESHCORE_PROTOCOL '{meshcore_protocol}'. "
                f"Valid built-in options are: {VALID_MESHCORE_PROTOCOLS}. "
                f"Attempting to use '{meshcore_protocol}' - ensure a corresponding handler exists."
            )
            # Or, enforce strict validation:
            # logger.error(f"Invalid MESHCORE_PROTOCOL '{meshcore_protocol}'. Must be one of: {VALID_MESHCORE_PROTOCOLS}")
            # return None


        # --- Create and Return Config Object ---
        bridge_config = BridgeConfig(
            meshtastic_port=meshtastic_port,
            meshtastic_tcp_host=meshtastic_tcp_host,
            meshtastic_tcp_port=meshtastic_tcp_port,
            meshcore_port=meshcore_port,
            meshcore_baud=meshcore_baud,
            meshcore_protocol=meshcore_protocol,
            meshcore_network_id=meshcore_network_id,
            bridge_node_id=bridge_node_id,
            queue_size=queue_size,
            log_level=log_level
        )
        logger.debug(f"Configuration loaded: {bridge_config}")
        return bridge_config

    except configparser.Error as e:
        logger.error(f"Error parsing configuration file {config_path}: {e}")
        return None
    except KeyError as e:
        # This shouldn't happen if defaults cover all keys, but good practice
        logger.error(f"Missing expected configuration key: {e}")
        return None
    except Exception as e:
        # Catch unexpected errors during loading/validation
        logger.error(f"Unexpected error loading configuration: {e}", exc_info=True)
        return None

