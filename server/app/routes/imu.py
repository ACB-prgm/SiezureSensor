from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import Batch, IMUSample
from app.schemas import IMUBatchAck, IMUBatchIn
from app.session_assignment import ensure_device, get_or_create_active_session


router = APIRouter(prefix="/api/v1/imu", tags=["imu"])


def now_iso() -> str:
  return datetime.now(UTC).isoformat()


@router.post("/batch", response_model=IMUBatchAck)
def upload_imu_batch(payload: IMUBatchIn, db: OrmSession = Depends(get_db)) -> IMUBatchAck:
  received_at = now_iso()

  try:
    with db.begin():
      ensure_device(db, payload.device_id, payload.firmware_version, received_at)
      session = get_or_create_active_session(db, payload.device_id, received_at)

      db.add(
        Batch(
          device_id=payload.device_id,
          session_id=session.session_id,
          boot_id=payload.boot_id,
          sequence=payload.sequence,
          sample_hz=payload.sample_hz,
          device_ms_start=payload.device_ms_start,
          server_received_at=received_at,
          sample_count=len(payload.samples),
          battery_mv=payload.battery_mv,
          reset_reason=payload.reset_reason,
          reset_info=payload.reset_info,
          uptime_ms=payload.uptime_ms,
          wifi_rssi=payload.wifi_rssi,
          free_heap=payload.free_heap,
          min_free_heap=payload.min_free_heap,
          heap_fragmentation=payload.heap_fragmentation,
          queued_batch_count=payload.queued_batch_count,
          dropped_batch_count=payload.dropped_batch_count,
          max_sample_lateness_ms=payload.max_sample_lateness_ms,
          upload_skip_count=payload.upload_skip_count,
          last_http_duration_ms=payload.last_http_duration_ms,
          last_http_status=payload.last_http_status,
          consecutive_upload_failures=payload.consecutive_upload_failures,
          wifi_disconnect_count=payload.wifi_disconnect_count,
          raw_payload_json=payload.model_dump_json(),
        )
      )

      for index, sample in enumerate(payload.samples):
        db.add(
          IMUSample(
            device_id=payload.device_id,
            session_id=session.session_id,
            boot_id=payload.boot_id,
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
      detail="Duplicate batch sequence for device boot",
    ) from exc

  return IMUBatchAck(
    status="ok",
    device_id=payload.device_id,
    sequence=payload.sequence,
    samples_received=len(payload.samples),
  )
