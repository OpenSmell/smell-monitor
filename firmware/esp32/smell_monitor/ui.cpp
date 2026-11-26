// ui.cpp - local SSD1306, two debounced buttons, status LED and buzzer.
//
// MEASURE (short) = start / ack / mute (and confirm a pending factory reset).
// MENU    (short) = next display screen.
// MENU    (>2 s)  = WiFi setup AP (WebServer at 192.168.4.1).
// MENU    (>5 s)  = arm factory reset; MEASURE confirms, MENU cancels.
// LED and buzzer behaviour is unchanged from v1.1.
#include "ui.h"
#include "config.h"
#include "cycle.h"
#include "display.h"
#include "net.h"
#include "proto.h"
#include <Arduino.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

namespace {

const uint32_t DEBOUNCE_MS = 30;
const uint32_t LONG_MS     = 2000;
const uint32_t VLONG_MS    = 5000;
const uint32_t CONFIRM_MS  = 10000;
const uint32_t BANNER_MS   = 8000;
const uint32_t REDRAW_MS   = 400;

enum Screen : uint8_t { SCR_STATUS = 0, SCR_VALUES, SCR_MANUAL, SCR_COUNT };
enum Mode : uint8_t { MODE_AUTO = 0, MODE_MANUAL, MODE_RESET_CONFIRM };

struct Button {
  uint8_t  pin;
  bool     raw;           // debounced electrical level (true = pressed)
  bool     down;
  uint32_t t_change;      // last raw edge, for debounce
  uint32_t t_down;
  bool     long_fired;
  bool     vlong_fired;
};

Button g_btn_measure = {OS_PIN_BUTTON, false, false, 0, 0, false, false};
Button g_btn_menu    = {OS_PIN_BUTTON_MENU, false, false, 0, 0, false, false};

Mode     g_mode = MODE_AUTO;
Screen   g_screen = SCR_STATUS;
bool     g_fault = false;
bool     g_force = true;
uint32_t g_last_draw = 0;
uint8_t  g_last_phase = 255;

char     g_manual[2][17] = {{0}, {0}};
char     g_banner[2][17] = {{0}, {0}};
uint32_t g_banner_until = 0;
uint32_t g_confirm_until = 0;

float    g_values[8] = {NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN};
char     g_aqi_label[16] = "";
float    g_aqi = NAN;

uint8_t  g_phase = PH_IDLE;
float    g_t = NAN, g_rh = NAN, g_ao0 = NAN;
bool     g_wifi = false, g_ble = false;

void number(char *dst, size_t n, float v, int prec) {
  if (!isfinite(v)) snprintf(dst, n, "--");
  else snprintf(dst, n, "%.*f", prec, (double)v);
}

void draw() {
  DisplayView v;
  memset(&v, 0, sizeof(v));
  const bool banner = millis() < g_banner_until && g_banner[0][0];

  if (g_mode == MODE_RESET_CONFIRM) {
    snprintf(v.line[0], sizeof(v.line[0]), "FACTORY RESET?");
    snprintf(v.line[1], sizeof(v.line[1]), "OK=CONFIRM");
    snprintf(v.line[2], sizeof(v.line[2]), "MENU=CANCEL");
    snprintf(v.line[3], sizeof(v.line[3]), "IN %u S",
             (unsigned)((g_confirm_until - millis()) / 1000));
  } else if (banner) {
    strncpy(v.line[0], g_banner[0], sizeof(v.line[0]) - 1);
    strncpy(v.line[1], g_banner[1], sizeof(v.line[1]) - 1);
  } else if (g_mode == MODE_MANUAL) {
    snprintf(v.line[0], sizeof(v.line[0]), "USER TEXT");
    strncpy(v.line[1], g_manual[0], sizeof(v.line[1]) - 1);
    strncpy(v.line[2], g_manual[1], sizeof(v.line[2]) - 1);
  } else if (g_screen == SCR_VALUES) {
    for (int i = 0; i < 8; i += 2) {
      char a[8], b[8];
      number(a, sizeof(a), g_values[i], 1);
      number(b, sizeof(b), g_values[i + 1], 1);
      snprintf(v.line[i / 2], sizeof(v.line[i / 2]),
               "%d:%s %d:%s", i, a, i + 1, b);
    }
  } else {
    snprintf(v.line[0], sizeof(v.line[0]), "%s%s%s", phase_name(g_phase),
             g_wifi ? " W" : "", g_ble ? " B" : "");
    char ts[8], rs[8];
    number(ts, sizeof(ts), g_t, 1);
    number(rs, sizeof(rs), g_rh, 0);
    snprintf(v.line[1], sizeof(v.line[1]), "T%sC RH%s%%", ts, rs);
    if (g_aqi_label[0]) {
      char q[8];
      number(q, sizeof(q), g_aqi, 1);
      snprintf(v.line[2], sizeof(v.line[2]), "AQI %s %s", q, g_aqi_label);
    } else {
      char a[8];
      number(a, sizeof(a), g_ao0, 3);
      snprintf(v.line[2], sizeof(v.line[2]), "AO0 %sV", a);
    }
    v.value_count = 8;
    memcpy(v.values, g_values, sizeof(g_values));
  }

  v.fault = g_fault;
  display_show(v);
  g_last_draw = millis();
  g_last_phase = g_phase;
  g_force = false;
}

void on_short(Button &b) {
  if (g_mode == MODE_RESET_CONFIRM) {
    if (b.pin == OS_PIN_BUTTON) {
      net_factory_reset();          // wipes NVS and reboots; never returns
    } else {
      g_mode = MODE_AUTO;           // MENU cancels
      ui_beep(60);
      g_force = true;
    }
    return;
  }
  if (b.pin == OS_PIN_BUTTON) {
    if (g_fault) {                  // acknowledge a fault banner
      g_fault = false;
      ui_beep(60);
      g_force = true;
      return;
    }
    if (cycle_busy()) {             // mute toggle during a measurement
      CycleConfig c = cycle_get_config();
      c.muted = !c.muted;
      cycle_set_config(c);
      ui_beep(60);
      return;
    }
    cycle_request();                // existing MEASURE behaviour
    ui_beep(40);
    return;
  }
  // MENU short: cycle screens (manual screen is skipped when empty).
  g_mode = MODE_AUTO;
  for (uint8_t i = 0; i < SCR_COUNT; i++) {
    g_screen = (Screen)((g_screen + 1) % SCR_COUNT);
    if (g_screen != SCR_MANUAL || g_manual[0][0] || g_manual[1][0]) break;
  }
  ui_beep(40);
  g_force = true;
}

void on_long(Button &b) {
  if (b.pin != OS_PIN_BUTTON_MENU) return;
  net_enter_ap();
  snprintf(g_banner[0], sizeof(g_banner[0]), "WIFI SETUP AP");
  snprintf(g_banner[1], sizeof(g_banner[1]), "OPENSMELL-SETUP");
  g_banner_until = millis() + BANNER_MS;
  g_force = true;
}

void on_vlong(Button &b) {
  if (b.pin != OS_PIN_BUTTON_MENU) return;
  g_mode = MODE_RESET_CONFIRM;
  g_confirm_until = millis() + CONFIRM_MS;
  g_force = true;
}

void poll_button(Button &b, uint32_t now) {
  const bool pressed = digitalRead(b.pin) == LOW;
  if (pressed != b.raw) { b.raw = pressed; b.t_change = now; }
  if (now - b.t_change < DEBOUNCE_MS) return;

  if (pressed != b.down) {
    b.down = pressed;
    if (pressed) {
      b.t_down = now;
      b.long_fired = b.vlong_fired = false;
    } else if (!b.long_fired) {
      on_short(b);                  // a short press has been released
    }
    return;
  }
  if (!b.down) return;

  const uint32_t held = now - b.t_down;
  if (!b.long_fired && held >= LONG_MS) {
    b.long_fired = true;
    on_long(b);
  }
  if (!b.vlong_fired && held >= VLONG_MS) {
    b.vlong_fired = true;
    on_vlong(b);
  }
}

} // namespace

