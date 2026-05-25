# Sprint Roadmap

This roadmap groups the V0 milestones into outcome-based sprints. A sprint does not need to match a single milestone; the goal is to finish each sprint with a usable system capability.

## Sprint 1: Foundation and Ingestion

Status: complete.

Milestones:

- `M0` Repository Bootstrap
- `M1` Server Skeleton
- `M2` Database Layer
- `M3` IMU Batch Upload API
- `M7.1` PlatformIO project
- `M7.2` I2C scanner
- `M7.3` MPU-6050 bench read

Outcome:

- Repo structure exists.
- FastAPI server starts locally.
- SQLite tables are created automatically.
- `POST /api/v1/imu/batch` stores raw IMU batches and samples.
- Duplicate batch sequences return `409 Conflict`.
- ESP8266 reads the MPU-6050 at approximately 50 Hz over I2C.

## Sprint 2: Label, Export, Inspect

Milestones:

- `M4` Manual Event Labeling API
- `M5` Export API
- `M6` Analysis Utilities

Outcome:

- Manual labels can be created for session-relative time windows.
- Samples can be exported as CSV.
- Event labels can be joined to samples by `session_id` and `device_ms` overlap.
- Session and event windows can be plotted for quick data review.

Rationale:

- Build inspection and labeling tools before collecting real long-run sessions.
- Avoid accumulating raw data that cannot be easily labeled, exported, or visually checked.

## Sprint 3: Real Device Upload Loop

Milestones:

- `M8.1` Wi-Fi connection
- `M8.2` Sample batching
- `M8.3` HTTP POST upload

Outcome:

- ESP8266 connects to Wi-Fi.
- Firmware batches 50 samples per upload.
- Firmware posts batches to `/api/v1/imu/batch`.
- Server stores real sensor data from the device.

Rationale:

- Keep upload work separate from analysis tooling so firmware-server integration can be tested against stable APIs.
- Allow server hardening if real device uploads expose timing, payload, or duplicate-sequence issues.

## Sprint 4: Long-Run Validation

Milestones:

- `M8.4` Long-run firmware test
- `M9` Data Quality Validation

Outcome:

- Device runs for 30 minutes without obvious firmware failure.
- At least one 15-minute baseline session is collected.
- Sequence gaps are documented.
- Accel and gyro magnitudes are reviewed for plausibility.
- Synthetic activity checklist is complete.

Rationale:

- Treat long-run hardware validation as its own sprint because it depends on physical setup, uninterrupted runtime, and manual review.

## Sprint 5: Documentation and V0 Closeout

Milestones:

- `M10` Documentation
- Final V0 cleanup from earlier sprints

Outcome:

- Hardware wiring documentation is complete.
- API contract documentation is complete.
- Payload schema documentation is complete.
- Test procedure is documented.
- V0 definition of done is reviewed and closed.

Rationale:

- Final docs should reflect the implemented behavior after server, firmware, export, plotting, and validation work have stabilized.
