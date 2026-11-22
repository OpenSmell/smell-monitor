// cycle.h - three-phase measurement state machine (blueprint 7.1).
#pragma once

#include <stdint.h>

// Runtime-tunable cycle settings.  Defaults come from config.h; Osmograph can
// change them over serial / Wi-Fi / BLE, and net.cpp persists them in NVS.
struct CycleConfig {
  uint8_t  fan_intake;   // PWM duty during INTAKE
  uint8_t  fan_hold;     // PWM duty during HOLD (0 = sensors soak in still air)
  uint8_t  fan_purge;    // PWM duty during PURGE
  uint32_t t_intake_ms;
  uint32_t t_hold_ms;
  uint32_t t_purge_ms;
  uint16_t sweep_ms;     // ADC read interval during HOLD
  bool     muted;        // suppress the end-of-cycle confirmation beep
};

void cycle_begin();
void cycle_loop();
void cycle_request();      // ask for one cycle (button / command)
bool cycle_busy();
uint8_t cycle_phase();

void cycle_set_config(const CycleConfig &cfg);
CycleConfig cycle_get_config();
