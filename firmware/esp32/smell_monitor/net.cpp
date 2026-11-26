// net.cpp - USB serial + Wi-Fi (MQTT + HTTP) + BLE transports.
//
// One JSON record shape goes out over every enabled transport.  Radios are off
// by default (idle < 1 W, blueprint 7.5); enable with a button / command.
#include "net.h"
#include "config.h"
#include "cycle.h"
#include "ota.h"
#include "profile.h"
#include "store.h"
#include "ui.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <esp_sntp.h>
#include <time.h>
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
static bool g_force_ap = false;      // MENU long press: always raise setup AP

static char g_disp1[17] = "";
static char g_disp2[17] = "";
static bool g_disp_manual = false;

static char g_ssid[33] = "";
static char g_pass[65] = "";
static char g_broker[64] = "";
static uint16_t g_broker_port = 1883;
static char g_topic[48] = "opensmell/record";
static char g_mqtt_user[33] = "";     // optional, anonymous by default
static char g_mqtt_pass[65] = "";
static char g_ntp_host[64] = "pool.ntp.org";
static bool g_sntp_running = false;
static bool g_time_synced = false;

static char g_latest[4096] = "{}";   // one full 8-slot .osmell record
static NetCommandFn g_on_command = nullptr;

// BLE writes arrive on the BLE stack task; hand them to the main loop instead
// of mutating loop-owned state from another task.
static char          g_ble_cmd[512];
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
  prefs.getString("mqtt_user", g_mqtt_user, sizeof(g_mqtt_user));
  prefs.getString("mqtt_pass", g_mqtt_pass, sizeof(g_mqtt_pass));
  prefs.getString("ntp", g_ntp_host, sizeof(g_ntp_host));
  if (!g_ntp_host[0]) strcpy(g_ntp_host, "pool.ntp.org");
  prefs.getString("disp1", g_disp1, sizeof(g_disp1));
  prefs.getString("disp2", g_disp2, sizeof(g_disp2));
  g_disp_manual = prefs.getBool("disp_manual", false);

  CycleConfig c = cycle_get_config();
  c.fan_intake  = prefs.getUChar ("fan_in",  c.fan_intake);
  c.fan_hold    = prefs.getUChar ("fan_hold", c.fan_hold);
  c.fan_purge   = prefs.getUChar ("fan_purge",c.fan_purge);
  c.t_intake_ms = prefs.getUInt  ("t_in",    c.t_intake_ms);
  c.t_hold_ms   = prefs.getUInt  ("t_hold",  c.t_hold_ms);
  c.t_purge_ms  = prefs.getUInt  ("t_purge", c.t_purge_ms);
  c.sweep_ms    = prefs.getUShort("sweep",   c.sweep_ms);
  c.muted       = prefs.getBool  ("muted",   c.muted);
  cycle_set_config(c);

  prefs.end();
  // ui_begin() has already run when net_begin() loads configuration.
  if (g_disp_manual) ui_manual_text(g_disp1, g_disp2);
  else ui_auto();
}

static void save_cfg() {
  prefs.begin("opensmell", false);
  prefs.putString("ssid", g_ssid);
  prefs.putString("pass", g_pass);
  prefs.putString("broker", g_broker);
  prefs.putUShort("port", g_broker_port);
  prefs.putString("topic", g_topic);
  prefs.putString("mqtt_user", g_mqtt_user);
  prefs.putString("mqtt_pass", g_mqtt_pass);
  prefs.putString("ntp", g_ntp_host);
  prefs.putString("disp1", g_disp1);
  prefs.putString("disp2", g_disp2);
  prefs.putBool("disp_manual", g_disp_manual);

  CycleConfig c = cycle_get_config();
  prefs.putUChar ("fan_in",  c.fan_intake);
  prefs.putUChar ("fan_hold", c.fan_hold);
  prefs.putUChar ("fan_purge",c.fan_purge);
  prefs.putUInt  ("t_in",    c.t_intake_ms);
  prefs.putUInt  ("t_hold",  c.t_hold_ms);
  prefs.putUInt  ("t_purge", c.t_purge_ms);
  prefs.putUShort("sweep",   c.sweep_ms);
  prefs.putBool  ("muted",   c.muted);

  prefs.end();
}

// ---------------------------------------------------------------------------
// Wall clock (SNTP).  Started only while Wi-Fi STA is connected; all calls
// are non-blocking and never delay boot or a measurement cycle.
// ---------------------------------------------------------------------------
static void ntp_start() {
  if (g_sntp_running || !g_wifi_connected || WiFi.status() != WL_CONNECTED)
    return;                                  // no NTP in setup AP / Wi-Fi off
  esp_sntp_setoperatingmode(ESP_SNTP_OPMODE_POLL);
  esp_sntp_setservername(0, g_ntp_host);
  esp_sntp_init();
  g_sntp_running = true;
}