void ui_begin() {
  pinMode(OS_PIN_LED, OUTPUT);
  digitalWrite(OS_PIN_LED, LOW);
  pinMode(OS_PIN_BUZZER, OUTPUT);
  digitalWrite(OS_PIN_BUZZER, LOW);
  pinMode(OS_PIN_BUTTON, INPUT_PULLUP);
  pinMode(OS_PIN_BUTTON_MENU, INPUT_PULLUP);

  const uint32_t now = millis();
  for (Button *b : {&g_btn_measure, &g_btn_menu}) {
    b->raw = b->down = digitalRead(b->pin) == LOW;
    b->t_change = b->t_down = now;
  }
  display_begin();                  // silently no-ops if no display fitted
}

void ui_loop() {
  const uint32_t now = millis();
  poll_button(g_btn_measure, now);
  poll_button(g_btn_menu, now);

  if (g_mode == MODE_RESET_CONFIRM && now >= g_confirm_until) {
    g_mode = MODE_AUTO;
    g_force = true;
  }
  if (g_banner_until && now >= g_banner_until) {
    g_banner_until = 0;
    g_banner[0][0] = g_banner[1][0] = 0;
    g_force = true;
  }
  if (g_force || g_phase != g_last_phase || now - g_last_draw >= REDRAW_MS)
    draw();
}

