#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <mbedtls/md.h>
#include <time.h>

const char *WIFI_SSID = "COURTVISION_WIFI";
const char *WIFI_PASSWORD = "CHANGE_ME";
const char *AGENT_URL = "http://192.168.1.50:8790/v1/button/press";
const char *BUTTON_SECRET = "CHANGE_ME";
const char *DEVICE_ID = "CV-BTN-01";
constexpr uint8_t BUTTON_PIN = 27;

String hmacSha256(const String &value) {
  byte digest[32];
  mbedtls_md_context_t context;
  mbedtls_md_init(&context);
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  mbedtls_md_setup(&context, info, 1);
  mbedtls_md_hmac_starts(&context, reinterpret_cast<const unsigned char *>(BUTTON_SECRET), strlen(BUTTON_SECRET));
  mbedtls_md_hmac_update(&context, reinterpret_cast<const unsigned char *>(value.c_str()), value.length());
  mbedtls_md_hmac_finish(&context, digest);
  mbedtls_md_free(&context);
  String result;
  for (byte item : digest) {
    if (item < 16) result += "0";
    result += String(item, HEX);
  }
  return result;
}

String utcTimestamp() {
  time_t now = time(nullptr);
  struct tm tmNow;
  gmtime_r(&now, &tmNow);
  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &tmNow);
  return String(buffer);
}

void sendPress() {
  if (WiFi.status() != WL_CONNECTED) return;
  String eventId = String("press-") + String(millis());
  String pressedAt = utcTimestamp();
  String canonical = String(DEVICE_ID) + ":" + eventId + ":" + pressedAt;
  HTTPClient http;
  http.begin(AGENT_URL);
  http.addHeader("Content-Type", "application/json");
  String body = String("{\"device_id\":\"") + DEVICE_ID + "\",\"event_id\":\"" + eventId + "\",\"pressed_at\":\"" + pressedAt + "\",\"signature\":\"" + hmacSha256(canonical) + "\"}";
  http.POST(body);
  http.end();
}

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

void loop() {
  static bool previous = HIGH;
  bool current = digitalRead(BUTTON_PIN);
  if (previous == HIGH && current == LOW) sendPress();
  previous = current;
  delay(25);
}