static void ntp_stop() {
  if (!g_sntp_running) return;
  esp_sntp_stop();
  g_sntp_running = false;
}

size_t net_wall_clock(char *buf, size_t n) {
  if (!buf || !n) return 0;
  buf[0] = 0;
  // 2025-01-01: reject the unsynced epoch (1970) and any absurd pre-2025 time.
  if (!g_time_synced || time(nullptr) < 1735689600L) return 0;
  struct tm utc;
  time_t now = time(nullptr);
  if (!gmtime_r(&now, &utc)) return 0;
  size_t len = strftime(buf, n, "%Y-%m-%dT%H:%M:%SZ", &utc);
  if (!len) buf[0] = 0;
  return len;
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

  // "ntp <host>" (default pool.ntp.org), or "ntp" / "ntp status" to inspect.
  // SNTP is restarted in net_loop() only if Wi-Fi STA is actually connected.
  if (!strcmp(cmd, "ntp") || !strcmp(cmd, "ntp status") ||
      !strncmp(cmd, "ntp ", 4)) {
    if (!strcmp(cmd, "ntp") || !strcmp(cmd, "ntp status")) {
      char clk[25];
      net_wall_clock(clk, sizeof(clk));
      Serial.printf("{\"ntp\":\"%s\",\"synced\":%d,\"utc\":\"%s\"}\n",
                    g_ntp_host, g_time_synced ? 1 : 0, clk[0] ? clk : "");
      return;
    }
    char host[sizeof(g_ntp_host)];
    strncpy(host, cmd + 4, sizeof(host) - 1);
    host[sizeof(host) - 1] = 0;
    if (!host[0]) { Serial.print("?ntp <host>\n"); return; }
    strncpy(g_ntp_host, host, sizeof(g_ntp_host) - 1);
    g_ntp_host[sizeof(g_ntp_host) - 1] = 0;
    save_cfg();
    if (g_sntp_running) { ntp_stop(); ntp_start(); }
    Serial.printf("{\"ok\":true,\"ntp\":\"%s\"}\n", g_ntp_host);
    return;
  }

  // "mqtt auth <user> <pass>" - optional credentials, persisted in NVS.
  if (!strncmp(cmd, "mqtt auth ", 10)) {
    char user[sizeof(g_mqtt_user)], pass[sizeof(g_mqtt_pass)];
    if (sscanf(cmd + 10, "%32s %64s", user, pass) == 2) {
      strncpy(g_mqtt_user, user, sizeof(g_mqtt_user) - 1);
      strncpy(g_mqtt_pass, pass, sizeof(g_mqtt_pass) - 1);
      save_cfg();
      mqtt.disconnect();                   // reconnect with new credentials
      Serial.print("{\"ok\":true,\"mqtt\":\"auth\"}\n");
    } else {
      Serial.print("?mqtt auth <user> <pass>\n");
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

  // "fan <intake|hold|purge> <0-255>" - PWM duty, persisted in NVS.
  if (!strncmp(cmd, "fan ", 4)) {
    char area[12];
    unsigned v = 0;
    if (sscanf(cmd + 4, "%11s %u", area, &v) == 2 && v <= 255) {
      CycleConfig c = cycle_get_config();
      if      (!strcmp(area, "intake")) c.fan_intake = (uint8_t)v;
      else if (!strcmp(area, "hold"))   c.fan_hold   = (uint8_t)v;
      else if (!strcmp(area, "purge"))  c.fan_purge  = (uint8_t)v;
      else { Serial.print("?fan area: intake|hold|purge\n"); return; }
      cycle_set_config(c);
      save_cfg();
    } else {
      Serial.print("?fan <intake|hold|purge> <0-255>\n");
    }
    return;
  }

  // "rate <ms>" - ADC read interval during HOLD (20..5000 ms).
  if (!strncmp(cmd, "rate ", 5)) {
    unsigned ms = (unsigned)atoi(cmd + 5);
    if (ms >= 20 && ms <= 5000) {
      CycleConfig c = cycle_get_config();
      c.sweep_ms = (uint16_t)ms;
      cycle_set_config(c);
      save_cfg();
    } else {
      Serial.print("?rate <20-5000>\n");
    }
    return;
  }

  // "timing <intake_ms> <hold_ms> <purge_ms>" - phase lengths (0.1..300 s).
  if (!strncmp(cmd, "timing ", 7)) {
    unsigned a = 0, h = 0, p = 0;
    if (sscanf(cmd + 7, "%u %u %u", &a, &h, &p) == 3 &&
        a >= 100 && a <= 300000 && h >= 100 && h <= 300000 &&
        p >= 100 && p <= 300000) {
      CycleConfig c = cycle_get_config();
      c.t_intake_ms = a; c.t_hold_ms = h; c.t_purge_ms = p;
      cycle_set_config(c);
      save_cfg();
    } else {
      Serial.print("?timing <100-300000> <100-300000> <100-300000>\n");
    }
    return;
  }

  if (!strcmp(cmd, "mute") || !strcmp(cmd, "unmute")) {
    CycleConfig c = cycle_get_config();
    c.muted = (cmd[0] == 'm');
    cycle_set_config(c);
    save_cfg();
    return;
  }

  if (!strcmp(cmd, "measure") || !strcmp(cmd, "start")) {
    if (g_on_command) g_on_command("measure");
    return;
  }

  // "display <line1>|<line2>" - persistent manual text on the local OLED.
  // "display auto" returns to the live status screens.
  if (!strcmp(cmd, "display") || !strncmp(cmd, "display ", 8)) {
    if (!strcmp(cmd, "display")) {
      Serial.print("?display <line1>|<line2> | display auto\n");
      return;
    }
    const char *arg = cmd + 8;
    if (!strcmp(arg, "auto")) {
      g_disp_manual = false;
      save_cfg();
      ui_auto();
      Serial.print("{\"ok\":true,\"display\":\"auto\"}\n");
      return;
    }
    const char *bar = strchr(arg, '|');
    size_t n1 = bar ? (size_t)(bar - arg) : strlen(arg);
    if (n1 >= sizeof(g_disp1)) n1 = sizeof(g_disp1) - 1;
    memset(g_disp1, 0, sizeof(g_disp1));
    memcpy(g_disp1, arg, n1);
    memset(g_disp2, 0, sizeof(g_disp2));
    if (bar) {
      size_t n2 = strlen(bar + 1);
      if (n2 >= sizeof(g_disp2)) n2 = sizeof(g_disp2) - 1;
      memcpy(g_disp2, bar + 1, n2);
    }
    g_disp_manual = true;
    save_cfg();
    ui_manual_text(g_disp1, g_disp2);
    Serial.print("{\"ok\":true,\"display\":\"manual\"}\n");
    return;
  }

  // "profile <json>" / "profile clear" / "profile get".
  if (!strcmp(cmd, "profile") || !strncmp(cmd, "profile ", 8)) {
    const char *arg = cmd[7] ? cmd + 8 : "";
    if (!strcmp(arg, "clear")) {
      Profile::clear();
      Serial.print("{\"ok\":true,\"profile\":null}\n");
    } else if (!strcmp(arg, "get")) {
      char raw[1100];
      if (Profile::get_json(raw, sizeof(raw))) Serial.print(raw);
      else Serial.print("null");
      Serial.print("\n");
    } else if (!strcmp(arg, "")) {
      Serial.print("?profile <json> | profile clear | profile get\n");
    } else if (Profile::set_json(arg)) {
      Serial.print("{\"ok\":true}\n");
    } else {
      Serial.print("?profile invalid JSON\n");
    }
    return;
  }

  // "ota <url> <sha256>" - host-signed manifest must live at <url>.json.
  // "ota status" reports progress without starting a download.
  if (!strcmp(cmd, "ota") || !strncmp(cmd, "ota ", 4)) {
    if (!strcmp(cmd, "ota status")) {
      char b[256];
      ota_status(b, sizeof(b));
      Serial.print(b);
      Serial.print("\n");
      return;
    }
    char url[160], digest[65];
    if (!strncmp(cmd, "ota ", 4) &&
        sscanf(cmd + 4, "%159s %64s", url, digest) == 2) {
      if (ota_start(url, digest)) Serial.print("{\"ok\":true,\"ota\":\"queued\"}\n");
      else Serial.print("?ota busy or invalid arguments\n");
    } else {
      Serial.print("?ota <url> <sha256> | ota status\n");
    }
    return;
  }

  // "replay [since]" - dump the persisted NVS ring as a JSON array. With no
  // argument, since=0 emits every buffered record (oldest surviving first).
  if (!strcmp(cmd, "replay") || !strncmp(cmd, "replay ", 7)) {
    uint32_t since = (cmd[6] == ' ')
        ? (uint32_t)strtoul(cmd + 7, nullptr, 10) : 0;
    String body;
    store_write_replay(since, body);
    Serial.println(body);
    return;
  }

  if (!strcmp(cmd, "status")) {
    CycleConfig c = cycle_get_config();
    char b[448];
    snprintf(b, sizeof(b),
             "{\"fw\":\"" FW_VERSION "\",\"wifi\":%d,\"ble\":%d,"
             "\"ssid\":\"%s\",\"broker\":\"%s\",\"sequence\":%lu,"
             "\"ntp\":\"%s\",\"synced\":%d,"
             "\"fan\":[%u,%u,%u],\"timing_ms\":[%lu,%lu,%lu],"
             "\"rate_ms\":%u,\"muted\":%d}\n",
             g_wifi_on, g_ble_on, g_ssid, g_broker,
             (unsigned long)store_last_sequence(),
             g_ntp_host, g_time_synced ? 1 : 0,
             (unsigned)c.fan_intake, (unsigned)c.fan_hold,
             (unsigned)c.fan_purge,
             (unsigned long)c.t_intake_ms, (unsigned long)c.t_hold_ms,
             (unsigned long)c.t_purge_ms,
             (unsigned)c.sweep_ms, c.muted ? 1 : 0);
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
  if (g_force_ap || !g_ssid[0]) {
    // No credentials (or MENU long press): password-protected setup AP.
    WiFi.mode(WIFI_AP);
    WiFi.softAP("OpenSmell-setup", "opensmell");
  } else {
    WiFi.mode(WIFI_STA);
    WiFi.begin(g_ssid, g_pass);
  }
  server.begin();
}

static void stop_wifi() {
  server.stop();
  ntp_stop();
  if (mqtt.connected()) {
    // Graceful disconnect does not trigger the LWT; make retained status
    // consistent in that case too.
    mqtt.publish((String(g_topic) + "/status").c_str(), "\"offline\"", true);
  }
  mqtt.disconnect();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  g_wifi_connected = false;
  g_force_ap = false;
}

void net_enter_ap() {
  // net_set_wifi(true) is a no-op while already on; cycle it so a connected
  // STA setup is replaced by the setup AP.
  if (g_wifi_on) net_set_wifi(false);   // stop_wifi() clears g_force_ap
  g_force_ap = true;
  net_set_wifi(true);
}

void net_factory_reset() {
  Preferences p;
  p.begin("opensmell", false);  p.clear(); p.end();
  p.begin("opensmellpf", false); p.clear(); p.end();
  store_factory_reset();
  ota_factory_reset();
  ESP.restart();
}

static void mqtt_ensure() {
  if (!g_wifi_connected || !g_broker[0] || mqtt.connected()) return;
  mqtt.setServer(g_broker, g_broker_port);
  // Record + topic exceed PubSubClient's 256-byte default.
  mqtt.setBufferSize(768);

  // Unique per device so two monitors do not evict each other's session.
  char client_id[64];
  snprintf(client_id, sizeof(client_id), "%s-%s-%08lX",
           FW_NAME, FW_VERSION,
           (unsigned long)((uint32_t)ESP.getEfuseMac() & 0xFFFFFFFFUL));
  const String status_topic = String(g_topic) + "/status";

  // Retained LWT: the broker stores "offline" NOW and publishes it to
  // <topic>/status if this client disconnects ungracefully.
  if (mqtt.connect(client_id, g_mqtt_user, g_mqtt_pass,
                   status_topic.c_str(), 1, true, "\"offline\"")) {
    // Take over the retained slot immediately after connecting.
    mqtt.publish(status_topic.c_str(), "\"online\"", true);
  }
}

static void http_setup() {
  server.on("/", HTTP_GET, []() {
    String h = F("<!doctype html><title>OpenSmell</title><h3>OpenSmell "
                 FW_VERSION "</h3><p><a href=\"/data\">/data</a></p>");
    server.send(200, "text/html", h);
  });
  // NOTE: /data is now a JSON ARRAY of the persisted NVS ring (additive
  // change from the previous single-object body); /latest keeps the old
  // single-record body for hosts that only want the last record.
  // /data?since=<seq> returns only records with sequence > <seq>.
  server.on("/data", HTTP_GET, []() {
    uint32_t since = server.hasArg("since")
        ? (uint32_t)strtoul(server.arg("since").c_str(), nullptr, 10) : 0;
    String body;
    store_write_replay(since, body);
    server.send(200, "application/json", body);
  });
  server.on("/latest", HTTP_GET, []() {
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
  // POST /display?c=display%20LINE1%7CLINE2 (or via /cmd with the same text).
  server.on("/display", HTTP_POST, []() {
    if (server.hasArg("c")) {
      String c = server.arg("c");
      if (!c.startsWith("display")) c = "display " + c;
      net_dispatch(c.c_str());
    }
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
  Profile::load();
  load_cfg();
  http_setup();
  // Radios intentionally left off.
}

static void poll_serial() {
  // Long enough for a full eight-slot profile JSON on one serial line.
  static char buf[1200];
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
      ntp_start();                       // no-op unless SNTP is not running
      if (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED)
        g_time_synced = true;
      mqtt_ensure();
      mqtt.loop();
    } else {
      ntp_stop();                        // never poll NTP while Wi-Fi is down
    }
    server.handleClient();
  }
  ota_loop();   // OTA state machine; self-gates on WiFi + pending request
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
