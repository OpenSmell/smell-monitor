// ui.h - local SSD1306 display, two buttons, status LED and buzzer.
#pragma once

#include <stdint.h>

// Buttons (active low, INPUT_PULLUP), polled by ui_loop():
//   MEASURE/OK  short: start a cycle / ack a fault / mute / confirm reset
//   MENU        short: cycle display screen
//               >2 s:  WiFi setup AP
//               >5 s:  arm factory reset (confirmed with MEASURE/OK)
void ui_begin();
void ui_loop();

// Live status arrives from cycle.cpp; ui_show() throttles actual I2C writes.
void ui_show(uint8_t phase, float t_c, float rh, float ao0,
             bool wifi, bool ble);
// Latest profile-derived numbers for the values screen (and AQI label).
void ui_set_values(const float *derived, uint8_t count,
                   const char *aqi_label, float aqi);
void ui_set_aqi(float aqi, const char *label);   // convenience for net/host
void ui_set_fault(bool fault);
void ui_manual_text(const char *line1, const char *line2);
void ui_auto();                     // back to live status screens
void ui_screen_next();

void ui_led(uint8_t phase, bool active);
void ui_beep(uint16_t ms);
