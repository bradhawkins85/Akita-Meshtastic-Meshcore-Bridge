#!/usr/bin/env python3
# run_bridge.py
"""
Executable script to initialize and run the Akita Meshtastic-Meshcore Bridge.

This script handles:
- Checking for essential dependencies.
- Loading configuration from 'config.ini'.
- Setting up application-wide logging.
- Creating and running the main Bridge instance.
- Handling graceful shutdown on KeyboardInterrupt (Ctrl+C).
"""

import sys
import logging
import os

# Ensure the script can find the 'ammb' package, assuming run_bridge.py
# is in the project root and 'ammb' is a subdirectory.
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# --- Dependency Check ---
# Perform checks before importing potentially missing modules
try:
    import configparser
    import queue
    import threading
    import time
    import json
    import serial
    from pubsub import pub
    import meshtastic
    import meshtastic.tcp_interface  # Explicitly check submodule too
except ImportError as e:
    # Use basic print/logging as full logging isn't set up yet
    print(f"ERROR: Missing required library - {e.name}", file=sys.stderr)
    print("Please install required libraries by running:", file=sys.stderr)
    print(f"  pip install -r {os.path.join(project_root, 'requirements.txt')}", file=sys.stderr)
    sys.exit(1)

# --- Imports ---
# Now import project modules after dependency check
try:
    from ammb import Bridge
    from ammb.utils import setup_logging
    from ammb.config_handler import load_config, CONFIG_FILE
except ImportError as e:
    print(f"ERROR: Failed to import AMMB modules: {e}", file=sys.stderr)
    print("Ensure the script is run from the project root directory", file=sys.stderr)
    print(f"Current sys.path: {sys.path}", file=sys.stderr) # Debugging path issues
    sys.exit(1)


# --- Main Execution ---
if __name__ == "__main__":
    # Basic logging setup until config is loaded and proper logging is configured
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("--- Akita Meshtastic-Meshcore Bridge Starting ---")

    # --- Configuration Loading ---
    config_path = os.path.join(project_root, CONFIG_FILE)
    logging.info(f"Loading configuration from: {config_path}")
    config = load_config(config_path)
    if not config:
        logging.critical("Failed to load configuration. Bridge cannot start.")
        sys.exit(1)
    logging.info("Configuration loaded successfully.")

    # --- Logging Setup ---
    # Reconfigure logging based on the loaded configuration level
    setup_logging(config.log_level)
    logging.debug(f"Logging level set to {config.log_level}") # Log level confirmation

    # --- Bridge Initialization and Execution ---
    logging.info("Initializing bridge instance...")
    bridge = Bridge(config)
    try:
        logging.info("Starting bridge run loop...")
        bridge.run() # This call blocks until shutdown is initiated
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Initiating graceful shutdown...")
        # The bridge.run() loop likely exited, now call stop explicitly if needed,
        # although stop should ideally be called within run's finally block.
        # bridge.stop() # Bridge.run() should handle this via its finally block
    except Exception as e:
        # Catch any unexpected critical errors during bridge execution
        logging.critical(f"Unhandled critical exception in bridge execution: {e}", exc_info=True)
        logging.info("Attempting emergency shutdown...")
        bridge.stop() # Attempt graceful shutdown even on unexpected error
        sys.exit(1) # Exit with error status

    logging.info("--- Akita Meshtastic-Meshcore Bridge Stopped ---")
    sys.exit(0) # Exit cleanly
