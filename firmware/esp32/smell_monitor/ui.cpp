// ui.cpp - status LED and buzzer (blueprint 5.6 / 7.6).
//
// v1 is headless: no fitted display (U6 removed in the OSM-1 re-lay) and the
// UI is Osmograph.  Only the LED and buzzer remain.
#include "ui.h"
#include "config.h"
#include "proto.h"
#include <Arduino.h>
#include <math.h>

void ui_begin() {
  pinMode(OS_PIN_LED, OUTPUT);
  digitalWrite(OS_PIN_LED, LOW);
  pinMode(OS_PIN_BUZZER, OUTPUT);
  digitalWrite(OS_PIN_BUZZER, LOW);
}

void ui_led(uint8_t phase, bool active) {
  // IDLE: slow blink; active phases: solid; brief fast blink handled by caller
  // via ui_beep sequencing.  Kept deliberately simple on a single LED.
  static bool on = false;
  static uint32_t last = 0;
  uint32_t now = millis();
  if (phase == PH_IDLE) {
    if (now - last > 1000) { last = now; on = !on; }
  } else {
    on = active;
  }
  digitalWrite(OS_PIN_LED, on ? HIGH : LOW);
}

void ui_show(uint8_t phase, float t_c, float rh, float ao0,
             bool wifi, bool ble) {
  // No fitted display: nothing to draw.  Parameters kept for API stability;
  // the live record is streamed over serial/Wi-Fi/BLE instead.
  (void)phase; (void)t_c; (void)rh; (void)ao0; (void)wifi; (void)ble;
}

void ui_beep(uint16_t ms) {
  tone(OS_PIN_BUZZER, 2700, ms);
}
