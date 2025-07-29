# ammb/protocol.py
"""
Defines handlers for different Meshcore serial communication protocols.

Allows the bridge to encode/decode messages based on the protocol
specified in the configuration (e.g., newline-terminated JSON).
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any

# --- Base Class ---
class MeshcoreProtocolHandler(ABC):
    """
    Abstract base class for handling Meshcore serial protocols.

    Subclasses must implement encode and decode methods for a specific protocol.
    """
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.debug("Protocol handler initialized.")

    @abstractmethod
    def encode(self, data: Dict[str, Any]) -> Optional[bytes]:
        """
        Encodes a dictionary payload into bytes suitable for sending over serial.

        Args:
            data: The dictionary containing the message payload.

        Returns:
            The encoded message as bytes, or None if encoding fails.
        """
        pass

    @abstractmethod
    def decode(self, line: bytes) -> Optional[Dict[str, Any]]:
        """
        Decodes bytes received from serial (typically a line) into a dictionary.

        Args:
            line: The bytes received from the serial port.

        Returns:
            A dictionary representing the decoded message, or None if decoding fails
            or the line is invalid/incomplete for the protocol.
        """
        pass

# --- Concrete Implementations ---

class JsonNewlineProtocol(MeshcoreProtocolHandler):
    """
    Handles newline-terminated JSON strings encoded in UTF-8.

    Assumes each complete message received from serial is a single line
    containing a valid JSON object. Sends messages as JSON strings
    followed by a newline character.
    """
    def encode(self, data: Dict[str, Any]) -> Optional[bytes]:
        """Encodes dictionary to a UTF-8 JSON string followed by a newline."""
        try:
            # Add newline character for line-based reading on the other end
            encoded_message = json.dumps(data).encode('utf-8') + b'\n'
            self.logger.debug(f"Encoded: {encoded_message!r}") # Use !r for unambiguous representation
            return encoded_message
        except (TypeError, ValueError) as e:
            self.logger.error(f"JSON Encode Error: {e} - Data: {data}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Unexpected encoding error: {e}", exc_info=True)
            return None

    def decode(self, line: bytes) -> Optional[Dict[str, Any]]:
        """Decodes a single line of UTF-8 bytes into a dictionary via JSON."""
        try:
            # Strip potential whitespace/newlines before parsing
            # Decode assuming UTF-8, ignore errors for logging robustness
            decoded_str = line.decode('utf-8', errors='ignore').strip()
            if not decoded_str: # Ignore empty lines resulting from stripping
                self.logger.debug("Ignoring empty line.")
                return None

            self.logger.debug(f"Attempting to decode JSON: {decoded_str}")
            decoded_data = json.loads(decoded_str)
            if not isinstance(decoded_data, dict):
                 self.logger.warning(f"Decoded JSON is not a dictionary: {type(decoded_data)}")
                 return None # Expecting a dictionary structure

            self.logger.debug(f"Decoded successfully: {decoded_data}")
            return decoded_data

        except json.JSONDecodeError:
            self.logger.warning(f"Received non-JSON data or incomplete JSON line: {decoded_str!r}")
            return None
        except UnicodeDecodeError:
            # This case might be less common if errors='ignore' is used, but good to have
            self.logger.warning(f"Received non-UTF8 data: {line!r}")
            return None
        except Exception as e:
            # Catch other potential errors during decoding/processing
            self.logger.error(f"Error decoding Meshcore data: {e} - Raw line: {line!r}", exc_info=True)
            return None

class CompanionFrameProtocol(MeshcoreProtocolHandler):
    """Handle binary frames used by the MeshCore companion radio."""

    def encode(self, data: Dict[str, Any]) -> Optional[bytes]:
        self.logger.error("Encoding not implemented for CompanionFrameProtocol")
        return None

    def decode(self, frame: bytes) -> Optional[Dict[str, Any]]:
        if not frame or len(frame) < 4:
            return None

        start = frame[0]
        if start not in (0x3E, 0x3C):
            self.logger.warning(f"Invalid frame start byte: {start:#x}")
            return None

        length = int.from_bytes(frame[1:3], "little")
        payload = frame[3:3 + length]

        if len(payload) < length:
            self.logger.warning(
                f"Incomplete frame: expected {length} bytes payload, got {len(payload)}"
            )
            return None

        msg: Dict[str, Any] = {
            "direction": "outbound" if start == 0x3E else "inbound",
            "code": payload[0],
        }

        code = payload[0]

        try:
            if code == 7 and length >= 13:
                msg.update({
                    "pubkey_prefix": payload[1:7].hex(),
                    "path_len": payload[7],
                    "txt_type": payload[8],
                    "sender_timestamp": int.from_bytes(payload[9:13], "little"),
                    "text": payload[13:length].decode("utf-8", errors="ignore"),
                })
            elif code == 8 and length >= 9:
                msg.update({
                    "channel_idx": payload[1],
                    "path_len": payload[2],
                    "txt_type": payload[3],
                    "sender_timestamp": int.from_bytes(payload[4:8], "little"),
                    "text": payload[8:length].decode("utf-8", errors="ignore"),
                })
            else:
                msg["payload"] = payload[1:length].hex()
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Failed to decode Companion frame: {exc}", exc_info=True)
            return None

        return msg

# --- Factory Function ---

# Store registered protocol handlers
_protocol_handlers = {
    'json_newline': JsonNewlineProtocol,
    'companion_frame': CompanionFrameProtocol,
}

def get_protocol_handler(protocol_name: str) -> MeshcoreProtocolHandler:
    """
    Factory function to get an instance of the appropriate protocol handler.

    Args:
        protocol_name: The name of the protocol (e.g., 'json_newline').

    Returns:
        An instance of the corresponding MeshcoreProtocolHandler subclass.

    Raises:
        ValueError: If the requested protocol_name is not registered.
    """
    logger = logging.getLogger(__name__)
    protocol_name_lower = protocol_name.lower()

    handler_class = _protocol_handlers.get(protocol_name_lower)

    if handler_class:
        logger.info(f"Using Meshcore protocol handler: {handler_class.__name__}")
        return handler_class()
    else:
        logger.error(f"Unsupported Meshcore protocol specified: '{protocol_name}'.")
        logger.error(f"Available protocols: {list(_protocol_handlers.keys())}")
        # Defaulting strategy (optional):
        # logger.warning("Defaulting to 'json_newline' protocol.")
        # return JsonNewlineProtocol()
        # Or raise error:
        raise ValueError(f"Unsupported Meshcore protocol: {protocol_name}")

