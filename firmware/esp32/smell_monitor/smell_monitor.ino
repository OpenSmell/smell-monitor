// smell_monitor.ino - OpenSmell v1.1 ESP32-WROOM-32E firmware entry point.
//
// Reads eight identical OSM-1 slots (two ADS1115s + TCA9548A) + SHT31, drives
// the fan/LED/buzzer, shows live status on the local SSD1306 and streams one
// JSON record per cycle over USB serial (default), Wi-Fi (MQTT + HTTP) and BLE.
// Field firmware updates arrive over HTTP OTA; USB serial is the recovery path.
#include "config.h"
#include "sensors.h"
#include "net.h"
#include "ui.h"
#include "ota.h"
#include "store.h"
#include "cycle.h"
#include "proto.h"
#include <Wire.h>

static void on_command(const char *cmd) {
  if (!strcmp(cmd, "measure")) cycle_request();
}

void setup() {
  ota_begin();                 // rollback bookkeeping before anything else
  store_begin();               // restore sequence + NVS record ring
  Wire.begin(OS_PIN_SDA, OS_PIN_SCL, 400000);

  ui_begin();                  // display, LED, buzzer, both buttons
  net_begin();
  net_on_command(on_command);

  bool adc_ok = Adc::begin();
  bool mux_ok = Mux::begin();
  bool sht_ok = Sht::begin();

  cycle_begin();

  // Power-on self-test line (blueprint 7.7).
  char b[192];
  snprintf(b, sizeof(b),
           "{\"boot\":\"" FW_VERSION "\",\"i2c\":{\"adc\":%d,\"mux\":%d,"
           "\"sht\":%d}}\n",
           adc_ok ? 1 : 0, mux_ok ? 1 : 0, sht_ok ? 1 : 0);
  Serial.print(b);

  ui_set_fault(!(adc_ok && mux_ok && sht_ok));
  ui_show(PH_IDLE, NAN, NAN, NAN, net_wifi_on(), net_ble_on());
  ota_confirm();               // new partition is only marked good after boot
}

void loop() {
  net_loop();                  // serial / BLE / HTTP commands (drives ota_loop)
  cycle_loop();
  ui_loop();                   // debounced buttons + display redraw
}
