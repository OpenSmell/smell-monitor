// config.h - board pins, I2C addresses and timing.
//
// These values MUST match electrical/interface.py (PINMAP / I2C) and
// electrical/board.py. tools/verify_firmware_pins.py checks that they do.
// Board = OSM-1 re-lay: eight uniform slots, two ADS1115s, one shared
// 1-Wire ID bus, a front-wall SSD1306 with four panel buttons, and field OTA
// (main flashing path; USB serial remains the recovery path).
#pragma once

// ---- I2C bus (shared: ADS1115 pair, TCA9548A, SHT31, SSD1306 display) ------
#define OS_PIN_SDA   21
#define OS_PIN_SCL   22

#define ADDR_ADS1115_A   0x48   // slots 0-3 AO (downstream row)
#define ADDR_ADS1115_B   0x49   // slots 4-7 AO (upstream row)
#define ADDR_TCA9548A    0x70
#define ADDR_SHT31       0x44
#define ADDR_DISPLAY     0x3C   // SSD1306 128x64 on the MASTER bus (not muxed)

// ---- Discrete I/O ---------------------------------------------------------
// Names are OS_-prefixed: the ESP32 SDK already defines bare PIN_CTRL etc.
#define OS_PIN_FAN_PWM     4
#define OS_PIN_BUZZER     13
#define OS_PIN_LED        14

// Shared 1-Wire identity bus: every slot ID pin is tied to this one GPIO.
// It is open-drain and MUST stay on a bidirectional pin; the electrical
// contract reserves it BEFORE the button / DO inputs for that reason.
#define OS_PIN_ONEWIRE    16

// Two active-low user buttons (INPUT_PULLUP).
#define OS_PIN_BUTTON      17   // MEASURE / OK
#define OS_PIN_BUTTON_MENU 18   // MENU / screen, AP setup, factory reset

// One digital read-back line per slot, slots 0-7, through a 10k series R.
static const int OS_PIN_DO[8]   = {19, 23, 25, 26, 27, 32, 33, 34};

// ---- Cycle timing (ms) - blueprint 7.1 ------------------------------------
#define T_INTAKE_MS  10000UL
#define T_HOLD_MS    10000UL
#define T_PURGE_MS   20000UL

// ---- ADC ------------------------------------------------------------------
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
#define FW_VERSION  "1.2.0"
#define SERIAL_BAUD 115200
