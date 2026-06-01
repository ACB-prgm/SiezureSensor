# Dog Seizure Sensor V0

V0 is a data acquisition and labeling system for collecting raw IMU data from a dog-mounted sensor. It is not a seizure detector, medical alerting device, or machine learning system.

## Hardware

- ESP8266 ESP-12F / NodeMCU-style development board
- GY-521 / MPU-6050 IMU
- USB serial cable
- Local Wi-Fi network for later batch upload work

## Architecture

```text
MPU-6050
  -> I2C
ESP8266 firmware
  -> Wi-Fi HTTP POST
FastAPI server
  -> SQLite database
React labeling workbench + analysis/export scripts
```

## Local Server Setup

From the repository root:

```sh
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m pytest
uvicorn app.main:app --reload
```

The server creates its SQLite database at `../data/seizure_sensor_v0.sqlite` by default. Override this with `SEIZURE_SENSOR_DB_PATH` for tests or alternate local runs.

## Sprint 2 Data Review Workflow

Create a manual event label after a session exists:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "2026-05-23T20-15-00-beanie-v0-001",
    "event_type": "scratching",
    "severity": 2,
    "start_device_ms": 184240,
    "end_device_ms": 188000,
    "source": "manual",
    "notes": "short scratching window"
  }'
```

Export samples through the API:

```sh
curl 'http://127.0.0.1:8000/api/v1/export/samples?session_id=2026-05-23T20-15-00-beanie-v0-001' \
  -o data/exports/session_samples.csv
```

Export a labeled session from SQLite:

```sh
python analysis/scripts/export_session.py \
  --db-path data/seizure_sensor_v0.sqlite \
  --session-id 2026-05-23T20-15-00-beanie-v0-001 \
  --include-labels
```

Generate review plots:

```sh
python analysis/scripts/plot_session.py \
  --db-path data/seizure_sensor_v0.sqlite \
  --session-id 2026-05-23T20-15-00-beanie-v0-001

python analysis/scripts/plot_event.py \
  --db-path data/seizure_sensor_v0.sqlite \
  --event-id 1 \
  --padding-ms 5000
```

Exports are written to `data/exports/` by default. Plots are written to `data/plots/` as PNG files.

## Sprint 4 Labeling Workbench

The local labeling workbench is a browser UI for visually inspecting sessions and creating event labels.

Start all local services from the repository root:

```sh
./scripts/start_services.sh
```

The script starts FastAPI on `0.0.0.0:8000` and the workbench on `0.0.0.0:5173`, waits until both are reachable, prints local and LAN URLs, and stops child processes when you press `Ctrl+C`.

If you want to start services manually, start the API:

```sh
cd server
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Start the workbench:

```sh
cd web/labeling_workbench
npm install
npm run dev
```

Open `http://127.0.0.1:5173` on the server Mac, or `http://192.168.0.114:5173` from another device on the same LAN.

The workbench lets you:

- select a recorded session
- see whether the FastAPI service is online, offline, or actively receiving samples
- start or stop the local FastAPI service from the dashboard when using the Vite dev server
- view accel, gyro, accel magnitude, and gyro magnitude on a timeline
- pan with horizontal scrolling or the horizontal slider
- zoom with vertical scrolling, trackpad zoom, or the `+` / `-` controls
- adjust signal amplitude with the vertical scale slider
- click `Select range`, drag across the timeline, adjust range handles, and save a label
- enter start/end hour, minute, and second values without changing the label date
- edit or delete existing labels
- create a new empty session before collecting data

By default, the workbench calls the API on the same hostname at port `8000`. Set `VITE_API_BASE_URL` if the API is somewhere else.

The Start/Stop API buttons are local-development controls provided by the Vite dev server at `/__dev/api/*`. They are intentionally not part of the production FastAPI API. Stop is only available for API processes started by the dashboard; if you started FastAPI manually in a terminal, stop it from that terminal.

## Sprint 3 Device Upload Workflow

Create private firmware config:

```sh
cp firmware/esp8266_mpu6050_logger/include/config.example.h \
  firmware/esp8266_mpu6050_logger/include/config.h
```

Edit `config.h` with your Wi-Fi credentials, LAN server URL, device ID, and firmware version. `SERVER_URL` should not include a trailing slash. Recording sessions are assigned by the server, not the ESP.

Start the server on the LAN:

```sh
cd server
. .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Flash and monitor the firmware:

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

Expected successful upload response:

```json
{"status":"ok","device_id":"beanie-v0-001","sequence":0,"samples_received":50}
```

If uploads fail, check that `SERVER_URL` points at the Mac's LAN API URL and that `./scripts/start_services.sh` is running. Sequence numbers restart at `0` on firmware reboot, but the server separates reboots by `boot_id`.

## Firmware Setup

The ESP8266 firmware lives in `firmware/esp8266_mpu6050_logger`.

```sh
cd firmware/esp8266_mpu6050_logger
PLATFORMIO_CORE_DIR=/Users/aaronbastian/Code/SiezureSensor/.platformio-core \
  /Users/aaronbastian/Code/SiezureSensor/.venv-platformio/bin/pio run
```

The current firmware bench build initializes the MPU-6050 and prints accelerometer and gyroscope readings at approximately 50 Hz.

## V0 Limitations

- No seizure detection.
- No medical alerting.
- No BLE.
- No mobile app.
- No battery optimization.
- No ML model training.
- Raw IMU data reliability is prioritized over power consumption and enclosure work.
