from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import Batch, Device, IMUSample, Session
from app.schemas import IMUBatchAck, IMUBatchIn


router = APIRouter(prefix="/api/v1/imu", tags=["imu"])


def now_iso() -> str:
  return datetime.now(UTC).isoformat()


@router.post("/batch", response_model=IMUBatchAck)
def upload_imu_batch(payload: IMUBatchIn, db: OrmSession = Depends(get_db)) -> IMUBatchAck:
  received_at = now_iso()

  try:
    with db.begin():
      device = db.get(Device, payload.device_id)
      if device is None:
        device = Device(
          device_id=payload.device_id,
          firmware_version=payload.firmware_version,
          created_at=received_at,
        )
        db.add(device)
      else:
        device.firmware_version = payload.firmware_version or device.firmware_version

      session = db.get(Session, payload.session_id)
      if session is None:
        db.add(
          Session(
            session_id=payload.session_id,
            device_id=payload.device_id,
            started_at=None,
            ended_at=None,
            mount_location=None,
            notes=None,
          )
        )

      db.add(
        Batch(
          device_id=payload.device_id,
          session_id=payload.session_id,
          sequence=payload.sequence,
          sample_hz=payload.sample_hz,
          device_ms_start=payload.device_ms_start,
          server_received_at=received_at,
          sample_count=len(payload.samples),
          battery_mv=payload.battery_mv,
          raw_payload_json=payload.model_dump_json(),
        )
      )

      for index, sample in enumerate(payload.samples):
        db.add(
          IMUSample(
            device_id=payload.device_id,
            session_id=payload.session_id,
            batch_sequence=payload.sequence,
            sample_index=index,
            device_ms=payload.device_ms_start + sample.dt_ms,
            server_received_at=received_at,
            ax=sample.ax,
            ay=sample.ay,
            az=sample.az,
            gx=sample.gx,
            gy=sample.gy,
            gz=sample.gz,
          )
        )
  except IntegrityError as exc:
    db.rollback()
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="Duplicate batch sequence for device and session",
    ) from exc

  return IMUBatchAck(
    status="ok",
    device_id=payload.device_id,
    sequence=payload.sequence,
    samples_received=len(payload.samples),
  )
