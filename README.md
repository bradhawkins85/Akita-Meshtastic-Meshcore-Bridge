# README.md

# Akita Meshtastic-Meshcore Bridge (AMMB)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
**AMMB is a flexible and robust software bridge designed to facilitate seamless, bidirectional communication between LoRa mesh networks [Meshtastic](https://meshtastic.org/)  and MeshCore (like [`ripplebiz/MeshCore`](https://github.com/ripplebiz/MeshCore)) radio networks.**

This bridge enables interoperability, allowing messages, sensor data (with appropriate translation), and potentially other information to flow between these two distinct low-power, long-range communication systems.

**This bridge has been modified to use on FemtoFox devices and is still in development** we cannot guarantee it works just yet.

---

## Table of Contents

* [Features](#features)
* [How it Works](#how-it-works)
* [Prerequisites](#prerequisites)
* [Installation](#installation)
* [Configuration](#configuration)
* [Running the Bridge](#running-the-bridge)
* [Documentation](#documentation)
* [Testing](#testing)
* [Contributing](#contributing)
* [Disclaimer](#disclaimer)
* [License](#license)

---

## Features

* **Bidirectional Message Forwarding:** Relays messages originating from Meshtastic nodes to the connected MeshCore network, and vice-versa.
* **Direct Serial MeshCore Connection:** Interfaces directly with MeshCore nodes via standard RS-232/USB serial ports, avoiding the need for intermediate network gateways in the base case.
* **~~Reliable~~ Meshtastic Integration:** Leverages the official `meshtastic-python` library, utilizing its asynchronous callback mechanism (`pubsub`) for efficient message reception.
* **Modular & Extensible Design:** Built with separate handlers for each network type (`MeshtasticHandler`, `MeshcoreHandler`) and protocol (`protocol.py`), making it easier to understand, maintain, and extend.
* **Configurable Meshcore Protocol:** Supports different serial communication protocols for MeshCore via the `config.ini` file. Includes a default handler for newline-terminated JSON (`json_newline`), which can be adapted or replaced.
* **Robust Connection Management:** Automatically attempts to reconnect to Meshtastic and MeshCore devices if the serial connection is lost during operation.
* **Graceful Shutdown:** Handles `Ctrl+C` (SIGINT) to cleanly shut down threads, close connections, and exit.
* **Clear Configuration:** Uses a simple `config.ini` file for all settings (ports, baud rates, node IDs, logging levels, protocol selection).
* **Informative Logging:** Provides configurable logging levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) to monitor bridge activity and troubleshoot issues.
* **Basic Message Translation:** Includes foundational logic for translating message formats between the networks (primarily focused on text and basic JSON structures in the default protocol).

---

## How it Works

The bridge operates using several key components working together in separate threads:

1.  **Meshtastic Handler:** Connects to the Meshtastic device, listens for incoming LoRa packets using callbacks, filters out irrelevant or loopback packets, translates valid messages into a standard internal format, and places them on a queue destined for MeshCore. It also has a sender component that takes messages from another queue (originating from MeshCore) and transmits them over the Meshtastic network.
2.  **MeshCore Handler:** Connects to the MeshCore device via serial. A receiver thread continuously reads data from the serial port, uses a selected `Protocol Handler` to decode the incoming bytes (e.g., parse JSON lines), translates the decoded data into the standard internal format, and places it on a queue destined for Meshtastic. A sender thread takes messages from the queue (originating from Meshtastic), uses the `Protocol Handler` to encode them into bytes, and writes them to the MeshCore serial port. It also handles serial errors and reconnection attempts.
3.  **Protocol Handler:** An abstract component responsible for the specifics of encoding/decoding data for the MeshCore serial connection based on the `MESHCORE_PROTOCOL` setting (e.g., `JsonNewlineProtocol`).
4.  **Queues:** Thread-safe queues (`to_meshtastic_queue`, `to_meshcore_queue`) are used to pass messages between the handlers, decoupling the network I/O operations.
5.  **Bridge Orchestrator:** The main class that initializes all handlers, manages threads, and coordinates the startup and shutdown sequences.

For a more detailed explanation of the data flow and components, see the [Architecture Overview](docs/architecture.md).

---

## Prerequisites

* **Hardware:**
    * A computer to run the bridge software (Linux, macOS, Windows).
    * A [Meshtastic compatible device](https://meshtastic.org/docs/hardware) connected via USB.
    * A MeshCore compatible device accessible via a standard serial port (USB-to-Serial adapter may be needed).
* **Software:**
    * [Python](https://www.python.org/) version 3.8 or newer.
    * `pip` (Python package installer, usually included with Python).
    * `git` (for cloning the repository).
    * Appropriate serial port drivers for your operating system and connected devices.

---

## Installation

1.  **Clone the Repository:**
    Open your terminal or command prompt and run:
    ```bash
    git clone [https://github.com/akitaengineering/akita-meshtastic-meshcore-bridge.git](https://github.com/akitaengineering/akita-meshtastic-meshcore-bridge.git)
    cd akita-meshtastic-meshcore-bridge
    ```

2.  **Set up a Python Virtual Environment (Highly Recommended):**
    This isolates the project's dependencies from your system's Python installation.
    ```bash
    python -m venv venv
    ```
    Activate the environment:
    * **Linux / macOS:** `source venv/bin/activate`
    * **Windows (CMD):** `.\venv\Scripts\activate.bat`
    * **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
    You should see `(venv)` prepended to your command prompt line.

3.  **Install Dependencies:**
    With the virtual environment activated, install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

---

## Configuration

The bridge requires a `config.ini` file in the project's root directory.

1.  **Create the Configuration File:**
    Copy the provided example file:
    ```bash
    cp examples/config.ini.example config.ini
    ```

2.  **Edit `config.ini`:**
    Open the newly created `config.ini` file in a text editor and adjust the settings according to your hardware setup:
    * `MESHCORE_SERIAL_PORT`: Set the correct serial port for your MeshCore device (e.g., `/dev/ttyS0`, `COM4`).
    * `MESHCORE_BAUD_RATE`: **Crucially, set this to match the baud rate configured on your MeshCore device.** (e.g., `9600`, `115200`).
    * `MESHCORE_PROTOCOL`: Select the protocol handler matching how your MeshCore device communicates. `json_newline` is the default. Set to `companion_frame` for the binary companion-radio frames defined in the MeshCore wiki.
    * `BRIDGE_NODE_ID`: **Recommended:** Set this to the actual Meshtastic Node ID (e.g., `!a1b2c3d4`) of the device running the bridge to prevent message loops. Use `meshtastic --info` to find your ID.
    * `LOG_LEVEL`: Adjust logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). `INFO` is a good starting point.

    Refer to the detailed [**Configuration Guide (docs/configuration.md)**](docs/configuration.md) for explanations of all available settings.

---

## Running the Bridge

1.  **Ensure Prerequisites Met:** Verify both Meshtastic and MeshCore devices are connected and powered on.
2.  **Activate Virtual Environment:** If not already active, activate it (`source venv/bin/activate` or `.\venv\Scripts\activate`).
3.  **Navigate to Project Directory:** Make sure your terminal is in the root directory of the cloned project (where `run_bridge.py` is located).
4.  **Execute the Script:**
    ```bash
    python run_bridge.py
    ```

The bridge will start, attempt to connect to the devices, and begin logging its activity to the console. If connections are successful, it will start relaying messages between the networks.

**To stop the bridge, press `Ctrl+C` in the terminal.** It will perform a graceful shutdown.

See the [**Usage Guide (docs/usage.md)**](docs/usage.md) for more details on monitoring and troubleshooting.

---

## Documentation

This project includes detailed documentation in the `docs/` directory:

* [**Configuration Details (`docs/configuration.md`)**](docs/configuration.md): In-depth explanation of every setting in `config.ini`.
* [**Usage Guide (`docs/usage.md`)**](docs/usage.md): Instructions on running, monitoring, and troubleshooting the bridge.
* [**Architecture Overview (`docs/architecture.md`)**](docs/architecture.md): Explanation of the internal components, data flow, threading model, and assumed communication protocols.
* [**Development & Contribution Guide (`docs/development.md`)**](docs/development.md): Information for developers wanting to modify the code, run tests, or contribute back to the project.

---

## Testing

The project includes a test suite using `pytest`. To run the tests:

1.  **Install development dependencies:**
    ```bash
    pip install -r requirements-dev.txt
    ```
2.  **Run pytest from the project root directory:**
    ```bash
    pytest
    ```
    For test coverage details:
    ```bash
    pytest --cov=ammb
    ```

See the [Development Guide](docs/development.md) for more testing information.

---

## Contributing

Contributions, bug reports, and feature requests are welcome! Please follow these steps:

1.  Review the [**Development & Contribution Guide (`docs/development.md`)**](docs/development.md).
2.  Check for existing [Issues](https://github.com/YOUR_USERNAME/akita-meshtastic-meshcore-bridge/issues) or open a new one to discuss your proposed changes.
3.  Fork the repository, create a feature branch, make your changes, and submit a Pull Request.

---

## Disclaimer

**Protocol Compatibility:** This bridge's ability to communicate with a MeshCore device fundamentally depends on the serial protocol used by that device. The bridge provides a framework and a default implementation (`json_newline`) assuming specific newline-terminated JSON structures (detailed in `docs/architecture.md`). **You MUST verify that your MeshCore device's serial communication format matches the selected `MESHCORE_PROTOCOL` handler.** If it doesn't, you will need to adapt the existing protocol handler or create a new one in `ammb/protocol.py`.

**"As Is":** This software is provided "as is", without warranty of any kind. Use it at your own risk. Ensure you understand its operation and limitations before deploying it in critical scenarios.

---

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for the full license text.
