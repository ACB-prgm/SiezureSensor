#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIRMWARE_DIR="${FIRMWARE_DIR:-"$ROOT_DIR/firmware/esp8266_mpu6050_logger"}"
PLATFORMIO_CORE_DIR="${PLATFORMIO_CORE_DIR:-"$FIRMWARE_DIR/.platformio-core"}"
BAUD="${BAUD:-115200}"
LOG_DIR="${LOG_DIR:-"$ROOT_DIR/data/logs/esp"}"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
LOG_FILE="${LOG_FILE:-"$LOG_DIR/esp_monitor_$TIMESTAMP.log"}"
PIO="${PIO:-pio}"

find_default_port() {
  local preferred="/dev/cu.usbserial-83420"
  if [[ -e "$preferred" ]]; then
    printf '%s\n' "$preferred"
    return 0
  fi

  local candidate
  for candidate in /dev/cu.usbserial-* /dev/cu.SLAB_USBtoUART* /dev/cu.wchusbserial*; do
    if [[ -e "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if ! command -v "$PIO" >/dev/null 2>&1; then
  echo "PlatformIO CLI was not found. Set PIO=/path/to/pio or install PlatformIO." >&2
  exit 1
fi

PORT="${PORT:-}"
if [[ -z "$PORT" ]]; then
  if ! PORT="$(find_default_port)"; then
    echo "No ESP serial port found. Set PORT=/dev/cu.usbserial-... and rerun." >&2
    exit 1
  fi
fi

mkdir -p "$LOG_DIR"

echo "Firmware dir: $FIRMWARE_DIR"
echo "Port: $PORT"
echo "Baud: $BAUD"
echo "Log file: $LOG_FILE"
echo "Stop monitor with Ctrl-C."

export PLATFORMIO_CORE_DIR
cd "$FIRMWARE_DIR"

"$PIO" device monitor \
  --port "$PORT" \
  --baud "$BAUD" \
  --filter time \
  --filter esp8266_exception_decoder \
  --filter log2file \
  | tee "$LOG_FILE"
