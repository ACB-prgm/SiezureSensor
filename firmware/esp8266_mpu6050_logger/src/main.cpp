#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <Wire.h>

#include "config.h"

namespace {
constexpr uint8_t SDA_PIN = D2; // GPIO4
constexpr uint8_t SCL_PIN = D1; // GPIO5
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t SAMPLE_INTERVAL_MS = 20; // 50 Hz
constexpr uint16_t SAMPLES_PER_BATCH = 50;
constexpr uint8_t QUEUED_BATCH_CAPACITY = 12; // ESP8266 RAM-safe backlog.
constexpr bool ENABLE_STARTUP_I2C_SCAN = true;
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 10000;
constexpr uint32_t HTTP_TIMEOUT_MS = 900;
constexpr uint32_t UPLOAD_RETRY_INTERVAL_MS = 250;
constexpr uint32_t UPLOAD_SAMPLE_GUARD_MS = 8;
constexpr int HTTP_STATUS_CONFLICT = 409;

constexpr uint8_t MPU6050_ADDRESS = 0x68;
constexpr uint8_t MPU6050_REG_SMPLRT_DIV = 0x19;
constexpr uint8_t MPU6050_REG_CONFIG = 0x1A;
constexpr uint8_t MPU6050_REG_GYRO_CONFIG = 0x1B;
constexpr uint8_t MPU6050_REG_ACCEL_CONFIG = 0x1C;
constexpr uint8_t MPU6050_REG_ACCEL_XOUT_H = 0x3B;
constexpr uint8_t MPU6050_REG_PWR_MGMT_1 = 0x6B;
constexpr uint8_t MPU6050_REG_WHO_AM_I = 0x75;

constexpr float ACCEL_LSB_PER_G = 16384.0F; // +/- 2 g
constexpr float GYRO_LSB_PER_DPS = 131.0F;  // +/- 250 deg/s

struct RawImuReading {
  int16_t ax;
  int16_t ay;
  int16_t az;
  int16_t gx;
  int16_t gy;
  int16_t gz;
};

struct BatchSample {
  uint16_t dt_ms;
  RawImuReading reading;
};

struct PreparedBatch {
  uint32_t sequence;
  uint32_t device_ms_start;
  uint16_t sample_count;
  BatchSample samples[SAMPLES_PER_BATCH];
};

PreparedBatch current_batch = {};
PreparedBatch queued_batches[QUEUED_BATCH_CAPACITY];
uint8_t queue_head = 0;
uint8_t queue_count = 0;
uint32_t next_sample_ms = 0;
uint32_t next_wifi_retry_ms = 0;
uint32_t next_upload_attempt_ms = 0;
uint32_t batch_sequence = 0;
uint32_t dropped_batch_count = 0;
uint32_t max_sample_lateness_ms = 0;
uint32_t upload_skip_count = 0;
String boot_id;
String reset_reason;
bool imu_ready = false;
bool wifi_begin_called = false;

void printAddress(uint8_t address) {
  Serial.print("0x");
  if (address < 16) {
    Serial.print("0");
  }
  Serial.print(address, HEX);
}

bool isWiFiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

void printWiFiStatus() {
  Serial.print("Wi-Fi status: ");
  Serial.print(WiFi.status());
  if (isWiFiConnected()) {
    Serial.print(", IP: ");
    Serial.print(WiFi.localIP());
    Serial.print(", RSSI: ");
    Serial.print(WiFi.RSSI());
  }
  Serial.println();
}

void startWiFiConnect() {
  if (isWiFiConnected()) {
    return;
  }

  Serial.print("Connecting to Wi-Fi SSID: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  wifi_begin_called = true;
}

void maintainWiFi(uint32_t now_ms) {
  if (isWiFiConnected()) {
    static bool printed_connected = false;
    if (!printed_connected) {
      Serial.print("Wi-Fi connected. Local IP: ");
      Serial.print(WiFi.localIP());
      Serial.print(", RSSI: ");
      Serial.println(WiFi.RSSI());
      printed_connected = true;
    }
    return;
  }

  if (static_cast<int32_t>(now_ms - next_wifi_retry_ms) >= 0) {
    if (wifi_begin_called) {
      Serial.println("Wi-Fi not connected; retrying without blocking sampling.");
      printWiFiStatus();
      WiFi.disconnect();
    }
    startWiFiConnect();
    next_wifi_retry_ms = now_ms + WIFI_RETRY_INTERVAL_MS;
  }
}

void scanI2CBus() {
  uint8_t found_count = 0;

  Serial.println();
  Serial.println("Scanning I2C bus...");

  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    const uint8_t error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at ");
      printAddress(address);
      if (address == MPU6050_ADDRESS) {
        Serial.print(" (expected MPU-6050)");
      }
      Serial.println();
      found_count++;
    } else if (error == 4) {
      Serial.print("Unknown I2C error at ");
      printAddress(address);
      Serial.println();
    }
  }

