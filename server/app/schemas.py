import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DEFAULT_EVENT_TYPES = [
  "seizure",
  "sleep_twitch",
  "scratching",
  "scooting",
  "shake_off",
  "walking",
  "running",
  "resting",
  "unknown",
]
EventType = str


def normalize_event_type(value: object) -> str:
  if not isinstance(value, str):
    raise ValueError("event_type must be a string")
  normalized = value.strip().lower()
  normalized = re.sub(r"[\s-]+", "_", normalized)
  normalized = re.sub(r"[^a-z0-9_]", "", normalized)
  normalized = re.sub(r"_+", "_", normalized).strip("_")
  if not normalized:
    raise ValueError("event_type must include at least one letter or number")
  if len(normalized) > 64:
    raise ValueError("event_type must be 64 characters or fewer")
  return normalized


class IMUSampleIn(BaseModel):
  dt_ms: int = Field(ge=0)
  ax: float
  ay: float
  az: float
  gx: float
  gy: float
  gz: float


class IMUBatchIn(BaseModel):
  device_id: str = Field(min_length=1)
  boot_id: str = Field(min_length=1)
  firmware_version: str | None = None
  sequence: int = Field(ge=0)
  sample_hz: int = Field(gt=0)
  device_ms_start: int = Field(ge=0)
  battery_mv: int | None = None
  reset_reason: str | None = None
  reset_info: str | None = None
  uptime_ms: int | None = Field(default=None, ge=0)
  wifi_rssi: int | None = None
  free_heap: int | None = Field(default=None, ge=0)
  min_free_heap: int | None = Field(default=None, ge=0)
  heap_fragmentation: int | None = Field(default=None, ge=0, le=100)
  queued_batch_count: int | None = Field(default=None, ge=0)
  dropped_batch_count: int | None = Field(default=None, ge=0)
  max_sample_lateness_ms: int | None = Field(default=None, ge=0)
  upload_skip_count: int | None = Field(default=None, ge=0)
  last_http_duration_ms: int | None = Field(default=None, ge=0)
  last_http_status: int | None = None
  consecutive_upload_failures: int | None = Field(default=None, ge=0)
  wifi_disconnect_count: int | None = Field(default=None, ge=0)
  samples: list[IMUSampleIn] = Field(min_length=1)


class IMUBatchAck(BaseModel):
  status: Literal["ok"]
  device_id: str
  sequence: int
  samples_received: int


class EventIn(BaseModel):
  session_id: str = Field(min_length=1)
  event_type: EventType
  severity: int | None = Field(default=None, ge=1, le=5)
  start_device_ms: int = Field(ge=0)
  end_device_ms: int = Field(ge=0)
  start_server_received_at: str | None = None
  end_server_received_at: str | None = None
  source: str = Field(default="manual", min_length=1)
  notes: str | None = None

  @field_validator("event_type", mode="before")
  @classmethod
  def normalize_event_type_field(cls, value: object) -> str:
    return normalize_event_type(value)

  @model_validator(mode="after")
  def validate_time_window(self) -> "EventIn":
    if self.start_device_ms >= self.end_device_ms:
      raise ValueError("start_device_ms must be less than end_device_ms")
    return self


class EventUpdate(BaseModel):
  session_id: str | None = Field(default=None, min_length=1)
  event_type: EventType | None = None
  severity: int | None = Field(default=None, ge=1, le=5)
  start_device_ms: int | None = Field(default=None, ge=0)
  end_device_ms: int | None = Field(default=None, ge=0)
  start_server_received_at: str | None = None
  end_server_received_at: str | None = None
  source: str | None = Field(default=None, min_length=1)
  notes: str | None = None

  @field_validator("event_type", mode="before")
  @classmethod
  def normalize_event_type_field(cls, value: object) -> str | None:
    if value is None:
      return None
    return normalize_event_type(value)


class EventOut(EventIn):
  id: int
  created_at: str


class SessionSummaryOut(BaseModel):
  session_id: str
  device_id: str
  started_at: str | None = None
  ended_at: str | None = None
  mount_location: str | None = None
  notes: str | None = None
  sample_count: int
  batch_count: int
  min_device_ms: int | None = None
  max_device_ms: int | None = None
  first_server_received_at: str | None = None
  last_server_received_at: str | None = None


class SessionCreateIn(BaseModel):
  session_id: str = Field(min_length=1)
  device_id: str = Field(min_length=1)
  started_at: str | None = None
  ended_at: str | None = None
  mount_location: str | None = None
  notes: str | None = None


class ActiveSessionIn(BaseModel):
  session_id: str = Field(min_length=1)


class ActiveSessionOut(BaseModel):
  device_id: str
  session_id: str
  updated_at: str
  session: SessionSummaryOut


class BootSummaryOut(BaseModel):
  device_id: str
  session_id: str
  boot_id: str
  reset_reason: str | None = None
  reset_info: str | None = None
  first_received_at: str | None = None
  last_received_at: str | None = None
  min_sequence: int | None = None
  max_sequence: int | None = None
  batch_count: int
  sample_count: int
  min_device_ms_start: int | None = None
  max_device_ms_start: int | None = None
  latest_uptime_ms: int | None = None
  latest_http_status: int | None = None
  latest_http_duration_ms: int | None = None
  max_consecutive_upload_failures: int | None = None
  max_wifi_disconnect_count: int | None = None
  max_queued_batch_count: int | None = None
  max_dropped_batch_count: int | None = None
  max_sample_lateness_ms: int | None = None
  max_upload_skip_count: int | None = None
  min_wifi_rssi: int | None = None
  max_wifi_rssi: int | None = None
  min_free_heap: int | None = None
  min_reported_free_heap: int | None = None
  max_heap_fragmentation: int | None = None


class SessionSampleOut(BaseModel):
  device_id: str
  session_id: str
  boot_id: str
  batch_sequence: int
  sample_index: int
  device_ms: int
  server_received_at: str
  ax: float
  ay: float
  az: float
  gx: float
  gy: float
  gz: float
  accel_mag: float
  gyro_mag: float


class SessionSampleWindowOut(BaseModel):
  samples: list[SessionSampleOut]
  total_sample_count: int
  window_start_index: int | None = None
  window_end_index: int | None = None
  window_start_server_received_at: str | None = None
  window_end_server_received_at: str | None = None
  window_start_device_ms: int | None = None
  window_end_device_ms: int | None = None
