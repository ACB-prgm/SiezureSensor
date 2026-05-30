export type EventType =
  | "seizure"
  | "sleep_twitch"
  | "scratching"
  | "scooting"
  | "shake_off"
  | "walking"
  | "running"
  | "resting"
  | "unknown";

export const EVENT_TYPES: EventType[] = [
  "seizure",
  "sleep_twitch",
  "scratching",
  "scooting",
  "shake_off",
  "walking",
  "running",
  "resting",
  "unknown",
];

export type EventPayload = {
  session_id: string;
  event_type: EventType;
  severity: number | null;
  start_device_ms: number;
  end_device_ms: number;
  source: string;
  notes: string | null;
};

export type SessionCreatePayload = {
  session_id: string;
  device_id: string;
  started_at?: string | null;
  ended_at?: string | null;
  mount_location?: string | null;
  notes?: string | null;
};

export type SessionSummary = {
  session_id: string;
  device_id: string;
  started_at: string | null;
  ended_at: string | null;
  mount_location: string | null;
  notes: string | null;
  sample_count: number;
  batch_count: number;
  min_device_ms: number | null;
  max_device_ms: number | null;
  first_server_received_at: string | null;
  last_server_received_at: string | null;
};

export type SessionSample = {
  device_id: string;
  session_id: string;
  batch_sequence: number;
  sample_index: number;
  device_ms: number;
  server_received_at: string;
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
  accel_mag: number;
  gyro_mag: number;
};

export type EventLabel = {
  id: number;
  session_id: string;
  event_type: EventType;
  severity: number | null;
  start_device_ms: number;
  end_device_ms: number;
  source: string;
  notes: string | null;
  created_at: string;
};

export type SelectionRange = {
  startDeviceMs: number;
  endDeviceMs: number;
};

export type ViewRange = {
  startDeviceMs: number;
  endDeviceMs: number;
};

export type ApiRuntimeStatus = {
  status: "ok";
  server_time: string;
  database_path: string;
  session_count: number;
  batch_count: number;
  sample_count: number;
  latest_batch_received_at: string | null;
  latest_sample_received_at: string | null;
  latest_device_ms: number | null;
  latest_session: {
    session_id: string;
    sample_count: number;
    latest_received_at: string | null;
  } | null;
};

export type ApiControlStatus = {
  apiBaseUrl: string;
  apiReachable: boolean;
  managed: boolean;
  pid: number | null;
  message: string;
  logs: string[];
};