void ui_show(uint8_t phase, float t_c, float rh, float ao0,
             bool wifi, bool ble) {
  g_phase = phase;
  g_t = t_c;
  g_rh = rh;
  g_ao0 = ao0;
  g_wifi = wifi;
  g_ble = ble;
  if (phase != g_last_phase) g_force = true;
}

void ui_set_values(const float *derived, uint8_t count,
                   const char *aqi_label, float aqi) {
  for (int i = 0; i < 8; i++) g_values[i] = NAN;
  if (derived) {
    for (uint8_t i = 0; i < count && i < 8; i++) g_values[i] = derived[i];
  }
  g_aqi = aqi;
  g_aqi_label[0] = 0;
  if (aqi_label) strncpy(g_aqi_label, aqi_label, sizeof(g_aqi_label) - 1);
  g_force = true;
}

void ui_set_aqi(float aqi, const char *label) {
  g_aqi = aqi;
  g_aqi_label[0] = 0;
  if (label) strncpy(g_aqi_label, label, sizeof(g_aqi_label) - 1);
  g_force = true;
}

void ui_set_fault(bool fault) {
  if (fault != g_fault) {
    g_fault = fault;
    g_force = true;
  }
}

void ui_manual_text(const char *line1, const char *line2) {
  strncpy(g_manual[0], line1 ? line1 : "", sizeof(g_manual[0]) - 1);
  strncpy(g_manual[1], line2 ? line2 : "", sizeof(g_manual[1]) - 1);
  g_manual[0][sizeof(g_manual[0]) - 1] = 0;
  g_manual[1][sizeof(g_manual[1]) - 1] = 0;
  g_mode = MODE_MANUAL;
  g_screen = SCR_MANUAL;
  g_force = true;
}

void ui_auto() {
  g_mode = MODE_AUTO;
  g_force = true;
}

void ui_screen_next() {
  if (g_mode == MODE_RESET_CONFIRM) return;
  g_mode = MODE_AUTO;
  for (uint8_t i = 0; i < SCR_COUNT; i++) {
    g_screen = (Screen)((g_screen + 1) % SCR_COUNT);
    if (g_screen != SCR_MANUAL || g_manual[0][0] || g_manual[1][0]) break;
  }
  g_force = true;
}

void ui_led(uint8_t phase, bool active) {
  // IDLE: slow blink; active phases: solid.  Unchanged from v1.1.
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

void ui_beep(uint16_t ms) {
  tone(OS_PIN_BUZZER, 2700, ms);
}
