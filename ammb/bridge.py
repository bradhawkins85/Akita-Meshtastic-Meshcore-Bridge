# ammb/bridge.py
"""
Main Bridge orchestrator class.

Initializes and manages the Meshtastic and Meshcore handlers,
starts their threads, and handles graceful shutdown.
"""

import logging
import threading
from queue import Queue
import time

# Project dependencies
from .config_handler import BridgeConfig
from .meshtastic_handler import MeshtasticHandler
from .meshcore_handler import MeshcoreHandler

class Bridge:
    """Orchestrates the Meshtastic-Meshcore bridge operation."""

    def __init__(self, config: BridgeConfig):
        """
        Initializes the Bridge.

        Args:
            config: The loaded bridge configuration.
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.shutdown_event = threading.Event()

        # --- Initialize Queues ---
        # Queue names indicate direction *towards* that network
        self.to_meshtastic_queue = Queue(maxsize=config.queue_size)
        self.to_meshcore_queue = Queue(maxsize=config.queue_size)
        self.logger.info(f"Message queues initialized with max size: {config.queue_size}")

        # --- Initialize Handlers ---
        self.logger.info("Initializing network handlers...")
        self.meshtastic_handler = MeshtasticHandler(
            config=config,
            to_meshcore_queue=self.to_meshcore_queue,
            from_meshcore_queue=self.to_meshtastic_queue, # Pass the correct queue
            shutdown_event=self.shutdown_event
        )
        self.meshcore_handler = MeshcoreHandler(
            config=config,
            to_meshtastic_queue=self.to_meshtastic_queue,
            from_meshtastic_queue=self.to_meshcore_queue, # Pass the correct queue
            shutdown_event=self.shutdown_event
        )
        self.logger.info("Network handlers initialized.")

        # List to keep track of handler instances for easy stop() iteration
        self.handlers = [self.meshtastic_handler, self.meshcore_handler]


    def run(self):
        """Starts the bridge and keeps it running until shutdown."""
        self.logger.info("Starting AMMB...")

        # --- Initial Connections ---
        # Attempt initial connection to Meshtastic (required to start)
        if not self.meshtastic_handler.connect():
            self.logger.critical("Failed to connect to Meshtastic device on startup. Bridge cannot start.")
            # Perform minimal cleanup if needed before exiting
            self.stop() # Call stop even on failed start for consistency
            return # Exit run method

        # Attempt initial connection to Meshcore (can retry in background if fails)
        if not self.meshcore_handler.connect():
            self.logger.warning("Failed to connect to Meshcore device initially. Handler will keep trying in background.")
            # Bridge continues running even if Meshcore fails initially

        # --- Start Handler Threads ---
        self.logger.info("Starting handler threads...")
        try:
            self.meshtastic_handler.start_sender()
            self.meshcore_handler.start_threads() # Starts both receiver and sender
        except Exception as e:
             self.logger.critical(f"Failed to start handler threads: {e}", exc_info=True)
             self.stop() # Attempt cleanup
             return

        self.logger.info("Bridge threads started. Running... (Press Ctrl+C to stop)")

        # --- Main Loop ---
        # Keep the main thread alive while checking for the shutdown signal
        try:
            while not self.shutdown_event.is_set():
                # Optional: Add health checks here if needed
                # e.g., check if handler threads are still alive
                # if not self.meshcore_handler.receiver_thread.is_alive(): ...
                time.sleep(1) # Prevent busy-waiting

        except Exception as e:
             # Catch unexpected errors in the main loop itself
             self.logger.critical(f"Unexpected error in main bridge loop: {e}", exc_info=True)
        finally:
             # --- Shutdown Sequence ---
             self.logger.info("Main loop exiting. Initiating shutdown sequence...")
             self.stop() # Ensure stop is called on any exit from the loop

    def stop(self):
        """Initiates graceful shutdown of all components."""
        if self.shutdown_event.is_set():
             self.logger.info("Shutdown already in progress.")
             return

        self.logger.info("Signaling shutdown to all components...")
        self.shutdown_event.set()

        # Stop handlers (which will stop their threads and close connections)
        # Stop in reverse order of dependency, or handle potential deadlocks if any
        for handler in reversed(self.handlers): # Example: Stop Meshcore before Meshtastic? (Order might not matter much here)
             try:
                  handler.stop()
             except Exception as e:
                  self.logger.error(f"Error stopping handler {type(handler).__name__}: {e}", exc_info=True)

        # Optional: Wait for queues to empty? (Might block shutdown indefinitely)
        # self.logger.info("Waiting for queues to empty...")
        # self.to_meshtastic_queue.join()
        # self.to_meshcore_queue.join()

        self.logger.info("Bridge shutdown sequence complete.")

