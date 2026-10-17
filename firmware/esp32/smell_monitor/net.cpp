// net.cpp - USB serial + Wi-Fi (MQTT + HTTP) + BLE transports.
//
// One JSON record shape goes out over every enabled transport.  Radios are off
// by default (idle < 1 W, blueprint 7.5); enable with a button / command.
#include "net.h"
#include "config.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ---- BLE Nordic-UART-style service (phone apps speak this natively) --------
#define BLE_SERVICE "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define BLE_TX      "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  // notify
#define BLE_RX      "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  // write

// ---- state ----------------------------------------------------------------
static Preferences prefs;
static WebServer   server(80);
static WiFiClient  wifi_client;
static PubSubClient mqtt(wifi_client);

static bool g_wifi_on = false;
static bool g_ble_on  = false;
static bool g_wifi_connected = false;

static char g_ssid[33] = "";
static char g_pass[65] = "";
static char g_broker[64] = "";
static uint16_t g_broker_port = 1883;
static char g_topic[48] = "opensmell/record";

static char g_latest[512] = "{}";
static NetCommandFn g_on_command = nullptr;

// BLE writes arrive on the BLE stack task; hand them to the main loop instead
// of mutating loop-owned state from another task.
static char          g_ble_cmd[160];
static volatile bool g_ble_cmd_pending = false;

static BLEServer *g_ble_server = nullptr;
static BLECharacteristic *g_ble_tx = nullptr;
static BLECharacteristic *g_ble_rx = nullptr;

// ---------------------------------------------------------------------------
// config persistence
// ---------------------------------------------------------------------------
static void load_cfg() {
  prefs.begin("opensmell", true);
  prefs.getString("ssid", g_ssid, sizeof(g_ssid));
  prefs.getString("pass", g_pass, sizeof(g_pass));
  prefs.getString("broker", g_broker, sizeof(g_broker));
  g_broker_port = prefs.getUShort("port", 1883);
  prefs.getString("topic", g_topic, sizeof(g_topic));
  prefs.end();
}

static void save_cfg() {
  prefs.begin("opensmell", false);
  prefs.putString("ssid", g_ssid);
  prefs.putString("pass", g_pass);
  prefs.putString("broker", g_broker);
  prefs.putUShort("port", g_broker_port);
  prefs.putString("topic", g_topic);
  prefs.end();
}

// ---------------------------------------------------------------------------
// command dispatch (shared by serial / BLE / HTTP)
// ---------------------------------------------------------------------------
void net_dispatch(const char *cmd) {
  if (!cmd || !*cmd) return;

  if (!strncmp(cmd, "wifi on", 7))  { net_set_wifi(true);  return; }
  if (!strncmp(cmd, "wifi off", 8)) { net_set_wifi(false); return; }
  if (!strncmp(cmd, "ble on", 6))   { net_set_ble(true);   return; }
  if (!strncmp(cmd, "ble off", 7))  { net_set_ble(false);  return; }

  if (!strncmp(cmd, "wifi ", 5) && strncmp(cmd, "wifi on", 7) &&
      strncmp(cmd, "wifi off", 8)) {
    // "wifi <ssid> <pass>"
    char tmp[130];
    strncpy(tmp, cmd + 5, sizeof(tmp) - 1);
    tmp[sizeof(tmp) - 1] = 0;
    char *sp = strchr(tmp, ' ');
    if (sp) {
      *sp = 0;
      strncpy(g_ssid, tmp, sizeof(g_ssid) - 1);
      strncpy(g_pass, sp + 1, sizeof(g_pass) - 1);
      save_cfg();
      net_set_wifi(true);
    }
    return;
  }

  if (!strncmp(cmd, "mqtt ", 5)) {
    // "mqtt <host> [port]"
    char tmp[96];
    strncpy(tmp, cmd + 5, sizeof(tmp) - 1);
    tmp[sizeof(tmp) - 1] = 0;
    char *sp = strchr(tmp, ' ');
    if (sp) { *sp = 0; g_broker_port = (uint16_t)atoi(sp + 1); }
    strncpy(g_broker, tmp, sizeof(g_broker) - 1);
    save_cfg();
    return;
  }

  if (!strcmp(cmd, "measure") || !strcmp(cmd, "start")) {
    if (g_on_command) g_on_command("measure");
    return;
  }

  if (!strcmp(cmd, "status")) {
    char b[160];
    snprintf(b, sizeof(b),
             "{\"fw\":\"" FW_VERSION "\",\"wifi\":%d,\"ble\":%d,"
             "\"ssid\":\"%s\",\"broker\":\"%s\"}\n",
             g_wifi_on, g_ble_on, g_ssid, g_broker);
    Serial.print(b);
    return;
  }
}

void net_on_command(NetCommandFn fn) { g_on_command = fn; }

// ---------------------------------------------------------------------------
// Wi-Fi + MQTT + HTTP
// ---------------------------------------------------------------------------
static void start_wifi() {
  if (!g_wifi_on) return;
  WiFi.mode(WIFI_STA);
  if (g_ssid[0]) {
    WiFi.begin(g_ssid, g_pass);
  } else {
    // No credentials yet: raise a password-protected setup AP.
    WiFi.mode(WIFI_AP);
    WiFi.softAP("OpenSmell-setup", "opensmell");
  }
  server.begin();
}

