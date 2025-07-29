# ammb/meshcore_handler.py
"""
Handles all interactions with the Meshcore device via its serial port.

- Establishes serial connection.
- Runs receiver thread to read, decode (using selected protocol), translate,
  and queue messages for Meshtastic. Handles reconnection.
- Runs sender thread to encode (using selected protocol) and send messages
  from the queue to the Meshcore serial port.
"""

import logging
import threading
import time
import json # For converting non-string payloads back to string
from queue import Queue, Empty
from typing import Optional, Dict, Any

# External dependencies
import serial

# Project dependencies
from .config_handler import BridgeConfig
from .protocol import MeshcoreProtocolHandler, get_protocol_handler

class MeshcoreHandler:
    """Manages connection and communication with the Meshcore device."""

    RECONNECT_DELAY_S = 10 # Seconds to wait before attempting serial reconnect

    def __init__(self, config: BridgeConfig, to_meshtastic_queue: Queue, from_meshtastic_queue: Queue, shutdown_event: threading.Event):
        """
        Initializes the MeshcoreHandler.

        Args:
            config: The bridge configuration object.
            to_meshtastic_queue: Queue for messages going towards Meshtastic.
            from_meshtastic_queue: Queue for messages coming from Meshtastic (to be sent to Meshcore).
            shutdown_event: Event to signal graceful shutdown.
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.to_meshtastic_queue = to_meshtastic_queue
        self.to_meshcore_queue = from_meshtastic_queue # Rename for clarity
        self.shutdown_event = shutdown_event

        self.serial_port: Optional[serial.Serial] = None
        self.receiver_thread: Optional[threading.Thread] = None
        self.sender_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock() # Protect access to self.serial_port

        # Get the appropriate protocol handler based on config
        try:
            self.protocol_handler: MeshcoreProtocolHandler = get_protocol_handler(config.meshcore_protocol)
        except ValueError as e:
            self.logger.critical(f"Failed to initialize protocol handler: {e}. Meshcore communication will likely fail.")
            # Create a dummy handler to prevent crashes, but log critical error
            class DummyHandler(MeshcoreProtocolHandler):
                def encode(self, data): return None
                def decode(self, line): return None
            self.protocol_handler = DummyHandler()


    def connect(self) -> bool:
        """
        Attempts to establish a connection to the Meshcore device via serial.

        Returns:
            True if connection is successful, False otherwise.
        """
        with self._lock: # Ensure only one thread tries to connect at a time
            if self.serial_port and self.serial_port.is_open:
                self.logger.warning("Connect called while already connected.")
                return True

            try:
                self.logger.info(f"Attempting connection to Meshcore on {self.config.meshcore_port} at {self.config.meshcore_baud} baud...")
                self.serial_port = serial.Serial(
                    port=self.config.meshcore_port,
                    baudrate=self.config.meshcore_baud,
                    timeout=1, # Read timeout in seconds
                    # bytesize=serial.EIGHTBITS, # Default
                    # parity=serial.PARITY_NONE, # Default
                    # stopbits=serial.STOPBITS_ONE, # Default
                    # xonxoff=False, # Default
                    # rtscts=False, # Default
                    # dsrdtr=False, # Default
                )
                # Check if the port actually opened
                if self.serial_port.is_open:
                    self.logger.info(f"Connected to Meshcore device on {self.config.meshcore_port}")
                    # Optional: Send an initial command or wait for a ready signal if protocol requires
                    # self.serial_port.write(b'INIT\n')
                    # time.sleep(1)
                    # response = self.serial_port.readline()
                    # self.logger.info(f"Meshcore initial response: {response}")
                    return True
                else:
                    # This case should ideally be caught by SerialException, but safety check
                    self.logger.error(f"Failed to open Meshcore serial port {self.config.meshcore_port}, but no exception was raised.")
                    self.serial_port = None
                    return False

            except serial.SerialException as e:
                self.logger.error(f"Serial error connecting to Meshcore device {self.config.meshcore_port}: {e}")
                self.serial_port = None
                return False
            except Exception as e:
                # Catch unexpected errors like invalid baud rate, etc.
                self.logger.error(f"Unexpected error connecting to Meshcore: {e}", exc_info=True)
                self.serial_port = None
                return False

    def start_threads(self):
        """Starts the Meshcore receiver and sender threads."""
        if self.receiver_thread and self.receiver_thread.is_alive():
            self.logger.warning("Receiver thread already started.")
        else:
            self.logger.info("Starting Meshcore receiver thread...")
            self.receiver_thread = threading.Thread(target=self._meshcore_receiver_loop, daemon=True, name="MeshcoreReceiver")
            self.receiver_thread.start()

        if self.sender_thread and self.sender_thread.is_alive():
            self.logger.warning("Sender thread already started.")
        else:
            self.logger.info("Starting Meshcore sender thread...")
            self.sender_thread = threading.Thread(target=self._meshcore_sender_loop, daemon=True, name="MeshcoreSender")
            self.sender_thread.start()

    def stop(self):
        """Signals shutdown and cleans up resources."""
        self.logger.info("Stopping Meshcore handler...")

        # Threads will stop based on shutdown_event
        if self.receiver_thread and self.receiver_thread.is_alive():
             self.logger.debug("Waiting for Meshcore receiver thread to join...")
             self.receiver_thread.join(timeout=2) # Shorter timeout as it might be blocked on readline
             if self.receiver_thread.is_alive():
                  self.logger.warning("Meshcore receiver thread did not terminate gracefully.")
        if self.sender_thread and self.sender_thread.is_alive():
             self.logger.debug("Waiting for Meshcore sender thread to join...")
             self.sender_thread.join(timeout=5)
             if self.sender_thread.is_alive():
                  self.logger.warning("Meshcore sender thread did not terminate gracefully.")

        # Close serial port after threads have stopped (or attempted to)
        self._close_serial()
        self.logger.info("Meshcore handler stopped.")

    def _close_serial(self):
        """Closes the serial port if it's open."""
        with self._lock:
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                    self.logger.info(f"Meshcore serial port {self.config.meshcore_port} closed.")
                except Exception as e:
                    self.logger.error(f"Error closing Meshcore serial port: {e}", exc_info=True)
                finally:
                    self.serial_port = None


    def _meshcore_receiver_loop(self):
        """Continuously reads from serial, decodes, translates, and queues messages."""
        self.logger.info("Meshcore receiver loop started.")
        while not self.shutdown_event.is_set():
            # --- Connection Check and Reconnect Logic ---
            with self._lock:
                port_needs_reconnect = not self.serial_port or not self.serial_port.is_open

            if port_needs_reconnect:
                self.logger.warning("Meshcore serial port not connected. Attempting reconnect...")
                if self.connect(): # connect() is already thread-safe
                    self.logger.info(f"Meshcore reconnected successfully on {self.config.meshcore_port}.")
                else:
                    # Wait before retrying connection to avoid busy-looping
                    self.shutdown_event.wait(self.RECONNECT_DELAY_S)
                    continue # Skip to next loop iteration to retry connection

            # --- Read and Process Data ---
            try:
                # Read one line (or up to timeout) from the serial port
                # This assumes a line-based protocol (like json_newline)
                # For other protocols, reading logic might need adjustment (e.g., read fixed bytes)
                with self._lock:  # Ensure port isn't closed by another thread during read
                    if not self.serial_port or not self.serial_port.is_open:
                        continue  # Port closed between check and read, loop again
                    if self.config.meshcore_protocol == 'json_newline':
                        line: Optional[bytes] = self.serial_port.readline()
                    else:
                        header = self.serial_port.read(3)
                        if not header or len(header) < 3:
                            continue
                        start = header[0]
                        if start not in (0x3E, 0x3C):
                            continue
                        length = int.from_bytes(header[1:3], 'little')
                        payload = self.serial_port.read(length)
                        if len(payload) < length:
                            self.logger.warning(
                                f"Incomplete frame: expected {length} bytes, got {len(payload)}"
                            )
                            continue
                        line = header + payload

                if line:
                    self.logger.debug(f"Meshcore RAW RX: {line!r}")
                    # Decode using the selected protocol handler
                    meshcore_msg: Optional[Dict[str, Any]] = self.protocol_handler.decode(line)

                    if meshcore_msg:
                        # --- Basic Translation Logic (Meshcore -> Meshtastic) ---
                        # Assumes the decoded dict contains keys needed for Meshtastic
                        # Adjust keys based on protocol.py's decode implementation
                        dest_meshtastic_id = meshcore_msg.get("destination_meshtastic_id")
                        payload = meshcore_msg.get("payload") # Could be string or dict/list etc.
                        payload_json = meshcore_msg.get("payload_json") # Alternative structured payload
                        channel_index = meshcore_msg.get("channel_index", 0)
                        want_ack = meshcore_msg.get("want_ack", False)

                        # Determine the text payload to send
                        text_payload_str: Optional[str] = None
                        if isinstance(payload, str):
                            text_payload_str = payload
                        elif payload_json is not None:
                            # Convert structured JSON payload back to string for sendText
                            try:
                                text_payload_str = json.dumps(payload_json)
                            except (TypeError, ValueError) as e:
                                self.logger.error(f"Failed to serialize payload_json: {e} - Data: {payload_json}")
                        elif payload is not None: # Handle non-string, non-None payload if payload_json wasn't used
                             text_payload_str = str(payload)


                        if dest_meshtastic_id and text_payload_str is not None:
                            # Construct message for Meshtastic sender queue
                            meshtastic_msg = {
                                "destination": dest_meshtastic_id,
                                "text": text_payload_str,
                                "channel_index": channel_index,
                                "want_ack": want_ack,
                            }

                            try:
                                self.to_meshtastic_queue.put_nowait(meshtastic_msg)
                                self.logger.info(f"Queued message from Meshcore for Meshtastic node {dest_meshtastic_id}")
                            except Queue.Full:
                                self.logger.warning("Meshtastic send queue is full. Dropping incoming message from Meshcore.")
                        else:
                            self.logger.warning(f"Meshcore RX: Decoded message lacks required fields ('destination_meshtastic_id' or 'payload'/'payload_json'): {meshcore_msg}")
                    # else: message was decoded as None (e.g., empty line, parse error) - already logged by decoder

                # else: readline timed out (no data received), this is normal

            except serial.SerialException as e:
                self.logger.error(f"Meshcore serial error in receiver loop: {e}. Attempting to reconnect...")
                self._close_serial() # Ensure port is marked closed for reconnect logic
                # Reconnect attempt will happen at the start of the next loop iteration
                time.sleep(1) # Small delay before retry loop
            except Exception as e:
                # Catch unexpected errors in the receiver loop
                self.logger.error(f"Unexpected error in meshcore_receiver_loop: {e}", exc_info=True)
                # Consider if reconnect is needed here too
                self._close_serial()
                time.sleep(self.RECONNECT_DELAY_S / 2) # Shorter sleep for unexpected errors

        self.logger.info("Meshcore receiver loop stopped.")


    def _meshcore_sender_loop(self):
        """Continuously reads from the queue, encodes, and sends messages to Meshcore."""
        self.logger.info("Meshcore sender loop started.")
        while not self.shutdown_event.is_set():
            # --- Connection Check ---
            # Less critical to check connection before get(), but good practice
            with self._lock:
                port_is_open = self.serial_port and self.serial_port.is_open

            if not port_is_open:
                 # Wait for the receiver thread to potentially reconnect
                 self.logger.debug("Meshcore port closed, sender waiting...")
                 self.shutdown_event.wait(timeout=self.RECONNECT_DELAY_S / 2)
                 continue

            # --- Get Message and Send ---
            try:
                # Wait for a message for up to 1 second
                item: Optional[Dict[str, Any]] = self.to_meshcore_queue.get(timeout=1)
                if not item:
                    continue

                # Encode the message using the selected protocol handler
                encoded_message: Optional[bytes] = self.protocol_handler.encode(item)

                if encoded_message:
                    with self._lock: # Ensure port isn't closed during write
                        if not self.serial_port or not self.serial_port.is_open:
                            self.logger.warning("Meshcore port closed before send could complete. Message likely lost.")
                            # TODO: Requeue logic?
                            self.to_meshcore_queue.task_done()
                            continue

                        try:
                            self.logger.info(f"Meshcore TX -> Port: {self.config.meshcore_port}, Payload: {encoded_message!r}")
                            self.serial_port.write(encoded_message)
                            self.serial_port.flush() # Ensure data is sent from buffer
                            self.to_meshcore_queue.task_done() # Mark message as processed
                        except serial.SerialTimeoutException as e:
                            # This might happen if write timeout is set, though less common
                            self.logger.error(f"Meshcore serial timeout during send: {e}. Message likely lost.")
                            self.to_meshcore_queue.task_done()
                            self._close_serial() # Assume port issue, trigger reconnect
                        except serial.SerialException as e:
                            self.logger.error(f"Meshcore serial error during send: {e}. Message likely lost.")
                            self.to_meshcore_queue.task_done()
                            self._close_serial() # Assume port issue, trigger reconnect
                        except Exception as e:
                            self.logger.error(f"Unexpected error sending Meshcore message: {e}", exc_info=True)
                            self.to_meshcore_queue.task_done() # Discard message
                else:
                    # Encoding failed (already logged by encoder)
                    self.logger.error(f"Failed to encode message for Meshcore: {item}")
                    self.to_meshcore_queue.task_done() # Discard unencodable message

            except Empty:
                # Queue was empty, timeout occurred. This is normal.
                continue
            except Exception as e:
                # Catch unexpected errors in the sender loop itself
                self.logger.error(f"Critical error in meshcore_sender_loop: {e}", exc_info=True)
                time.sleep(5) # Avoid rapid looping

        self.logger.info("Meshcore sender loop stopped.")
