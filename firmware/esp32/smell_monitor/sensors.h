// sensors.h - ADS1115, TCA9548A and SHT31 drivers (raw I2C, no external libs).
#pragma once

#include <stdint.h>

// ---- TCA9548A I2C multiplexer (digital slots) -----------------------------
namespace Mux {
  bool begin();
  void select(uint8_t channel);   // 0..7; >=8 deselects (channel n <-> slot n)
  void disable();
  uint8_t address();              // scanned 0x70..0x77
}

// ---- ADS1115 pair: 8 single-ended analog channels, one per slot -----------
namespace Adc {
  bool begin();
  // Read one single-ended channel (0..7; channels 0-3 on ADS1115_A, 4-7 on
  // ADS1115_B) in raw counts, PGA = +/-4.096 V.
  int16_t read_raw(uint8_t channel);
  // Averaged raw reading over ADC_AVG samples.
  int16_t read_avg(uint8_t channel);
  // Convert raw counts to volts at the ADC input.
  static inline float counts_to_volts(int16_t raw) {
    return raw * (4.096f / 32768.0f);
  }
}

// ---- SHT31 temperature / humidity -----------------------------------------
namespace Sht {
  bool begin();
  bool read(float *t_c, float *rh_pct);
}

// ---- generic I2C helpers ---------------------------------------------------
uint8_t i2c_read_u8(uint8_t addr, uint8_t reg);
bool    i2c_write_u8(uint8_t addr, uint8_t reg, uint8_t val);
// Probe the bus; returns the first address that ACKs, or 0.
uint8_t i2c_scan_first();
bool    i2c_present(uint8_t addr);
