# Akita Meshtastic-Meshcore Bridge

This project provides a bridge between Meshtastic and Meshcore networks, enabling seamless communication between the two.

## Features

* **Bidirectional Communication:** Allows messages to be exchanged between Meshtastic and Meshcore networks.
* **Configurable Settings:** Uses a `config.ini` file for easy customization of network settings, serial ports, and logging levels.
* **JSON Data Handling:** Supports JSON formatted messages for flexible data exchange.
* **Binary Meshcore Support (Optional):** Supports binary data transfer for Meshcore networks via configuration.
* **Robust Error Handling:** Includes logging and error handling for reliable operation.
* **Multithreaded Architecture:** Employs multithreading for concurrent message handling.
* **Message Queues:** Uses queues to buffer messages, ensuring no message loss.

## Requirements

* Python 3.6+
* Meshtastic library (`pip install meshtastic`)
* Meshcore network setup (socket accessible)
* A Meshtastic compatible device.

## Installation

1.  Clone the repository (or download the `ammb.py` and `config.ini` files):

    ```bash
    git clone [repository URL]
    cd [repository directory]
    ```

2.  Install the required Python libraries:

    ```bash
    pip install meshtastic
    ```

3.  Configure the `config.ini` file (see Configuration section below).

## Configuration

The `config.ini` file allows you to customize the bridge's settings.

```ini
[DEFAULT]
MESHTASTIC_SERIAL_PORT = /dev/ttyUSB0
MESHCORE_NETWORK_ID = 123
BRIDGE_NODE_ID = 42
MESSAGE_QUEUE_SIZE = 100
RETRY_COUNT = 3
RETRY_DELAY = 1
SENSOR_DATA_FORWARDING = True
PRIORITY_MESSAGES = emergency,alert
LOG_LEVEL = INFO
MESHCORE_HOST = 127.0.0.1
MESHCORE_PORT = 12345
MESHCORE_BINARY_MODE = False
```

* `MESHTASTIC_SERIAL_PORT`: The serial port of your Meshtastic device (e.g., /dev/ttyUSB0, COM3).
* `MESHCORE_NETWORK_ID`: The ID of your Meshcore network.
* `BRIDGE_NODE_ID`: The ID of the bridge node.
* `MESSAGE_QUEUE_SIZE`: The size of the message queues.
* `RETRY_COUNT`: The number of retries for message sending.
* `RETRY_DELAY`: The delay between retries (seconds).
* `SENSOR_DATA_FORWARDING`: Enable/disable sensor data forwarding from Meshcore to Meshtastic (true/false).
* `PRIORITY_MESSAGES`: A comma-separated list of priority message keywords.
* `LOG_LEVEL`: The logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).
* `MESHCORE_HOST`: The host address of the Meshcore network.
* `MESHCORE_PORT`: The port number of the Meshcore network.
* `MESHCORE_BINARY_MODE`: Enable/disable binary Meshcore communication (true/false).

## Usage

* Ensure your Meshtastic device and Meshcore network are running.
* Run the bridge:
  
```bash
python ammb.py
```

* The bridge will start and begin forwarding messages between the networks.

## Meshcore Integration

This bridge uses socket communication for Meshcore integration. The Meshcore network must be accessible via a socket. If `MESHCORE_BINARY_MODE` is enabled, the code will expect binary data according to the structure defined in `meshcore_receive()` and `meshcore_send()`. Please modify these functions to match your specific Meshcore binary protocol.

## Logging

The bridge uses the Python logging module. Log messages are written to the console. The logging level can be configured in the `config.ini` file.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.