  if (found_count == 0) {
    Serial.println("No I2C devices found. Check VCC, GND, SDA, and SCL wiring.");
  } else {
    Serial.print("Scan complete. Devices found: ");
    Serial.println(found_count);
  }
}

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(MPU6050_ADDRESS);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readRegisters(uint8_t start_reg, uint8_t *buffer, size_t length) {
  Wire.beginTransmission(MPU6050_ADDRESS);
  Wire.write(start_reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  const size_t received = Wire.requestFrom(MPU6050_ADDRESS, length);
  if (received != length) {
    while (Wire.available() > 0) {
      Wire.read();
    }
    return false;
  }

  for (size_t i = 0; i < length; i++) {
    buffer[i] = static_cast<uint8_t>(Wire.read());
  }

  return true;
}

bool readRegister(uint8_t reg, uint8_t &value) {
  uint8_t buffer[1] = {0};
  if (!readRegisters(reg, buffer, sizeof(buffer))) {
    return false;
  }
  value = buffer[0];
  return true;
}

int16_t readInt16(uint8_t high_byte, uint8_t low_byte) {
  return static_cast<int16_t>((static_cast<uint16_t>(high_byte) << 8) | low_byte);
}

float accelRawToG(int16_t value) {
  return static_cast<float>(value) / ACCEL_LSB_PER_G;
}

float gyroRawToDps(int16_t value) {
  return static_cast<float>(value) / GYRO_LSB_PER_DPS;
}

bool initializeMpu6050() {
  uint8_t who_am_i = 0;
  if (!readRegister(MPU6050_REG_WHO_AM_I, who_am_i)) {
    Serial.println("MPU-6050 WHO_AM_I read failed.");
    return false;
  }

  Serial.print("MPU-6050 WHO_AM_I: ");
  printAddress(who_am_i);
  Serial.println();

  if ((who_am_i & 0x7E) != MPU6050_ADDRESS) {
    Serial.println("Unexpected WHO_AM_I value. Check sensor address and wiring.");
    return false;
  }

  bool ok = true;
  ok = writeRegister(MPU6050_REG_PWR_MGMT_1, 0x00) && ok;   // Wake sensor.
  delay(100);
  ok = writeRegister(MPU6050_REG_CONFIG, 0x03) && ok;       // DLPF on, gyro output 1 kHz.
  ok = writeRegister(MPU6050_REG_SMPLRT_DIV, 19) && ok;     // 1 kHz / (1 + 19) = 50 Hz.
  ok = writeRegister(MPU6050_REG_GYRO_CONFIG, 0x00) && ok;  // +/- 250 deg/s.
  ok = writeRegister(MPU6050_REG_ACCEL_CONFIG, 0x00) && ok; // +/- 2 g.

  if (!ok) {
    Serial.println("MPU-6050 configuration write failed.");
    return false;
  }

  Serial.println("MPU-6050 initialized at +/-2 g, +/-250 deg/s, 50 Hz sample cadence.");
  return true;
}

bool readImu(RawImuReading &reading) {
  uint8_t buffer[14] = {0};
  if (!readRegisters(MPU6050_REG_ACCEL_XOUT_H, buffer, sizeof(buffer))) {
    return false;
  }

  reading.ax = readInt16(buffer[0], buffer[1]);
  reading.ay = readInt16(buffer[2], buffer[3]);
  reading.az = readInt16(buffer[4], buffer[5]);
  reading.gx = readInt16(buffer[8], buffer[9]);
  reading.gy = readInt16(buffer[10], buffer[11]);
  reading.gz = readInt16(buffer[12], buffer[13]);

  return true;
}

void resetCurrentBatch(uint32_t next_start_ms) {
  current_batch.device_ms_start = next_start_ms;
  current_batch.sample_count = 0;
}

void appendSampleToCurrentBatch(uint32_t sample_ms, const RawImuReading &reading) {
  if (current_batch.sample_count == 0) {
    current_batch.device_ms_start = sample_ms;
  }

  current_batch.samples[current_batch.sample_count] = BatchSample{
      static_cast<uint16_t>(sample_ms - current_batch.device_ms_start),
      reading,
  };
  current_batch.sample_count++;
}

bool isCurrentBatchReady() {
  return current_batch.sample_count >= SAMPLES_PER_BATCH;
}

uint8_t queueTailIndex() {
  return (queue_head + queue_count) % QUEUED_BATCH_CAPACITY;
}

void dropOldestQueuedBatch() {
  if (queue_count == 0) {
    return;
  }
  Serial.print("Upload queue full; dropping oldest batch sequence=");
  Serial.println(queued_batches[queue_head].sequence);
  queue_head = (queue_head + 1) % QUEUED_BATCH_CAPACITY;
  queue_count--;
  dropped_batch_count++;
}

void enqueueCurrentBatch() {
  if (queue_count >= QUEUED_BATCH_CAPACITY) {
    dropOldestQueuedBatch();
  }

  current_batch.sequence = batch_sequence;
  queued_batches[queueTailIndex()] = current_batch;
  queue_count++;

  Serial.print("Batch queued: sequence=");
  Serial.print(current_batch.sequence);
  Serial.print(", samples=");
  Serial.print(current_batch.sample_count);
  Serial.print(", device_ms_start=");
  Serial.print(current_batch.device_ms_start);
  Serial.print(", queue=");
  Serial.print(queue_count);
  Serial.print("/");
  Serial.println(QUEUED_BATCH_CAPACITY);

  batch_sequence++;
}

void popQueuedBatch() {
  if (queue_count == 0) {
    return;
  }
  queue_head = (queue_head + 1) % QUEUED_BATCH_CAPACITY;
  queue_count--;
}

String uploadUrl() {
  String base_url = SERVER_URL;
  if (base_url.endsWith("/")) {
    base_url.remove(base_url.length() - 1);
  }
  return base_url + "/api/v1/imu/batch";
}

String buildBatchJson(const PreparedBatch &batch) {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["boot_id"] = boot_id;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["sequence"] = batch.sequence;
  doc["sample_hz"] = 50;
  doc["device_ms_start"] = batch.device_ms_start;
  doc["battery_mv"] = nullptr;
  doc["reset_reason"] = reset_reason;
  doc["wifi_rssi"] = isWiFiConnected() ? WiFi.RSSI() : 0;
  doc["free_heap"] = ESP.getFreeHeap();
  doc["queued_batch_count"] = queue_count;
  doc["dropped_batch_count"] = dropped_batch_count;
  doc["max_sample_lateness_ms"] = max_sample_lateness_ms;
  doc["upload_skip_count"] = upload_skip_count;

  JsonArray samples = doc["samples"].to<JsonArray>();
  for (uint16_t i = 0; i < batch.sample_count; i++) {
    const BatchSample &batch_sample = batch.samples[i];
    JsonObject sample = samples.add<JsonObject>();
    sample["dt_ms"] = batch_sample.dt_ms;
    sample["ax"] = accelRawToG(batch_sample.reading.ax);
    sample["ay"] = accelRawToG(batch_sample.reading.ay);
    sample["az"] = accelRawToG(batch_sample.reading.az);
    sample["gx"] = gyroRawToDps(batch_sample.reading.gx);
    sample["gy"] = gyroRawToDps(batch_sample.reading.gy);
    sample["gz"] = gyroRawToDps(batch_sample.reading.gz);
  }

  String payload;
  serializeJson(doc, payload);
  return payload;
}

bool uploadBatch(const PreparedBatch &batch) {
  if (!isWiFiConnected()) {
    Serial.println("Deferring upload: Wi-Fi is not connected.");
    return false;
  }

  const String url = uploadUrl();
  const String payload = buildBatchJson(batch);
  WiFiClient client;
  HTTPClient http;

  Serial.print("Uploading batch sequence=");
  Serial.print(batch.sequence);
  Serial.print(", boot_id=");
  Serial.print(boot_id);
  Serial.print(", queue=");
  Serial.print(queue_count);
  Serial.print(", bytes=");
  Serial.print(payload.length());
  Serial.print(", url=");
  Serial.println(url);

  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(client, url)) {
    Serial.println("HTTP begin failed; keeping batch queued.");
    return false;
  }

  http.addHeader("Content-Type", "application/json");
  const int status_code = http.POST(payload);
  Serial.print("Upload HTTP status: ");
  Serial.println(status_code);

  const bool already_stored = status_code == HTTP_STATUS_CONFLICT;
  bool ok = (status_code >= 200 && status_code < 300) || already_stored;
  if (status_code > 0) {
    Serial.print("Upload response: ");
    Serial.println(http.getString());
    if (already_stored) {
      Serial.println("Upload duplicate already stored; removing queued batch.");
    }
  } else {
    Serial.print("Upload failed: ");
    Serial.println(http.errorToString(status_code));
  }

  http.end();
  return ok;
}

