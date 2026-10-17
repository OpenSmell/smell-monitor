// ui.cpp
#include "ui.h"
#include "config.h"
#include "proto.h"
#include <Arduino.h>
#include <math.h>
#include <Wire.h>
#include <U8g2lib.h>

// SSD1306 128x64 on the shared I2C bus.
static U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /*reset=*/U8X8_PIN_NONE);
static bool g_oled_ok = false;

void ui_begin() {
  pinMode(OS_PIN_LED, OUTPUT);
  digitalWrite(OS_PIN_LED, LOW);
  pinMode(OS_PIN_BUZZER, OUTPUT);
  digitalWrite(OS_PIN_BUZZER, LOW);
  u8g2.begin();
  g_oled_ok = true;  // U8g2 has no ACK report; assume present.
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
  if (!g_oled_ok) return;
  char line[24];
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(0, 9, FW_NAME " v" FW_VERSION);
  snprintf(line, sizeof(line), "WiFi:%s BLE:%s", wifi ? "on" : "-",
           ble ? "on" : "-");
  u8g2.drawStr(0, 20, line);           // own line: 128 px is too narrow to share

  u8g2.setFont(u8g2_font_9x15B_tf);
  u8g2.drawStr(0, 38, phase_name(phase));

  u8g2.setFont(u8g2_font_6x10_tf);
  if (isfinite(t_c) && isfinite(rh))
    snprintf(line, sizeof(line), "T %.1fC  RH %.0f%%", t_c, rh);
  else
    snprintf(line, sizeof(line), "T --    RH --");
  u8g2.drawStr(0, 50, line);
  if (isfinite(ao0))
    snprintf(line, sizeof(line), "AO0 %.2f V", ao0);
  else
    snprintf(line, sizeof(line), "AO0 --");
  u8g2.drawStr(0, 62, line);
  u8g2.sendBuffer();
}

void ui_beep(uint16_t ms) {
  tone(OS_PIN_BUZZER, 2700, ms);
}
