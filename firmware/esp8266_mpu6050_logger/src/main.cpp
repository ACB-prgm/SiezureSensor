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
constexpr bool ENABLE_STARTUP_I2C_SCAN = true;
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 10000;
constexpr uint32_t HTTP_TIMEOUT_MS = 5000;

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

struct ImuReading {
  float ax_g;
  float ay_g;
  float az_g;
  float gx_dps;
  float gy_dps;
  float gz_dps;
};

struct BatchSample {
  uint32_t dt_ms;
  ImuReading reading;
};

BatchSample batch_samples[SAMPLES_PER_BATCH];
uint32_t next_sample_ms = 0;
uint32_t next_wifi_retry_ms = 0;
uint32_t batch_device_ms_start = 0;
uint32_t batch_sequence = 0;
uint16_t batch_sample_count = 0;
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
      Serial.println(WiFi.localIP());
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

bool readImu(ImuReading &reading) {
  uint8_t buffer[14] = {0};
  if (!readRegisters(MPU6050_REG_ACCEL_XOUT_H, buffer, sizeof(buffer))) {
    return false;
  }

  const int16_t raw_ax = readInt16(buffer[0], buffer[1]);
  const int16_t raw_ay = readInt16(buffer[2], buffer[3]);
  const int16_t raw_az = readInt16(buffer[4], buffer[5]);
  const int16_t raw_gx = readInt16(buffer[8], buffer[9]);
  const int16_t raw_gy = readInt16(buffer[10], buffer[11]);
  const int16_t raw_gz = readInt16(buffer[12], buffer[13]);

  reading.ax_g = static_cast<float>(raw_ax) / ACCEL_LSB_PER_G;
  reading.ay_g = static_cast<float>(raw_ay) / ACCEL_LSB_PER_G;
  reading.az_g = static_cast<float>(raw_az) / ACCEL_LSB_PER_G;
  reading.gx_dps = static_cast<float>(raw_gx) / GYRO_LSB_PER_DPS;
  reading.gy_dps = static_cast<float>(raw_gy) / GYRO_LSB_PER_DPS;
  reading.gz_dps = static_cast<float>(raw_gz) / GYRO_LSB_PER_DPS;

  return true;
}

void resetBatch(uint32_t next_start_ms) {
  batch_device_ms_start = next_start_ms;
  batch_sample_count = 0;
}

void appendSampleToBatch(uint32_t sample_ms, const ImuReading &reading) {
  if (batch_sample_count == 0) {
    batch_device_ms_start = sample_ms;
  }

  batch_samples[batch_sample_count] = BatchSample{
      sample_ms - batch_device_ms_start,
      reading,
  };
  batch_sample_count++;
}

bool isBatchReady() {
  return batch_sample_count >= SAMPLES_PER_BATCH;
}

void printBatchPrepared() {
  Serial.print("Batch prepared: sequence=");
  Serial.print(batch_sequence);
  Serial.print(", samples=");
  Serial.print(batch_sample_count);
  Serial.print(", device_ms_start=");
  Serial.println(batch_device_ms_start);
}

String uploadUrl() {
  String base_url = SERVER_URL;
  if (base_url.endsWith("/")) {
    base_url.remove(base_url.length() - 1);
  }
  return base_url + "/api/v1/imu/batch";
}

String buildBatchJson(uint32_t sequence) {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["firmware_version"] = FIRMWARE_VERSION;
  doc["session_id"] = SESSION_ID;
  doc["sequence"] = sequence;
  doc["sample_hz"] = 50;
  doc["device_ms_start"] = batch_device_ms_start;
  doc["battery_mv"] = nullptr;

  JsonArray samples = doc["samples"].to<JsonArray>();
  for (uint16_t i = 0; i < batch_sample_count; i++) {
    JsonObject sample = samples.add<JsonObject>();
    sample["dt_ms"] = batch_samples[i].dt_ms;
    sample["ax"] = batch_samples[i].reading.ax_g;
    sample["ay"] = batch_samples[i].reading.ay_g;
    sample["az"] = batch_samples[i].reading.az_g;
    sample["gx"] = batch_samples[i].reading.gx_dps;
    sample["gy"] = batch_samples[i].reading.gy_dps;
    sample["gz"] = batch_samples[i].reading.gz_dps;
  }

  String payload;
  serializeJson(doc, payload);
  return payload;
}

void uploadBatch(uint32_t sequence) {
  if (!isWiFiConnected()) {
    Serial.println("Skipping upload: Wi-Fi is not connected.");
    return;
  }

  const String url = uploadUrl();
  const String payload = buildBatchJson(sequence);
  WiFiClient client;
  HTTPClient http;

  Serial.print("Uploading batch sequence=");
  Serial.print(sequence);
  Serial.print(", bytes=");
  Serial.print(payload.length());
  Serial.print(", url=");
  Serial.println(url);

  http.setTimeout(HTTP_TIMEOUT_MS);
  if (!http.begin(client, url)) {
    Serial.println("HTTP begin failed; dropping batch.");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  const int status_code = http.POST(payload);
  Serial.print("Upload HTTP status: ");
  Serial.println(status_code);

  if (status_code > 0) {
    Serial.print("Upload response: ");
    Serial.println(http.getString());
  } else {
    Serial.print("Upload failed: ");
    Serial.println(http.errorToString(status_code));
  }

  http.end();
}
} // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);

  Serial.println();
  Serial.println("Dog Seizure Sensor V0 - ESP8266 MPU-6050 bench read");
  Serial.println("Expected MPU-6050 address: 0x68");
  Serial.println("Wiring: SDA=D2/GPIO4, SCL=D1/GPIO5, VCC=3V3, GND=GND");
  Serial.print("Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("Session ID: ");
  Serial.println(SESSION_ID);
  Serial.print("Server URL: ");
  Serial.println(SERVER_URL);

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
  resetBatch(next_sample_ms);
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
        resetBatch(next_sample_ms);
      }
      next_retry_ms = now_ms + 1000;
    }
    return;
  }

  if (static_cast<int32_t>(now_ms - next_sample_ms) >= 0) {
    ImuReading reading = {};
    if (readImu(reading)) {
      appendSampleToBatch(now_ms, reading);
      if (isBatchReady()) {
        const uint32_t prepared_sequence = batch_sequence;
        printBatchPrepared();
        uploadBatch(prepared_sequence);
        batch_sequence++;
        const uint32_t resume_ms = millis() + SAMPLE_INTERVAL_MS;
        next_sample_ms = resume_ms;
        resetBatch(resume_ms);
        return;
      }
    } else {
      Serial.println("IMU read failed. Will retry initialization.");
      imu_ready = false;
    }

    next_sample_ms += SAMPLE_INTERVAL_MS;
    if (static_cast<int32_t>(millis() - next_sample_ms) > static_cast<int32_t>(SAMPLE_INTERVAL_MS)) {
      next_sample_ms = millis() + SAMPLE_INTERVAL_MS;
    }
  }
}
