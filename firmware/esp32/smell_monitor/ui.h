// ui.h - OLED, status LED and buzzer (blueprint 5.6 / 7.6).
#pragma once

#include <stdint.h>

void ui_begin();
void ui_show(uint8_t phase, float t_c, float rh, float ao0,
             bool wifi, bool ble);
void ui_led(uint8_t phase, bool active);
void ui_beep(uint16_t ms);
