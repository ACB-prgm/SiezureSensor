import csv
from io import StringIO
from math import sqrt

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session as OrmSession

from app.database import get_db
from app.models import IMUSample


router = APIRouter(prefix="/api/v1/export", tags=["export"])

EXPORT_COLUMNS = [
  "device_id",
  "session_id",
  "batch_sequence",
  "sample_index",
  "device_ms",
  "server_received_at",
  "ax",
  "ay",
  "az",
  "gx",
  "gy",
  "gz",
  "accel_mag",
  "gyro_mag",
]


def sample_to_row(sample: IMUSample) -> dict[str, object]:
  return {
    "device_id": sample.device_id,
    "session_id": sample.session_id,
    "batch_sequence": sample.batch_sequence,
    "sample_index": sample.sample_index,
    "device_ms": sample.device_ms,
    "server_received_at": sample.server_received_at,
    "ax": sample.ax,
    "ay": sample.ay,
    "az": sample.az,
    "gx": sample.gx,
    "gy": sample.gy,
    "gz": sample.gz,
    "accel_mag": sqrt(sample.ax**2 + sample.ay**2 + sample.az**2),
    "gyro_mag": sqrt(sample.gx**2 + sample.gy**2 + sample.gz**2),
  }


@router.get("/samples")
def export_samples(
  session_id: str | None = None,
  start_device_ms: int | None = Query(default=None, ge=0),
  end_device_ms: int | None = Query(default=None, ge=0),
  format: str = "csv",
  db: OrmSession = Depends(get_db),
) -> Response:
  if format != "csv":
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="Only csv format is supported",
    )

  if start_device_ms is not None and end_device_ms is not None and start_device_ms > end_device_ms:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="start_device_ms must be less than or equal to end_device_ms",
    )

  query = db.query(IMUSample)
  if session_id is not None:
    query = query.filter(IMUSample.session_id == session_id)
  if start_device_ms is not None:
    query = query.filter(IMUSample.device_ms >= start_device_ms)
  if end_device_ms is not None:
    query = query.filter(IMUSample.device_ms <= end_device_ms)

  samples = query.order_by(IMUSample.session_id, IMUSample.device_ms, IMUSample.sample_index).all()

  output = StringIO()
  writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
  writer.writeheader()
  for sample in samples:
    writer.writerow(sample_to_row(sample))

  return Response(content=output.getvalue(), media_type="text/csv")