void uploadOneQueuedBatch(uint32_t now_ms) {
  if (queue_count == 0 || static_cast<int32_t>(now_ms - next_upload_attempt_ms) < 0) {
    return;
  }

  const int32_t ms_until_next_sample = static_cast<int32_t>(next_sample_ms - now_ms);
  if (ms_until_next_sample <= static_cast<int32_t>(UPLOAD_SAMPLE_GUARD_MS)) {
    upload_skip_count++;
    next_upload_attempt_ms = now_ms + UPLOAD_RETRY_INTERVAL_MS;
    return;
  }

  if (uploadBatch(queued_batches[queue_head])) {
    Serial.print("Upload accepted; removing queued batch. sequence=");
    Serial.println(queued_batches[queue_head].sequence);
    popQueuedBatch();
  }

  next_upload_attempt_ms = millis() + UPLOAD_RETRY_INTERVAL_MS;
}

void initializeBootIdentity() {
  reset_reason = ESP.getResetReason();
  randomSeed(ESP.getCycleCount() ^ micros() ^ ESP.getChipId());
  char buffer[40] = {0};
  snprintf(
      buffer,
      sizeof(buffer),
      "%06X-%08lX-%08lX",
      ESP.getChipId(),
      static_cast<unsigned long>(micros()),
      static_cast<unsigned long>(random(0x7fffffff)));
  boot_id = String(buffer);
}
} // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  initializeBootIdentity();

  Serial.println();
  Serial.println("Dog Seizure Sensor V0 - ESP8266 MPU-6050 upload loop");
  Serial.println("Expected MPU-6050 address: 0x68");
  Serial.println("Wiring: SDA=D2/GPIO4, SCL=D1/GPIO5, VCC=3V3, GND=GND");
  Serial.print("Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("Boot ID: ");
  Serial.println(boot_id);
  Serial.print("Reset reason: ");
  Serial.println(reset_reason);
  Serial.print("Server URL: ");
  Serial.println(SERVER_URL);
  Serial.print("Queue capacity: ");
  Serial.println(QUEUED_BATCH_CAPACITY);

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  startWiFiConnect();
  next_wifi_retry_ms = millis() + WIFI_RETRY_INTERVAL_MS;

  if (ENABLE_STARTUP_I2C_SCAN) {
    scanI2CBus();
  }

  imu_ready = initializeMpu6050();
  if (imu_ready) {
    Serial.println("IMU ready. Preparing 50-sample batches at 50 Hz.");
  } else {
    Serial.println("IMU is not ready. Firmware will retry initialization every second.");
  }

  next_sample_ms = millis();
  next_upload_attempt_ms = next_sample_ms;
  resetCurrentBatch(next_sample_ms);
}

