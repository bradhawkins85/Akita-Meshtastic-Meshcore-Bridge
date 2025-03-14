# ammb.py - Akita Meshtastic-Meshcore Bridge

import time
import json
import threading
from queue import Queue
from meshtastic import meshtastic, serial_interface
import logging
import configparser
import os
import socket
import struct

# Configuration
config = configparser.ConfigParser()
config_file = "config.ini"

if not os.path.exists(config_file):
    config['DEFAULT'] = {
        'MESHTASTIC_SERIAL_PORT': '/dev/ttyUSB0',
        'MESHCORE_NETWORK_ID': '123',
        'BRIDGE_NODE_ID': '42',
        'MESSAGE_QUEUE_SIZE': '100',
        'RETRY_COUNT': '3',
        'RETRY_DELAY': '1',
        'SENSOR_DATA_FORWARDING': 'True',
        'PRIORITY_MESSAGES': 'emergency,alert',
        'LOG_LEVEL': 'INFO',
        'MESHCORE_HOST': '127.0.0.1',
        'MESHCORE_PORT': '12345',
        'MESHCORE_BINARY_MODE': 'False',
    }
    with open(config_file, 'w') as configfile:
        config.write(configfile)

config.read(config_file)

MESHTASTIC_SERIAL_PORT = config['DEFAULT']['MESHTASTIC_SERIAL_PORT']
MESHCORE_NETWORK_ID = int(config['DEFAULT']['MESHCORE_NETWORK_ID'])
BRIDGE_NODE_ID = int(config['DEFAULT']['BRIDGE_NODE_ID'])
MESSAGE_QUEUE_SIZE = int(config['DEFAULT']['MESSAGE_QUEUE_SIZE'])
RETRY_COUNT = int(config['DEFAULT']['RETRY_COUNT'])
RETRY_DELAY = int(config['DEFAULT']['RETRY_DELAY'])
SENSOR_DATA_FORWARDING = config['DEFAULT'].getboolean('SENSOR_DATA_FORWARDING')
PRIORITY_MESSAGES = [p.strip() for p in config['DEFAULT']['PRIORITY_MESSAGES'].split(',')]
LOG_LEVEL = config['DEFAULT']['LOG_LEVEL']
MESHCORE_HOST = config['DEFAULT']['MESHCORE_HOST']
MESHCORE_PORT = int(config['DEFAULT']['MESHCORE_PORT'])
MESHCORE_BINARY_MODE = config['DEFAULT'].getboolean('MESHCORE_BINARY_MODE')

# Logging Setup
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

# Message Queues
meshtastic_queue = Queue(maxsize=MESSAGE_QUEUE_SIZE)
meshcore_queue = Queue(maxsize=MESSAGE_QUEUE_SIZE)

# Meshtastic Setup
try:
    interface = serial_interface.SerialInterface(MESHTASTIC_SERIAL_PORT)
    logging.info(f"Connected to Meshtastic device on {MESHTASTIC_SERIAL_PORT}")
except Exception as e:
    logging.error(f"Error connecting to Meshtastic device: {e}")
    exit(1)

# Meshcore Setup
try:
    meshcore_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    logging.info(f"Connected to Meshcore network on {MESHCORE_HOST}:{MESHCORE_PORT}")
except Exception as e:
    logging.error(f"Error connecting to Meshcore network: {e}")
    exit(1)

# Meshtastic Message Handling
def meshtastic_receive():
    try:
        msg = interface.receive(blocking=False)
        if msg and msg["decoded"]["portnum"] == "TEXT_MESSAGE_APP":
            return msg["decoded"]
    except Exception as e:
        logging.error(f"Error receiving Meshtastic message: {e}")
    return None

def meshtastic_send(data, destination):
    try:
        interface.sendText(data, destination)
        logging.info(f"Meshtastic: Sent '{data}' to {destination}")
    except Exception as e:
        logging.error(f"Error sending Meshtastic message: {e}")

# Meshcore Message Handling
def meshcore_receive():
    try:
        meshcore_socket.settimeout(0.1)
        data, addr = meshcore_socket.recvfrom(1024)

        if MESHCORE_BINARY_MODE:
            source, sensor_value, sensor_type = struct.unpack("!iif", data)
            message = {"source": source, "data": {"sensor_value": sensor_value, "sensor_type": sensor_type}}
        else:
            message = json.loads(data.decode())

        return message
    except socket.timeout:
        return None
    except Exception as e:
        logging.error(f"Error receiving Meshcore message: {e}")
        return None

def meshcore_send(data, destination):
    try:
        if MESHCORE_BINARY_MODE:
            packed_data = struct.pack("!ifi", data['source'], data['data']['sensor_value'], data['data']['sensor_type'])
            meshcore_socket.sendto(packed_data, (MESHCORE_HOST, MESHCORE_PORT))
        else:
            message = json.dumps(data).encode()
            meshcore_socket.sendto(message, (MESHCORE_HOST, MESHCORE_PORT))
        logging.info(f"Meshcore: Sent '{data}' to {destination}")
    except Exception as e:
        logging.error(f"Error sending Meshcore message: {e}")

# Translation Functions
def translate_meshtastic_to_meshcore(meshtastic_message):
    try:
        payload = json.loads(meshtastic_message["text"])
        meshcore_data = {
            "source": BRIDGE_NODE_ID,
            "data": payload,
            "timestamp": time.time(),
        }
        return meshcore_data
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error translating Meshtastic message: {e}")
        return None

def translate_meshcore_to_meshtastic(meshcore_message):
    meshtastic_data = {
        "from": BRIDGE_NODE_ID,
        "text": json.dumps(meshcore_message["data"]),
        "timestamp": meshcore_message["timestamp"],
    }
    return meshtastic_data

# Receiver Threads
def meshtastic_receiver():
    while True:
        msg = meshtastic_receive()
        if msg:
            meshtastic_queue.put(msg)
        time.sleep(0.1)

def meshcore_receiver():
    while True:
        msg = meshcore_receive()
        if msg:
            meshcore_queue.put(msg)
        time.sleep(0.1)

# Message Processor Thread
def message_processor():
    while True:
        if not meshtastic_queue.empty():
            meshtastic_msg = meshtastic_queue.get()
            meshcore_msg = translate_meshtastic_to_meshcore(meshtastic_msg)
            if meshcore_msg:
                meshcore_send(meshcore_msg, 0)

        if not meshcore_queue.empty():
            meshcore_msg = meshcore_queue.get()
            meshtastic_msg = translate_meshcore_to_meshtastic(meshcore_msg)
            meshtastic_send(meshtastic_msg["text"], meshtastic_msg["from"])

        time.sleep(0.05)

# Main Function
def main():
    logging.info("Akita Meshtastic-Meshcore Bridge started!")

    threading.Thread(target=meshtastic_receiver, daemon=True).start()
    threading.Thread(target=meshcore_receiver, daemon=True).start()
    threading.Thread(target=message_processor, daemon=True).start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
