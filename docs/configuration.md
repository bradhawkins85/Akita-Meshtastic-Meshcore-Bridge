# Configuration (`config.ini`)

The Akita Meshtastic-Meshcore Bridge (AMMB) uses a configuration file named `config.ini` located in the project's root directory to control its behavior. You should copy `examples/config.ini.example` to `config.ini` and modify it according to your setup.

All settings are currently placed under the `[DEFAULT]` section.

## Settings Details

### Meshtastic Settings

* **`MESHTASTIC_TCP_ADDRESS`**
    * **Description:** Host and port for the Meshtastic TCP service to which the bridge should connect.
    * **Example:** `localhost:4403`, `meshtastic.local:4403`
    * **Finding the address:** Ensure the Meshtastic device is running a TCP interface (e.g., via `meshtasticd`) and note its listening address.
    * **Required:** Yes

* **`MESHTASTIC_TCP_HOST`**
    * **Description:** Hostname or IP address for connecting to a Meshtastic daemon over TCP.
    * **Default:** `127.0.0.1`
    * **Required:** No

* **`MESHTASTIC_TCP_PORT`**
    * **Description:** TCP port for the Meshtastic daemon connection.
    * **Default:** `4403`
    * **Required:** No

### Meshcore Settings

* **`MESHCORE_SERIAL_PORT`**
    * **Description:** The serial port where your MeshCore device is connected.
    * **Example Linux:** `/dev/ttyS0`, `/dev/ttyAMA0` (Raspberry Pi)
    * **Example Windows:** `COM1`, `COM5`
    * **Required:** Yes

* **`MESHCORE_BAUD_RATE`**
    * **Description:** The baud rate (speed) for the serial communication with the MeshCore device. **This must exactly match the baud rate configured on the MeshCore device itself.**
    * **Common Values:** `9600`, `19200`, `38400`, `57600`, `115200`
    * **Default:** `9600`
    * **Required:** Yes

* **`MESHCORE_PROTOCOL`**
    * **Description:** Specifies how messages are formatted when sent and received over the MeshCore serial connection.
    * **Supported Values:**
        * `json_newline`: Messages are expected to be single lines of UTF-8 encoded JSON text, terminated by a newline character (`\n`). This is the default and recommended protocol for structured data exchange. See `docs/architecture.md` for the expected JSON structure.
        * `protobuf`: Messages are newline-delimited binary protobuf using the `MeshcoreMessage` schema.
        * *(Future protocols like `plain_text` could be added)*
    * **Default:** `json_newline`
    * **Required:** Yes (effectively, as the default is used if missing)

* **`MESHCORE_NETWORK_ID`**
    * **Description:** A conceptual identifier for the MeshCore network this bridge is connected to. Currently used primarily for logging purposes but could be incorporated into more advanced translation or routing logic in the future.
    * **Default:** `ammb_default_net`
    * **Required:** No

### Bridge Settings

* **`BRIDGE_NODE_ID`**
    * **Description:** The identifier the bridge uses for itself when interacting on the Meshtastic network. This is primarily used to detect and ignore messages originating from the bridge itself, preventing infinite loops where a message is relayed back and forth.
    * **Format:** It's strongly recommended to use the Meshtastic node ID format (a hexadecimal string starting with `!`, e.g., `!a1b2c3d4`).
    * **Finding your ID:** Use `meshtastic --info` when connected to your device.
    * **Recommendation:** Set this explicitly to the Meshtastic node ID of the device the bridge is running on. If left blank, the bridge attempts to retrieve the ID automatically upon connection, but setting it ensures consistency.
    * **Default:** `!ammb_bridge`
    * **Required:** No (but highly recommended)

* **`MESSAGE_QUEUE_SIZE`**
    * **Description:** The maximum number of messages that can be held in each internal queue (`to_meshtastic` and `to_meshcore`) waiting to be sent. If a message arrives and the corresponding outgoing queue is full, the message will be dropped, and a warning will be logged.
    * **Default:** `100`
    * **Required:** No

### Logging Settings

* **`LOG_LEVEL`**
    * **Description:** Controls the minimum severity level of messages that will be logged to the console.
    * **Supported Values (from least to most verbose):**
        * `CRITICAL`
        * `ERROR`
        * `WARNING`
        * `INFO`
        * `DEBUG`
    * **Default:** `INFO`
    * **Required:** No
