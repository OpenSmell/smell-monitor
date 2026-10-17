// smell_monitor.ino - OpenSmell v1.1 ESP32-WROOM-32E firmware entry point.
//
// Reads 4 analog slots (ADS1115) + 4 digital slots (TCA9548A) + SHT31, drives
// the fan/LED/buzzer/OLED, and streams one JSON record per cycle over USB
// serial (default), Wi-Fi (MQTT + HTTP) and BLE.
#include "config.h"
#include "sensors.h"
#include "net.h"
#include "ui.h"
#include "cycle.h"
#include "proto.h"
#include <Wire.h>

static void on_command(const char *cmd) {
  if (!strcmp(cmd, "measure")) cycle_request();
}

void setup() {
  Wire.begin(OS_PIN_SDA, OS_PIN_SCL, 400000);

  ui_begin();
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

  ui_show(PH_IDLE, NAN, NAN, 0.0f, false, false);
}

void loop() {
  net_loop();
  cycle_loop();
}
