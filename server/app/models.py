from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class Device(Base):
  __tablename__ = "devices"

  device_id = Column(String, primary_key=True)
  name = Column(String, nullable=True)
  firmware_version = Column(String, nullable=True)
  created_at = Column(String, nullable=False)
  notes = Column(Text, nullable=True)


class Session(Base):
  __tablename__ = "sessions"

  session_id = Column(String, primary_key=True)
  device_id = Column(String, ForeignKey("devices.device_id"), nullable=False)
  started_at = Column(String, nullable=True)
  ended_at = Column(String, nullable=True)
  mount_location = Column(String, nullable=True)
  notes = Column(Text, nullable=True)


class Batch(Base):
  __tablename__ = "batches"
  __table_args__ = (
    UniqueConstraint("device_id", "session_id", "sequence", name="uq_batch_device_session_sequence"),
  )

  id = Column(Integer, primary_key=True, autoincrement=True)
  device_id = Column(String, nullable=False)
  session_id = Column(String, nullable=False)
  sequence = Column(Integer, nullable=False)
  sample_hz = Column(Integer, nullable=False)
  device_ms_start = Column(Integer, nullable=False)
  server_received_at = Column(String, nullable=False)
  sample_count = Column(Integer, nullable=False)
  battery_mv = Column(Integer, nullable=True)
  raw_payload_json = Column(Text, nullable=False)


class IMUSample(Base):
  __tablename__ = "imu_samples"

  id = Column(Integer, primary_key=True, autoincrement=True)
  device_id = Column(String, nullable=False)
  session_id = Column(String, nullable=False)
  batch_sequence = Column(Integer, nullable=False)
  sample_index = Column(Integer, nullable=False)
  device_ms = Column(Integer, nullable=False)
  server_received_at = Column(String, nullable=False)
  ax = Column(Float, nullable=False)
  ay = Column(Float, nullable=False)
  az = Column(Float, nullable=False)
  gx = Column(Float, nullable=False)
  gy = Column(Float, nullable=False)
  gz = Column(Float, nullable=False)


class Event(Base):
  __tablename__ = "events"

  id = Column(Integer, primary_key=True, autoincrement=True)
  session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False)
  event_type = Column(String, nullable=False)
  severity = Column(Integer, nullable=True)
  start_device_ms = Column(Integer, nullable=False)
  end_device_ms = Column(Integer, nullable=False)
  source = Column(String, nullable=False, default="manual")
  notes = Column(Text, nullable=True)
  created_at = Column(String, nullable=False)
