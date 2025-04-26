# examples/meshcore_simulator.py
"""
Simple Meshcore Serial Device Simulator.

This script opens a specified serial port and acts as a basic Meshcore device
that communicates using the newline-terminated JSON protocol expected by the AMMB.

Features:
- Listens for incoming JSON lines from the bridge.
- Prints received messages.
- Allows you to manually type and send JSON messages *to* the bridge.
- Sends periodic simulated sensor readings (optional).

Usage:
1. Find two connected serial ports (e.g., using a USB-to-Serial adapter loopback
   or virtual serial port software like `socat` on Linux or `com0com` on Windows).
2. Configure one port in this simulator script (SIMULATOR_PORT).
3. Configure the *other* port as `MESHCORE_SERIAL_PORT` in the bridge's `config.ini`.
4. Run this simulator script.
5. Run the main bridge script (`run_bridge.py`).

Example virtual ports with socat (Linux):
socat -d -d pty,raw,echo=0,link=/tmp/ttyV0 pty,raw,echo=0,link=/tmp/ttyV1
# Use /tmp/ttyV0 for the simulator and /tmp/ttyV1 for the bridge (or vice-versa).
"""

import serial
import time
import json
import threading
import sys
import random

# --- Configuration ---
SIMULATOR_PORT = "/dev/ttyS1"  # <<< CHANGE THIS to your simulator's serial port
BAUD_RATE = 9600             # <<< MUST MATCH bridge's MESHCORE_BAUD_RATE
SEND_PERIODIC_SENSOR_DATA = True # Set to True to send simulated sensor data
SENSOR_INTERVAL_S = 15       # Interval in seconds to send sensor data

# --- Global Variables ---
shutdown_event = threading.Event()
serial_port: serial.Serial | None = None

# --- Serial Reading Thread ---
def serial_reader():
    """Reads lines from the serial port and prints them."""
    global serial_port
    print("[Reader] Serial reader thread started.")
    while not shutdown_event.is_set():
        if serial_port and serial_port.is_open:
            try:
                if serial_port.in_waiting > 0:
                    line = serial_port.readline()
                    if line:
                        try:
                            decoded_line = line.decode('utf-8').strip()
                            print(f"\n[Reader] <<< Received from Bridge: {decoded_line}")
                            # Try parsing JSON for validation
                            try:
                                 data = json.loads(decoded_line)
                                 print(f"[Reader]     (Parsed JSON: {data})")
                            except json.JSONDecodeError:
                                 print("[Reader]     (Warning: Not valid JSON)")
                        except UnicodeDecodeError:
                            print(f"\n[Reader] <<< Received non-UTF8 data: {line!r}")
                    else:
                        # readline() timed out (can happen if timeout is set)
                        pass
                else:
                    # No data waiting, sleep briefly
                    time.sleep(0.1)
            except serial.SerialException as e:
                print(f"\n[Reader] Serial error: {e}. Closing port.")
                if serial_port:
                    serial_port.close()
                serial_port = None # Signal main loop to reconnect
                time.sleep(2) # Wait before allowing reconnect attempt
            except Exception as e:
                 print(f"\n[Reader] Unexpected error: {e}")
                 time.sleep(1)
        else:
            # Port is not open, wait
            time.sleep(1)
    print("[Reader] Serial reader thread stopped.")

# --- Periodic Sender Thread ---
def periodic_sender():
    """Sends simulated sensor data periodically."""
    print("[Periodic Sender] Started.")
    target_meshtastic_node = "!aabbccdd" # Example target node ID for sensor data

    while not shutdown_event.is_set():
        if serial_port and serial_port.is_open:
            try:
                # Simulate sensor reading
                sensor_value = round(20 + random.uniform(-2, 2), 2)
                message = {
                    "destination_meshtastic_id": target_meshtastic_node,
                    "payload_json": { # Send structured data example
                        "sensor_type": "temperature",
                        "value": sensor_value,
                        "unit": "C"
                    }
                }
                message_str = json.dumps(message) + '\n'
                print(f"\n[Periodic Sender] >>> Sending simulated sensor data: {message_str.strip()}")
                serial_port.write(message_str.encode('utf-8'))
            except serial.SerialException as e:
                 print(f"\n[Periodic Sender] Serial error sending: {e}")
                 # Let reader thread handle reconnect
            except Exception as e:
                 print(f"\n[Periodic Sender] Error sending: {e}")

        # Wait for the interval, checking shutdown event periodically
        shutdown_event.wait(SENSOR_INTERVAL_S)

    print("[Periodic Sender] Stopped.")


# --- Main Loop ---
def main():
    global serial_port
    print("--- Meshcore Serial Simulator ---")
    print(f"Configured Port: {SIMULATOR_PORT}")
    print(f"Baud Rate: {BAUD_RATE}")
    print("Type JSON messages to send to the bridge and press Enter.")
    print("Example: {\"destination_meshtastic_id\": \"^all\", \"payload\": \"Hello from simulator!\"}")
    print("Press Ctrl+C to exit.")

    # Start reader thread
    reader = threading.Thread(target=serial_reader, daemon=True)
    reader.start()

    # Start periodic sender if enabled
    if SEND_PERIODIC_SENSOR_DATA:
         sender = threading.Thread(target=periodic_sender, daemon=True)
         sender.start()

    while not shutdown_event.is_set():
        # --- Connection Management ---
        if not serial_port or not serial_port.is_open:
            print(f"\n[Main] Attempting to open serial port {SIMULATOR_PORT}...")
            try:
                serial_port = serial.Serial(SIMULATOR_PORT, BAUD_RATE, timeout=0.5) # Short timeout for reads
                print(f"[Main] Serial port {SIMULATOR_PORT} opened successfully.")
            except serial.SerialException as e:
                print(f"[Main] Failed to open serial port: {e}")
                print("[Main] Retrying in 5 seconds...")
                time.sleep(5)
                continue # Retry connection
            except Exception as e:
                 print(f"[Main] Unexpected error opening port: {e}")
                 time.sleep(5)
                 continue

        # --- User Input for Sending ---
        try:
            # Use input() which blocks, allowing threads to run
            user_input = input("\n[User Input] >>> Send JSON: ")
            if user_input:
                # Validate if it's JSON before sending (optional but helpful)
                try:
                     json.loads(user_input) # Try parsing
                     message_bytes = user_input.encode('utf-8') + b'\n'
                     if serial_port and serial_port.is_open:
                         serial_port.write(message_bytes)
                         print("[User Input]     Message sent.")
                     else:
                          print("[User Input]     Error: Serial port not open.")
                except json.JSONDecodeError:
                     print("[User Input]     Error: Input is not valid JSON. Message not sent.")
                except serial.SerialException as e:
                     print(f"[User Input]     Serial error sending: {e}")
                     # Let reader thread handle reconnect
                except Exception as e:
                     print(f"[User Input]     Error sending: {e}")

        except EOFError:
            # Handle case where input stream is closed (e.g., piping input)
            print("\n[Main] EOF received, shutting down.")
            break
        except KeyboardInterrupt:
             print("\n[Main] Ctrl+C detected, shutting down.")
             break # Exit main loop

    # --- Shutdown ---
    shutdown_event.set()
    print("[Main] Waiting for threads to stop...")
    reader.join(timeout=2)
    if SEND_PERIODIC_SENSOR_DATA:
         sender.join(timeout=2)

    if serial_port and serial_port.is_open:
        print("[Main] Closing serial port.")
        serial_port.close()

    print("--- Simulator Exited ---")

if __name__ == "__main__":
    main()
