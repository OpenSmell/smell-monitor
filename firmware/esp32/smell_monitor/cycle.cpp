// cycle.cpp - IDLE -> INTAKE -> HOLD -> PURGE -> IDLE, report at end of PURGE.
//
// Contract (blueprint 2 / 7.1):
//   INTAKE  fan ~50 %   10 s   draw the sample in
//   HOLD    fan OFF     10 s   sensors equilibrate; ACQUISITION happens here
//   PURGE   fan 100 %   20 s   flush the cavity, then report to the host
#include "cycle.h"
#include "config.h"
#include "proto.h"
#include "sensors.h"
#include "ui.h"
#include "net.h"
#include <Arduino.h>
#include <math.h>
#include <esp_arduino_version.h>

static uint8_t  g_phase = PH_IDLE;
static uint32_t g_phase_start = 0;
static bool     g_request = false;
static uint16_t g_cycle = 0;

// Acquired during HOLD, published at the end of PURGE.
static Record   g_last;
static uint16_t g_sweeps = 0;
static double   g_acc_ao[4];
static double   g_acc_adc[4];
static uint32_t g_last_sweep = 0;

// Latest SHT31 reading, refreshed at 1 Hz in every phase (blueprint 7.4).
static float    g_env_t = NAN;
static float    g_env_rh = NAN;
static uint32_t g_last_env = 0;

// ---------------------------------------------------------------------------
static void fan_set(uint8_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(OS_PIN_FAN_PWM, duty);
#else
  ledcWrite(FAN_PWM_CH, duty);
#endif
}

static void fan_begin() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(OS_PIN_FAN_PWM, FAN_PWM_HZ, FAN_PWM_BITS);
#else
  ledcSetup(FAN_PWM_CH, FAN_PWM_HZ, FAN_PWM_BITS);
  ledcAttachPin(OS_PIN_FAN_PWM, FAN_PWM_CH);
#endif
  fan_set(FAN_DUTY_OFF);
}

// ---------------------------------------------------------------------------
// Digital-slot identity.
//
// The *master* bus (ESP32, ADS1115 0x48, SHT31 0x44, OLED 0x3C, mux 0x70) is
// always present behind an enabled mux channel - the TCA9548A only switches
// the downstream segment.  So master addresses must never be used to identify
// a plugged module; probe the known digital-sensor addresses instead.
struct DigId { uint8_t addr; const char *name; };
static const DigId DIG_IDS[] = {
    {0x62, "scd40/41"}, {0x58, "sgp30"},   {0x59, "sgp40/41"},
    {0x76, "bme68x"},   {0x77, "bme68x"},  {0x52, "ens160"},
    {0x53, "ens160"},   {0x5A, "ccs811"},  {0x5B, "ccs811"},
    {0x32, "zmod"},
};

static void detect_digital(uint8_t channel, char out[16]) {
  strncpy(out, "none", 15); out[15] = 0;
  if (!Mux::address()) return;
  Mux::select(channel);
  delay(2);
  for (unsigned i = 0; i < sizeof(DIG_IDS) / sizeof(DIG_IDS[0]); i++) {
    if (i2c_present(DIG_IDS[i].addr)) {
      strncpy(out, DIG_IDS[i].name, 15); out[15] = 0;
      break;
    }
  }
  Mux::disable();
}

// ---------------------------------------------------------------------------
// Acquisition - accumulate sweeps across the whole HOLD window.
static void acquire_begin() {
  memset(&g_last, 0, sizeof(g_last));
  for (int i = 0; i < 4; i++) { g_acc_ao[i] = 0.0; g_acc_adc[i] = 0.0; }
  g_sweeps = 0;
  g_last_sweep = 0;
}