void loop() {
  const uint32_t now_ms = millis();
  maintainWiFi(now_ms);

  if (!imu_ready) {
    static uint32_t next_retry_ms = 0;
    if (static_cast<int32_t>(now_ms - next_retry_ms) >= 0) {
      imu_ready = initializeMpu6050();
      if (imu_ready) {
        Serial.println("IMU ready. Preparing 50-sample batches at 50 Hz.");
        next_sample_ms = millis();
        resetCurrentBatch(next_sample_ms);
      }
      next_retry_ms = now_ms + 1000;
    }
    return;
  }

  if (static_cast<int32_t>(now_ms - next_sample_ms) >= 0) {
    RawImuReading reading = {};
    if (readImu(reading)) {
      const uint32_t sample_lateness_ms = now_ms - next_sample_ms;
      if (sample_lateness_ms > max_sample_lateness_ms) {
        max_sample_lateness_ms = sample_lateness_ms;
      }
      appendSampleToCurrentBatch(now_ms, reading);
      next_sample_ms += SAMPLE_INTERVAL_MS;
      if (isCurrentBatchReady()) {
        enqueueCurrentBatch();
        resetCurrentBatch(next_sample_ms);
      }
    } else {
      Serial.println("IMU read failed. Will retry initialization.");
      imu_ready = false;
    }

    if (static_cast<int32_t>(millis() - next_sample_ms) > static_cast<int32_t>(SAMPLE_INTERVAL_MS)) {
      next_sample_ms = millis() + SAMPLE_INTERVAL_MS;
    }
  }

  uploadOneQueuedBatch(millis());
}
