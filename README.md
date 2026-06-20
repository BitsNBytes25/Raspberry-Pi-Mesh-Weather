# Raspberry PI Mesh Weather Sensor

Integrates with MeshCore (or Meshtastic) and Home Assistant for logging local weather data
and providing basic chat support on the Mesh network.

Designed to run on a Raspberry Pi, but should be compatible with any Linux-based device.

**Meshcore only**:
The host device will listen on a "#weather" channel and respond with the current weather data.
Direct messages over the mesh are supported too.

**Meshtastic only**:
The host device will listen on any configured channel for group messages.

This application also supports uploading packets to MQTT servers, for use as observation nodes.


## Expected Hardware

* Raspberry Pi (Zero W or better)
* BME280 Temperature/Humidity/Pressure Sensor
* MeshCore-compatible USB companion device
* Microcenter 1.3" OLED Display (345785)

Refer to our [build guide](https://bitsnbytes.dev/posts/2026-05/pi-mesh-weather-sensor.html)
for details on assembling the hardware for this project and wiring schematics.

![Assembled Hardware](docs/media/raspberry-pi-mesh-radio.webp)


## Installation

```bash
git clone git@github.com:BitsNBytes25/Raspberry-Pi-Mesh-Weather.git
cd Raspberry-Pi-Mesh-Weather

# Copy example configuration and edit as necessary
cp config.yaml.example config.yaml
vim config.yaml

# Run the install script
chmod +x install.sh
./install.sh
```

### Installation on 32-bit OS

Raspberry Pi 2 may ship with a 32-bit operating system; in that case you may need to manually install additional depdendencies.

```bash
# Install a few dependencies for building libraries not included anymore
sudo apt install -y python3-dev libjpeg-dev zlib1g-dev libfreetype6-dev

# One of the dependencies for meshtastic is rust; include that from source.
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## Supported Commands (Weather channel)

* !temperature - Get the current temperature
* !humidity - Get the current humidity
* !pressure - Get the current pressure
* !all - Get temp, humidity, and pressure
* !forecast - Get the 1-day forecast
* !alerts - Get any current weather alerts

![Example Group Chat](docs/media/chat-group.webp)


## Supported Commands (direct message)

* help - Get a list of supported commands
* temperature - Get the current temperature
* humidity - Get the current humidity
* pressure - Get the current pressure
* ping - Ping the device
* uptime - Get the uptime of the device
* cpu - Get the CPU usage of the device
* wake - Wake the device display for 2 minutes
* forecast - Get the 1-day forecast
* alerts - Get any current weather alerts
* 🔒 reboot - Reboot the device
* 🔒 net - Get the current network status

(🔒 denotes commands which require authorization)


![Example Direct Message](docs/media/chat-direct.webp)


## Example Responses

- 🥶 FREEZING! It's 0°C (32°F) - Just stay home and get some hot chocolate!
- 🧊 It's currently 8°C (46°F) - Stay inside or bundle up!
- ☁️ A bit chilly at 12°C (54°F) and rain may be on the horizon.
- ☀️ Perfectly comfortable at 20°C (68°F).  Go out for a nice walk.
- 🥵 It's a hot and muggy 33°C (91°F) but feels like 35°C (95°F).  Take water & limit activity.


## Configuration

Configuration of this application is performed via `config.yaml`.


### Display Configuration

Settings for the hardware display connected to the Raspberry Pi.

| Option      | Type      | Default | Description                                                                          |
|-------------|-----------|---------|--------------------------------------------------------------------------------------|
| enabled     | boolean   | False   | Whether the display is active.                                                       |
| type        | string    | None    | Currently only 'sh1106' is supported                                                 | 
| interface   | string    | 'spi'   | The display interface type. Currently, only "spi" is supported.                      |
| device      | integer   | None    | SPI device ID (typically 0 or 1).                                                    |
| port        | integer   | None    | SPI Port ID.                                                                         |
| dc_gpio     | integer   | None    | Data Command GPIO pin ID.                                                            |
| reset_gpio  | integer   | None    | Reset GPIO pin ID.                                                                   |
| baud_rate   | integer   | None    | The communication baud rate for the display.                                         |
| reset_delay | boolean   | True    | If true, implements a short delay during the reset sequence for compatible displays. |
| rotate      | integer   | None    | Some displays support a rotation metric, generally 0 - 3 or 1 - 4                    |
| width       | integer   | None    | Set the width of the display, generally in characters                                |
| height      | integer   | None    | Set the height of the display, generally in characters                               |

Example:

```yaml
display:
  enabled: true
  interface: spi
  type: sh1106
```


### Radio Configuration

Settings for the primary communication radio hardware.

| Option    | Type    | Default        | Description                                       |
|-----------|---------|----------------|---------------------------------------------------|
| type      | string  | 'meshcore'     | The type of radio hardware (default is meshcore). |
| interface | string  | 'serial'       | The connection method (default is serial).        |
| port      | string  | '/dev/ttyUSB0' | The system path to the serial port.               |
| baud_rate | integer | 115200         | The baud rate for serial communication.           |

Example:

```yaml
radio:
  type: "meshcore"      # Currently only meshcore is supported, here for future use
  interface: "serial"   # Currently only serial is supported, here for future use
  port: "/dev/ttyUSB0"  # Serial port
```

Type can be set to "meshcore" or "meshtastic" based on the type of radio you have


### Sensor Configuration

A list of hardware sensors attached to the Pi. Each entry in the list can have the following keys:

| Option    | Type     | Default  | Description                                   |
|-----------|----------|----------|-----------------------------------------------|
| type      | string   | Required | The model/type of sensor (e.g., bme280).      |
| port      | integer  | None     | The port number for the sensor.               |
| address   | integer  | None     | The hardware address (e.g., 0x76).            |
| baud_rate | integer  | None     | The baud rate for the sensor (if applicable). |

Example:

```yaml
sensors:
  - type: bme280
    port: 1
    address: 0x76
```


### Location Configuration

Geographic data used for weather forecasting and MQTT reporting.

| Option   | Type     | Default  | Description                                                        |
|----------|----------|----------|--------------------------------------------------------------------|
| altitude | integer  | None     | Altitude above sea level in meters (used for barometric pressure). |
| label    | string   | ''       | A friendly name/region label for broadcasts.                       |
| lat      | float    | None     | Latitude coordinate.                                               |
| lon      | float    | None     | Longitude coordinate.                                              |
| iata     | string   | 'XYZ'    | A 3-character airport code used for MQTT reporting on Meshcore.    |
| region   | string   | (auto)   | A 2-character country code for MQTT reporting on Meshtastic        |


Example:

```yaml
location:
  altitude: 250          # Altitude above sea level in meters
  label: "cbus"              # City name or short meaningful region label
  lat: "39.986813574660836"                # Latitude
  lon: "-82.98096688113979"                # Longitude
  iata: CMH
```


### Weather Configuration

API settings for fetching weather data.

| Option              | Type   | Default | Description                       |
|---------------------|--------|---------|-----------------------------------|
| openweather_api_key | string | ''      | Your API key from OpenWeatherMap. |

Example:

```yaml
weather:
  # Obtain OpenWeatherMap API key: https://home.openweathermap.org/api_keys
  openweather_api_key: "1234567890abcdef"
```


### Home Assistant

Configuration for pushing data to a Home Assistant instance.

| Option  | Type   | Default | Description                                            |
|---------|--------|---------|--------------------------------------------------------|
| url     | string | ''      | The Home Assistant URL on your local network.          |
| token   | string | ''      | A long-lived access token for Home Assistant.          |
| icons   | dict   | None    | List of custom icons within Home Asssitant per device. |

Example:

```yaml
home_assistant:
  url: "http://192.168.0.20:30103"
  token: "1234567890abcdef.fedcba0987654321"
```

To configure a custom icon for your device:

```yaml
home_assistant:
  icons:
    12345678: 'mdi:human-greeting-proximity'
```


### Security

**only supported on Meshcore**

| Option      | Type         | Description                                                    |
|-------------|--------------|----------------------------------------------------------------|
| auth_radios | list[string] | A list of Radio IDs permitted to perform administrative tasks. |

Example:

```yaml
auth_radios:          # List of radio IDs allowed for administrative tasks
  - "123412341234"
```

### MQTT Configuration

The system supports multiple MQTT brokers. Each entry in the mqtt list can contain:

| Option          | Type    | Default     | Description                                            |
|-----------------|---------|-------------|--------------------------------------------------------|
| host            | string  | ''          | The hostname or IP of the MQTT broker.                 |
| port            | integer | None        | The port of the MQTT broker (default is usually 1883). |
| usage           | string  | None        | Usage for this MQTT broker                             |
| topic           | string  | (automatic) | The MQTT topic. Supports placeholders like {IATA}.     |
| username        | string  | None        | The username for MQTT authentication.                  |
| password        | string  | None        | The password for MQTT authentication.                  |
| websocket       | boolean | False       | Whether to connect via WebSockets.                     |
| tls             | boolean | False       | Whether to use TLS encryption.                         |
| verify_tls      | boolean | True        | Whether to verify the TLS certificate.                 |
| token           | boolean | False       | Whether to use a Bearer token for authentication.      |
| token_audience  | string  | None        | The audience for the Bearer token.                     |
| token_timeout   | int     | 3600        | Timeout for JWT expiration                             |
| client_prefix   | string  | 'v1'        | A prefix to prepend to the client ID.                  |

Example:

```yaml
mqtt:
  - host: "192.168.0.227"
    port: 1883
    usage: packets
  - host: mqtt1.okimesh.org
    port: 1883
    usage: packets
```

Token authentication is **only supported on Meshcore**.

Ensure to set `usage: packets` for MQTT servers that should receive raw packet feeds.
