// config.h - board pins, I2C addresses and timing.
//
// These values MUST match electrical/interface.py (PINMAP / I2C) and
// electrical/board.py. tools/verify_firmware_pins.py checks that they do.
#pragma once

// ---- I2C bus (shared: ADS1115, TCA9548A, SHT31, OLED) ---------------------
#define OS_PIN_SDA   21
#define OS_PIN_SCL   22

#define ADDR_ADS1115   0x48
#define ADDR_TCA9548A  0x70
#define ADDR_SHT31     0x44
#define ADDR_OLED      0x3C

// ---- Discrete I/O ---------------------------------------------------------
// Names are OS_-prefixed: the ESP32 SDK already defines bare PIN_CTRL etc.
#define OS_PIN_FAN_PWM  4
#define OS_PIN_LED      14
#define OS_PIN_BUZZER   13
#define OS_PIN_BUTTON   23   // MEASURE.  BOOT/strapping is GPIO0, reset is EN.

// Analog-slot digital read-back (input-only pins on the ESP32).
static const int OS_PIN_DO[4]   = {33, 34, 35, 36};

// Digital-slot interrupt lines.
static const int OS_PIN_INT[4]  = {25, 26, 27, 32};

// Digital-slot CTRL enables.
static const int OS_PIN_CTRL[4] = {16, 17, 18, 19};

// ---- Cycle timing (ms) - blueprint 7.1 ------------------------------------
#define T_INTAKE_MS  10000UL
#define T_HOLD_MS    10000UL
#define T_PURGE_MS   20000UL

// ---- Analog sampling ------------------------------------------------------
// One ADS1115 conversion per channel per sweep; the HOLD window accumulates
// many sweeps (~8 sweeps/s = 8 SPS/channel) and averages them, per blueprint
// 7.2.  A smaller ADC_AVG keeps each sweep short so the main loop still runs.
#define ADC_AVG       1
#define HOLD_SWEEP_MS 125UL   // ~8 sweeps/s -> ~80 sweeps over the 10 s HOLD

// ---- Fan PWM (LEDC) -------------------------------------------------------
// Duty is 8-bit: blueprint 2 -> intake ~50 %, purge 100 %, hold off.
#define FAN_PWM_CH      0
#define FAN_PWM_HZ      25000
#define FAN_PWM_BITS    8
#define FAN_DUTY_INTAKE 128
#define FAN_DUTY_PURGE  255
#define FAN_DUTY_OFF    0

// ---- AO input divider (blueprint 4.1/5.3): 10k/10k -> slot volts = 2 x ADC --
#define AO_DIVIDER 2.0f

// ---- Firmware identity ----------------------------------------------------
#define FW_NAME     "OpenSmell"
#define FW_VERSION  "1.1.0"
#define SERIAL_BAUD 115200