static void stop_wifi() {
  server.stop();
  mqtt.disconnect();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  g_wifi_connected = false;
}

static void mqtt_ensure() {
  if (!g_wifi_connected || !g_broker[0] || mqtt.connected()) return;
  mqtt.setServer(g_broker, g_broker_port);
  // Record + topic exceed PubSubClient's 256-byte default.
  mqtt.setBufferSize(768);
  if (mqtt.connect(FW_NAME "-" FW_VERSION)) {
    mqtt.publish((String(g_topic) + "/status").c_str(), "\"online\"");
  }
}

static void http_setup() {
  server.on("/", HTTP_GET, []() {
    String h = F("<!doctype html><title>OpenSmell</title><h3>OpenSmell "
                 FW_VERSION "</h3><p><a href=\"/data\">/data</a></p>");
    server.send(200, "text/html", h);
  });
  server.on("/data", HTTP_GET, []() {
    server.send(200, "application/json", g_latest);
  });
  server.on("/measure", HTTP_POST, []() {
    if (g_on_command) g_on_command("measure");
    server.send(200, "application/json", "{\"ok\":true}");
  });
  server.on("/cmd", HTTP_POST, []() {
    if (server.hasArg("c")) net_dispatch(server.arg("c").c_str());
    server.send(200, "application/json", "{\"ok\":true}");
  });
}

void net_set_wifi(bool on) {
  if (on == g_wifi_on) return;
  g_wifi_on = on;
  if (on) start_wifi(); else stop_wifi();
}

bool net_wifi_on() { return g_wifi_on; }
bool net_ble_on()  { return g_ble_on; }

// ---------------------------------------------------------------------------
// BLE
// ---------------------------------------------------------------------------
class BleRxCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String v = c->getValue();
    if (!v.length()) return;
    size_t n = v.length();
    if (n > sizeof(g_ble_cmd) - 1) n = sizeof(g_ble_cmd) - 1;
    memcpy(g_ble_cmd, v.c_str(), n);
    g_ble_cmd[n] = 0;
    g_ble_cmd_pending = true;   // drained on the main loop (see net_loop)
  }
};

class BleServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { /* could resend state */ }
  void onDisconnect(BLEServer *s) override { s->startAdvertising(); }
};

static void start_ble() {
  BLEDevice::init(FW_NAME);
  BLEDevice::setMTU(517);              // ask for the max; notify() still chunks
  g_ble_server = BLEDevice::createServer();
  g_ble_server->setCallbacks(new BleServerCallbacks());
  BLEService *svc = g_ble_server->createService(BLE_SERVICE);

  g_ble_tx = svc->createCharacteristic(
      BLE_TX, BLECharacteristic::PROPERTY_NOTIFY);
  g_ble_tx->addDescriptor(new BLE2902());

  g_ble_rx = svc->createCharacteristic(
      BLE_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  g_ble_rx->setCallbacks(new BleRxCallbacks());

  svc->start();
  BLEAdvertising *adv = g_ble_server->getAdvertising();
  adv->addServiceUUID(BLE_SERVICE);
  adv->start();
}

static void stop_ble() {
  BLEDevice::deinit(true);
  g_ble_server = nullptr;
  g_ble_tx = nullptr;
  g_ble_rx = nullptr;
}

void net_set_ble(bool on) {
  if (on == g_ble_on) return;
  g_ble_on = on;
  if (on) start_ble(); else stop_ble();
}

// ---------------------------------------------------------------------------
// lifecycle
// ---------------------------------------------------------------------------
void net_begin() {
  Serial.begin(SERIAL_BAUD);
  load_cfg();
  http_setup();
  // Radios intentionally left off.
}

static void poll_serial() {
  static char buf[160];
  static size_t n = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      buf[n] = 0;
      if (n) net_dispatch(buf);
      n = 0;
    } else if (n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
}

void net_loop() {
  poll_serial();

  if (g_ble_cmd_pending) {
    g_ble_cmd_pending = false;
    net_dispatch(g_ble_cmd);
  }

  if (g_wifi_on) {
    g_wifi_connected = (WiFi.status() == WL_CONNECTED);
    if (g_wifi_connected) {
      mqtt_ensure();
      mqtt.loop();
    }
    server.handleClient();
  }
}

void net_publish(const char *json) {
  strncpy(g_latest, json, sizeof(g_latest) - 1);
  g_latest[sizeof(g_latest) - 1] = 0;

  Serial.println(json);                              // USB serial (default)
  if (g_wifi_on && g_wifi_connected && mqtt.connected())
    mqtt.publish(g_topic, json);                     // Wi-Fi / MQTT
  if (g_ble_on && g_ble_tx) {                        // BLE notify
    // Notify is limited to (ATT_MTU - 3) bytes; the default MTU gives 20.
    // Chunk so the record survives even when the peer never negotiates.
    size_t len = strlen(json), off = 0;
    const size_t CHUNK = 20;
    while (off < len) {
      size_t k = len - off; if (k > CHUNK) k = CHUNK;
      g_ble_tx->setValue((uint8_t *)(json + off), k);
      g_ble_tx->notify();
      off += k;
      if (off < len) delay(6);                       // let the stack drain
    }
  }
}
