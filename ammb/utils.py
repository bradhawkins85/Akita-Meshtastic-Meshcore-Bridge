# ammb/utils.py
"""
Shared utilities for the AMMB application, primarily logging setup.
"""

import logging

# Define custom logging format
LOG_FORMAT = '%(asctime)s - %(threadName)s - %(levelname)s - %(name)s - %(message)s'
# Define date format for logs
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logging(log_level_str: str):
    """
    Configures application-wide logging based on the provided level string.

    Sets the format, date format, and level for the root logger.
    Also adjusts levels for potentially noisy third-party libraries.

    Args:
        log_level_str: The desired logging level as a string (e.g., "INFO", "DEBUG").
    """
    numeric_level = getattr(logging, log_level_str.upper(), None)
    if not isinstance(numeric_level, int):
        logging.warning(
            f"Invalid log level specified: '{log_level_str}'. Defaulting to INFO."
        )
        numeric_level = logging.INFO

    # Reconfigure the root logger
    # Using force=True allows reconfiguration if basicConfig was called previously
    logging.basicConfig(level=numeric_level,
                        format=LOG_FORMAT,
                        datefmt=DATE_FORMAT,
                        force=True)

    # Adjust logging levels for noisy libraries if needed
    logging.getLogger("pypubsub").setLevel(logging.WARNING) # pypubsub can be verbose
    logging.getLogger("pubsub").setLevel(logging.WARNING)   # Alias for pypubsub often used
    logging.getLogger("meshtastic").setLevel(logging.INFO) # Set Meshtastic lib level (INFO or WARNING)

    # Example: Set a specific module's level
    # logging.getLogger("ammb.meshcore_handler").setLevel(logging.DEBUG)

    logging.info(f"Logging configured to level {logging.getLevelName(numeric_level)} ({numeric_level})")

