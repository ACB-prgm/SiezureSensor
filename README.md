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
Analysis/export scripts
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
