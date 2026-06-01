# Sprint 3 Device Upload Workflow

Sprint 3 implements the ESP8266 real-device upload loop for `M8.1-M8.3`.

## Configure Firmware

Create a private config file:

```sh
cp firmware/esp8266_mpu6050_logger/include/config.example.h \
  firmware/esp8266_mpu6050_logger/include/config.h
```

Edit `config.h`:

```cpp
#define WIFI_SSID "your-wifi-ssid"
#define WIFI_PASSWORD "your-wifi-password"
#define SERVER_URL "http://192.168.1.100:8000"
#define DEVICE_ID "beanie-v0-001"
#define FIRMWARE_VERSION "0.1.0"
```

Rules:

- `config.h` is ignored by Git and must not be committed.
- `SERVER_URL` should not include a trailing slash.
- Recording sessions are assigned by the server; the ESP only sends `device_id`, `boot_id`, sequence, timing, and diagnostics.
- `battery_mv` is sent as JSON `null` in V0.

## Start Server

From `server/`:

```sh
. .venv/bin/activate
python -m pytest
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify locally:

```sh
curl http://127.0.0.1:8000/health
```

The ESP8266 must use the Mac's LAN IP in `SERVER_URL`, not `127.0.0.1`.

## Flash And Monitor

```sh
cd firmware/esp8266_mpu6050_logger
PLATFORMIO_CORE_DIR=/Users/aaronbastian/Code/SiezureSensor/.platformio-core \
  /Users/aaronbastian/Code/SiezureSensor/.venv-platformio/bin/pio run \
  --target upload \
  --upload-port /dev/cu.usbserial-83420

PLATFORMIO_CORE_DIR=/Users/aaronbastian/Code/SiezureSensor/.platformio-core \
  /Users/aaronbastian/Code/SiezureSensor/.venv-platformio/bin/pio device monitor \
  --port /dev/cu.usbserial-83420 \
  --baud 115200
```

Expected serial behavior:

- MPU-6050 initializes.
- ESP8266 prints Wi-Fi state and local IP when connected.
- Firmware prepares 50-sample batches at the 50 Hz sample cadence.
- Firmware prioritizes sampling before upload and skips upload attempts that are too close to the next sample deadline.
- Firmware posts JSON to `{SERVER_URL}/api/v1/imu/batch`.
- Firmware prints HTTP status and server response.
- If Wi-Fi or upload fails, firmware keeps unsent batches in a bounded RAM queue and drops the oldest batch if the queue fills.
- Timing diagnostics include queue depth, dropped batch count, max sample lateness, and upload skip count.

Successful response example:

```json
{"status":"ok","device_id":"beanie-v0-001","sequence":0,"samples_received":50}
```

## Verify Stored Data

Use the export API:

```sh
curl 'http://127.0.0.1:8000/api/v1/export/samples?session_id=2026-05-25T08-00-00-beanie-v0-001' \
  -o data/exports/upload_test.csv
```

Or inspect SQLite:

```sh
sqlite3 data/seizure_sensor_v0.sqlite \
  'select sequence, sample_count from batches order by id desc limit 5;'
```

Each successful firmware upload should create one batch row and 50 IMU sample rows.

## Pending Sprint 6 Validation

The current sampling-priority upload loop is build-verified only until the ESP can be flashed again. Sprint 6 must confirm on hardware that inter-sample gaps stay near 20 ms during live upload and that `max_sample_lateness_ms` remains acceptable.
