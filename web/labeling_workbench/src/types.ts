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
  start_server_received_at?: string | null;
  end_server_received_at?: string | null;
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
  boot_id: string;
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
  start_server_received_at: string | null;
  end_server_received_at: string | null;
  source: string;
  notes: string | null;
  created_at: string;
};

export type SelectionRange = {
  startDeviceMs: number;
  endDeviceMs: number;
  startServerReceivedAt?: string | null;
  endServerReceivedAt?: string | null;
};

export type ViewRange = {
  startDeviceMs: number;
  endDeviceMs: number;
  startServerReceivedAt?: string | null;
  endServerReceivedAt?: string | null;
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
  latest_boot_id: string | null;
  latest_reset_reason: string | null;
  latest_wifi_rssi: number | null;
  latest_free_heap: number | null;
  latest_queued_batch_count: number | null;
  latest_dropped_batch_count: number | null;
  latest_max_sample_lateness_ms: number | null;
  latest_upload_skip_count: number | null;
  latest_session: {
    session_id: string;
    sample_count: number;
    latest_received_at: string | null;
  } | null;
};

export type ActiveSessionSummary = {
  device_id: string;
  session_id: string;
  updated_at: string;
  session: SessionSummary;
};

export type ApiControlStatus = {
  apiBaseUrl: string;
  apiReachable: boolean;
  managed: boolean;
  pid: number | null;
  message: string;
  logs: string[];
};