static void acquire_sweep() {
  for (int i = 0; i < 4; i++) {
    int16_t c = Adc::read_avg(i);
    g_acc_adc[i] += c;
    // Slot voltage = 2 x the ADC node (fixed 2:1 divider), blueprint 4.1.
    g_acc_ao[i]  += (double)Adc::counts_to_volts(c) * AO_DIVIDER;
    g_last.do_[i] = (int16_t)digitalRead(OS_PIN_DO[i]);
  }
  g_sweeps++;
}

static void acquire_finish() {
  if (!g_sweeps) return;
  g_last.ts = millis();
  g_last.cycle_id = g_cycle;
  for (int i = 0; i < 4; i++) {
    g_last.adc[i] = (int16_t)(g_acc_adc[i] / g_sweeps);
    g_last.ao[i]  = (float)(g_acc_ao[i] / g_sweeps);
  }
  for (int i = 0; i < 4; i++) detect_digital(i, g_last.digital[i]);
  g_last.t  = g_env_t;
  g_last.rh = g_env_rh;
}

static void report() {
  Record r = g_last;
  r.phase = PH_REPORT;                 // "a completed measurement"
  char buf[512];
  if (proto_to_json(&r, buf, sizeof(buf)) > 0) net_publish(buf);
  ui_show(r.phase, r.t, r.rh, r.ao[0], net_wifi_on(), net_ble_on());
  ui_beep(120);
}

// ---------------------------------------------------------------------------
void cycle_begin() {
  fan_begin();
  for (int i = 0; i < 4; i++) pinMode(OS_PIN_DO[i], INPUT);
  for (int i = 0; i < 4; i++) pinMode(OS_PIN_INT[i], INPUT);
  for (int i = 0; i < 4; i++) pinMode(OS_PIN_CTRL[i], OUTPUT);
  pinMode(OS_PIN_BUTTON, INPUT_PULLUP);
  g_phase = PH_IDLE;
  g_phase_start = millis();
}

void cycle_request() { g_request = true; }
bool cycle_busy() { return g_phase != PH_IDLE; }
uint8_t cycle_phase() { return g_phase; }

static void enter(uint8_t p) {
  g_phase = p;
  g_phase_start = millis();
  switch (p) {
    case PH_INTAKE: fan_set(FAN_DUTY_INTAKE); break;
    case PH_HOLD:   fan_set(FAN_DUTY_OFF);  acquire_begin(); break;
    case PH_PURGE:  fan_set(FAN_DUTY_PURGE); break;
    default:        fan_set(FAN_DUTY_OFF);   break;
  }
}

void cycle_loop() {
  uint32_t now = millis();
  uint32_t dt = now - g_phase_start;

  // Environmental logging at 1 Hz, all phases (blueprint 7.4).
  if (now - g_last_env >= 1000) {
    g_last_env = now;
    float t = NAN, rh = NAN;
    if (Sht::read(&t, &rh)) { g_env_t = t; g_env_rh = rh; }
  }

  // MEASURE button (active low) starts a cycle from idle.
  static bool prev_btn = HIGH;
  bool btn = digitalRead(OS_PIN_BUTTON);
  if (prev_btn == HIGH && btn == LOW && g_phase == PH_IDLE) g_request = true;
  prev_btn = btn;

  switch (g_phase) {
    case PH_IDLE:
      if (g_request) { g_request = false; g_cycle++; enter(PH_INTAKE); }
      break;
    case PH_INTAKE:
      if (dt >= T_INTAKE_MS) enter(PH_HOLD);
      break;
    case PH_HOLD:
      if (now - g_last_sweep >= HOLD_SWEEP_MS) {
        g_last_sweep = now;
        acquire_sweep();
      }
      if (dt >= T_HOLD_MS) { acquire_finish(); enter(PH_PURGE); }
      break;
    case PH_PURGE:
      if (dt >= T_PURGE_MS) { report(); enter(PH_IDLE); }
      break;
    default:
      enter(PH_IDLE);
      break;
  }

  static uint32_t last_ui = 0;
  if (now - last_ui > 500) {
    last_ui = now;
    ui_led(g_phase, g_phase != PH_IDLE);
  }
}
