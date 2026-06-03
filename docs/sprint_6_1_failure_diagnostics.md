# Sprint 6.1 Failure Diagnostics

Sprint 6.1 is a blocking diagnostics sprint before continuing long-run validation. The goal is to make ESP resets, watchdogs, exceptions, Wi-Fi failures, heap pressure, and upload stalls diagnosable from captured logs and persisted telemetry.

## Summary

Every boot and batch should carry enough diagnostic context to answer why a run failed. Live tests should also save decoded serial logs so ESP8266 exception stack traces are not lost when the board reboots.

## Commit Plan

### Commit 1: Firmware Crash And Reset Telemetry

Implement firmware fields in each batch payload:

- `reset_info` from `ESP.getResetInfo()`.
- `uptime_ms` from `millis()` when the batch is sent.
- `last_http_duration_ms`.
- `last_http_status`.
- `consecutive_upload_failures`.
- `wifi_disconnect_count`.
- `min_free_heap`.
- `heap_fragmentation` if supported by the ESP8266 Arduino core.

Also track Wi-Fi disconnect transitions, min heap over the boot lifetime, upload duration/status, and upload failure streak.

Verification:

- PlatformIO build succeeds.
- Serial output prints reset reason, reset info, boot id, and diagnostic counters.
- If the device is available, flash and confirm batches still upload.

### Commit 2: Persist Diagnostics In The API

Implement:

- Extend `POST /api/v1/imu/batch` schema with optional diagnostic fields.
- Add nullable columns to `batches`.
- Add SQLite migration logic for existing databases.
- Persist all new fields.
- Return latest diagnostic values from `/api/v1/status`.

Verification:

- Server tests pass.
- Upload tests cover optional diagnostics.
- Existing SQLite DB migrates successfully.

### Commit 3: Dashboard Diagnostic Status

Show these values in the dashboard status card:

- reset reason and reset info summary
- latest boot id
- uptime
- RSSI and Wi-Fi disconnect count
- free heap, min heap, and heap fragmentation if available
- last HTTP status and upload duration
- upload failure streak
- queue depth, dropped batches, upload skips, and max sample lateness

Highlight risky states:

- reset reason includes `Exception`
- reset reason includes `Watchdog`
- low heap
- upload failure streak greater than zero
- dropped batch count rising

Verification:

- Frontend build passes.
- Dashboard remains responsive while ESP is transmitting.

### Commit 4: Decoded Serial Logging Script

Add `scripts/monitor_esp.sh`.

Defaults:

- Port: `/dev/cu.usbserial-83420` if present.
- Baud: `115200`.
- Firmware dir: `firmware/esp8266_mpu6050_logger`.
- `PLATFORMIO_CORE_DIR`: local firmware core directory.
- Logs under `data/logs/esp/`.

Use PlatformIO monitor filters:

- `esp8266_exception_decoder`
- `log2file`
- `time`

Verification:

- Script starts the monitor.
- Log file is created.
- Missing ESP port fails with a clear message.

### Commit 5: Document Failure Triage Workflow

Document:

- How to start API/dashboard.
- How to start decoded serial logging.
- How to flash and begin a long-run test.
- Meaning of common reset reasons: `External System`, `Hardware Watchdog`, `Exception`.
- What diagnostics to collect before reporting a failure.

Required failure report fields:

- active session id
- boot id
- reset timestamp
- reset reason and reset info
- serial log path
- API status snapshot
- DB boot summary

## Test Plan

- Backend accepts optional diagnostic fields and persists them.
- `/api/v1/status` returns latest diagnostic fields.
- SQLite migration adds new columns to an existing DB.
- Firmware build succeeds.
- Dashboard build succeeds.
- Monitor script starts and creates a log file.

## Definition Of Done

Sprint 6.1 is done when a reset can be diagnosed with:

- which boot reset
- when it reset
- reset reason and reset info
- Wi-Fi stability
- heap state
- HTTP/upload timing
- queue/drop state
- decoded serial exception output when available

## Next Step

Implement firmware telemetry and API persistence first. Those are the minimum required before another meaningful long-run validation run.
