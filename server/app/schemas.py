from typing import Literal

from pydantic import BaseModel, Field, model_validator


EventType = Literal[
  "seizure",
  "sleep_twitch",
  "scratching",
  "shake_off",
  "walking",
  "running",
  "resting",
  "unknown",
]


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
  firmware_version: str | None = None
  session_id: str = Field(min_length=1)
  sequence: int = Field(ge=0)
  sample_hz: int = Field(gt=0)
  device_ms_start: int = Field(ge=0)
  battery_mv: int | None = None
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
  source: str = Field(default="manual", min_length=1)
  notes: str | None = None

  @model_validator(mode="after")
  def validate_time_window(self) -> "EventIn":
    if self.start_device_ms >= self.end_device_ms:
      raise ValueError("start_device_ms must be less than end_device_ms")
    return self


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


class SessionSampleOut(BaseModel):
  device_id: str
  session_id: str
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
