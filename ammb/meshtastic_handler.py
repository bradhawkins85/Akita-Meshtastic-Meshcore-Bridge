# ammb/meshtastic_handler.py
"""
Handles all interactions with the Meshtastic device and network.

- Establishes connection via serial port.
- Uses pubsub callbacks for receiving messages.
- Translates incoming Meshtastic messages and puts them on the outgoing queue.
- Runs a sender thread to send messages from the incoming queue to Meshtastic.
"""

import logging
import threading
import time
from queue import Queue, Empty
from typing import Optional, Dict, Any

# External dependencies
import meshtastic
import meshtastic.tcp_interface
from pubsub import pub
import serial # For specific exceptions like SerialException

# Project dependencies
from .config_handler import BridgeConfig

class MeshtasticHandler:
    """Manages connection and communication with the Meshtastic network."""

    def __init__(self, config: BridgeConfig, to_meshcore_queue: Queue, from_meshcore_queue: Queue, shutdown_event: threading.Event):
        """
        Initializes the MeshtasticHandler.

        Args:
            config: The bridge configuration object.
            to_meshcore_queue: Queue for messages going towards Meshcore.
            from_meshcore_queue: Queue for messages coming from Meshcore (to be sent to Meshtastic).
            shutdown_event: Event to signal graceful shutdown.
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.to_meshcore_queue = to_meshcore_queue
        self.to_meshtastic_queue = from_meshcore_queue # Rename for clarity within this class
        self.shutdown_event = shutdown_event

        self.interface: Optional[meshtastic.tcp_interface.TCPInterface] = None
        self.my_node_id: Optional[str] = None # Actual node ID from device
        self.sender_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock() # Protect access to self.interface during reconnect

    def connect(self) -> bool:
        """
        Attempts to establish a connection to the Meshtastic device.

        Returns:
            True if connection is successful, False otherwise.
        """
        with self._lock: # Ensure only one thread tries to connect at a time
            if self.interface:
                self.logger.warning("Connect called while already connected or connecting.")
                return True # Or False depending on desired behavior

            try:
                self.logger.info(
                    f"Attempting TCP connection to Meshtastic at {self.config.meshtastic_host}:{self.config.meshtastic_port}..."
                )
                # Explicitly pass noProto=False if needed, though default should be fine
                self.interface = meshtastic.tcp_interface.TCPInterface(
                    self.config.meshtastic_host,
                    portNumber=self.config.meshtastic_port,
                    # debugOut=sys.stdout # Optional: for deep debugging
                )

                # Get node info to confirm connection and get our actual ID
                # This can take a moment
                my_info = self.interface.getMyNodeInfo()
                if not my_info or 'num' not in my_info:
                     # Sometimes getMyNodeInfo fails initially, retry once?
                     time.sleep(1)
                     my_info = self.interface.getMyNodeInfo()

                if my_info and 'num' in my_info:
                    self.my_node_id = f"!{my_info['num']:x}" # Store as hex string '!...'
                    user_id = my_info.get('user', {}).get('id', 'N/A')
                    self.logger.info(f"Connected to Meshtastic device. Node ID: {self.my_node_id} ('{user_id}')")
                else:
                     self.logger.warning("Connected to Meshtastic, but failed to retrieve node info.")
                     # Can proceed without node info, but loopback detection might be less reliable

                # Register callback for received messages AFTER interface is confirmed working
                pub.subscribe(self._on_meshtastic_receive, "meshtastic.receive")
                self.logger.info("Meshtastic receive callback registered.")
                return True

            except (serial.SerialException, meshtastic.MeshtasticError, ImportError, Exception) as e:
                self.logger.error(f"Error connecting to Meshtastic device: {e}", exc_info=False) # Keep log cleaner
                self.interface = None # Ensure interface is None on failure
                self.my_node_id = None
                return False

    def start_sender(self):
        """Starts the Meshtastic sender thread."""
        if self.sender_thread and self.sender_thread.is_alive():
            self.logger.warning("Sender thread already started.")
            return

        self.logger.info("Starting Meshtastic sender thread...")
        self.sender_thread = threading.Thread(target=self._meshtastic_sender_loop, daemon=True, name="MeshtasticSender")
        self.sender_thread.start()

    def stop(self):
        """Signals shutdown and cleans up resources."""
        self.logger.info("Stopping Meshtastic handler...")
        # Unsubscribe from pubsub to prevent callbacks during shutdown
        try:
            # Use weak=False if subscribe used default weak=True, though explicit is safer
            pub.unsubscribe(self._on_meshtastic_receive, "meshtastic.receive")
            self.logger.debug("Unsubscribed from meshtastic.receive.")
        except Exception as e:
            # pubsub might raise if listener not found, ignore
            self.logger.debug(f"Error unsubscribing from pubsub (may be normal): {e}")

        with self._lock:
            if self.interface:
                try:
                    self.interface.close()
                    self.logger.info("Meshtastic interface closed.")
                except Exception as e:
                    self.logger.error(f"Error closing Meshtastic interface: {e}", exc_info=True)
                finally:
                    self.interface = None
                    self.my_node_id = None

        # Sender thread will stop based on shutdown_event
        if self.sender_thread and self.sender_thread.is_alive():
             self.logger.debug("Waiting for Meshtastic sender thread to join...")
             self.sender_thread.join(timeout=5) # Wait briefly
             if self.sender_thread.is_alive():
                  self.logger.warning("Meshtastic sender thread did not terminate gracefully.")

        self.logger.info("Meshtastic handler stopped.")


    def _on_meshtastic_receive(self, packet: Dict[str, Any], interface: Any):
        """
        Callback function for received Meshtastic packets (invoked by pubsub).

        Args:
            packet: The decoded packet dictionary from meshtastic-python.
            interface: The meshtastic interface instance (unused here).
        """
        try:
            self.logger.debug(f"Meshtastic Raw RX: {packet}")
            if not packet:
                return

            # Extract key information
            sender_id_num = packet.get('from') # Node number
            sender_id_hex = f"!{sender_id_num:x}" if sender_id_num else "UNKNOWN"
            portnum = packet.get('decoded', {}).get('portnum', 'UNKNOWN')
            payload_bytes = packet.get('decoded', {}).get('payload') # Raw bytes

            # --- Loopback Prevention ---
            # Compare against configured bridge ID and actual node ID (if available)
            is_loopback = False
            if self.config.bridge_node_id and sender_id_hex == self.config.bridge_node_id:
                 is_loopback = True
            elif self.my_node_id and sender_id_hex == self.my_node_id:
                 is_loopback = True

            if is_loopback:
                self.logger.debug(f"Ignoring loopback message from {sender_id_hex}")
                return

            # --- Message Processing & Translation ---
            # Handle different PortNums
            translated_payload = None
            if isinstance(portnum, str) and portnum == 'TEXT_MESSAGE_APP' and payload_bytes:
                try:
                    # Assume text messages are UTF-8 encoded strings
                    text_payload = payload_bytes.decode('utf-8', errors='replace')
                    self.logger.info(f"Meshtastic RX <{portnum}> From {sender_id_hex}: '{text_payload}'")
                    translated_payload = text_payload # Forward as is for JSON protocol
                except UnicodeDecodeError:
                    self.logger.warning(f"Meshtastic RX <{portnum}> From {sender_id_hex}: Received non-UTF8 payload: {payload_bytes!r}")
                    # Decide how to handle non-UTF8 text? Forward as hex? Drop?
                    # For now, let's try forwarding the repr()
                    translated_payload = repr(payload_bytes)

            elif isinstance(portnum, str) and portnum == 'POSITION_APP':
                 # Example: Handle position updates
                 pos = packet.get('decoded', {}).get('position', {})
                 lat = pos.get('latitude')
                 lon = pos.get('longitude')
                 alt = pos.get('altitude')
                 ts = pos.get('time') # This is GPS time, might need conversion
                 self.logger.info(f"Meshtastic RX <{portnum}> From {sender_id_hex}: Lat={lat}, Lon={lon}, Alt={alt}, Time={ts}")
                 # Translate position data into a structured format
                 translated_payload = {
                      "latitude": lat, "longitude": lon, "altitude": alt, "timestamp_gps": ts
                 }

            # Add handlers for other portnums (Telemetry, RangeTest, etc.) if needed
            # elif portnum == 'TELEMETRY_APP': ...

            else:
                # Log unhandled portnums if debugging is enabled
                self.logger.debug(f"Meshtastic RX <{portnum}> From {sender_id_hex}: Unhandled portnum or no payload.")
                return # Don't forward unhandled types for now

            # --- Queueing for Meshcore ---
            if translated_payload is not None:
                # Construct the standard message format for the Meshcore handler
                meshcore_message = {
                    "type": "meshtastic_message",
                    "sender_meshtastic_id": sender_id_hex,
                    "portnum": portnum,
                    "payload": translated_payload, # Can be string or dict
                    "timestamp_rx": time.time() # Bridge receive time
                    # Optionally add RSSI/SNR if available in packet
                    # "rssi": packet.get('rxSnr'),
                    # "snr": packet.get('rxRssi'),
                }

                try:
                    # Put the structured message onto the queue for the Meshcore sender
                    self.to_meshcore_queue.put_nowait(meshcore_message)
                    self.logger.debug(f"Queued message from {sender_id_hex} (Port: {portnum}) for Meshcore.")
                except Queue.Full:
                    self.logger.warning("Meshcore send queue is full. Dropping incoming Meshtastic message.")

        except Exception as e:
            # Catch errors within the callback to prevent crashing the pubsub/meshtastic threads
            self.logger.error(f"Error in _on_meshtastic_receive callback: {e}", exc_info=True)


    def _meshtastic_sender_loop(self):
        """Continuously reads from the queue and sends messages to Meshtastic."""
        self.logger.info("Meshtastic sender loop started.")
        while not self.shutdown_event.is_set():
            try:
                # Wait for a message for up to 1 second
                item: Optional[Dict[str, Any]] = self.to_meshtastic_queue.get(timeout=1)
                if not item: # Should not happen with Queue, but safety check
                     continue

                # Check connection status before attempting send
                with self._lock:
                    if not self.interface or not self.interface.is_connected():
                        self.logger.warning("Meshtastic disconnected. Cannot send message. Requeuing (TBD) or Dropping.")
                        # TODO: Implement a mechanism to requeue or handle failed sends better.
                        # For now, just log and discard.
                        self.to_meshtastic_queue.task_done()
                        continue # Skip sending

                    # Extract destination and text payload from the message dict
                    # Assumes message format from Meshcore handler: {'destination': '...', 'text': '...'}
                    destination = item.get('destination')
                    text_to_send = item.get('text')
                    channel_index = item.get('channel_index', 0) # Default to primary channel (0)
                    want_ack = item.get('want_ack', False) # Default to no ACK

                    if destination and isinstance(text_to_send, str):
                        self.logger.info(f"Meshtastic TX -> Dest: {destination}, Chan: {channel_index}, Ack: {want_ack}, Payload: '{text_to_send[:100]}...'") # Log truncated payload
                        try:
                            # Use node ID for destination (e.g., '!a1b2c3d4' or '^all')
                            # Note: sendText handles the node ID lookup internally
                            self.interface.sendText(
                                text=text_to_send,
                                destinationId=destination,
                                channelIndex=channel_index,
                                wantAck=want_ack
                            )
                            # TODO: Handle potential ACK failures if wantAck=True
                            self.to_meshtastic_queue.task_done() # Mark message as processed
                        except meshtastic.MeshtasticError as e:
                             self.logger.error(f"Meshtastic library error sending message: {e}")
                             # Decide if retry is needed or discard
                             self.to_meshtastic_queue.task_done()
                        except Exception as e:
                            self.logger.error(f"Unexpected error sending Meshtastic message: {e}", exc_info=True)
                            # Decide if retry is needed or discard
                            self.to_meshtastic_queue.task_done()
                    else:
                        self.logger.warning(f"Invalid message format in Meshtastic send queue (missing 'destination' or 'text' is not string): {item}")
                        self.to_meshtastic_queue.task_done() # Mark invalid task as done

            except Empty:
                # Queue was empty, timeout occurred. This is normal.
                continue
            except Exception as e:
                # Catch unexpected errors in the sender loop itself
                self.logger.error(f"Critical error in meshtastic_sender_loop: {e}", exc_info=True)
                # Avoid rapid looping on persistent errors
                time.sleep(5)

        self.logger.info("Meshtastic sender loop stopped.")
