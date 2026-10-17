// sensors.cpp
#include "sensors.h"
#include "config.h"
#include <Arduino.h>
#include <Wire.h>

// ===========================================================================
// generic I2C helpers
// ===========================================================================
bool i2c_present(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

uint8_t i2c_scan_first() {
  for (uint8_t a = 0x03; a < 0x78; a++) {
    if (i2c_present(a)) return a;
  }
  return 0;
}

uint8_t i2c_read_u8(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return 0;
  if (Wire.requestFrom((int)addr, 1) != 1) return 0;
  return Wire.read();
}

bool i2c_write_u8(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

// ===========================================================================
// TCA9548A
// ===========================================================================
namespace {
  uint8_t g_mux_addr = ADDR_TCA9548A;
}

bool Mux::begin() {
  // The board straps A0..A2 low, so 0x70 is expected; fall back to a scan.
  if (i2c_present(ADDR_TCA9548A)) {
    g_mux_addr = ADDR_TCA9548A;
  } else {
    for (uint8_t a = 0x70; a <= 0x77; a++) {
      if (i2c_present(a)) { g_mux_addr = a; break; }
    }
    if (g_mux_addr == ADDR_TCA9548A && !i2c_present(g_mux_addr)) return false;
  }
  Mux::disable();
  return true;
}

uint8_t Mux::address() { return g_mux_addr; }

void Mux::select(uint8_t channel) {
  uint8_t mask = (channel < 8) ? (uint8_t)(1u << channel) : 0;
  Wire.beginTransmission(g_mux_addr);
  Wire.write(mask);
  Wire.endTransmission();
}

void Mux::disable() { Mux::select(0xFF); }

// ===========================================================================
// ADS1115
// ===========================================================================
namespace {
  // Config register (0x01) fields.
  const uint16_t ADS_OS   = 0x8000;  // start a single conversion
  const uint16_t ADS_MODE = 0x0100;  // MODE=1 -> single-shot (power-down)
  const uint16_t ADS_PGA  = 0x0200;  // +/-4.096 V  (bits 11..9 = 001)
  const uint16_t ADS_SPS  = 0x0080;  // 128 SPS (bits 7..5 = 100), ~7.8 ms
  const uint16_t ADS_COMP = 0x0003;  // disable comparator
}

bool Adc::begin() {
  if (!i2c_present(ADDR_ADS1115)) return false;
  // Point the pointer at the config register once; conversions use it below.
  Wire.beginTransmission(ADDR_ADS1115);
  Wire.write(0x01);
  Wire.endTransmission();
  return true;
}

int16_t Adc::read_raw(uint8_t channel) {
  // MUX bits 14..12: 100..111 = AIN0..AIN3 single-ended vs GND.
  uint16_t cfg = ADS_OS | ADS_MODE | ADS_PGA | ADS_SPS | ADS_COMP
               | (uint16_t)((0x04 + (channel & 0x03)) << 12);

  Wire.beginTransmission(ADDR_ADS1115);
  Wire.write(0x01);
  Wire.write((uint8_t)(cfg >> 8));
  Wire.write((uint8_t)(cfg & 0xFF));
  if (Wire.endTransmission() != 0) return 0;

  // Wait for the single-shot conversion (128 SPS is ~7.8 ms).
  delay(9);

  Wire.beginTransmission(ADDR_ADS1115);
  Wire.write(0x00);
  if (Wire.endTransmission(false) != 0) return 0;
  if (Wire.requestFrom((int)ADDR_ADS1115, 2) != 2) return 0;
  uint8_t hi = Wire.read();
  uint8_t lo = Wire.read();
  return (int16_t)((hi << 8) | lo);
}

int16_t Adc::read_avg(uint8_t channel) {
  int32_t acc = 0;
  for (int i = 0; i < ADC_AVG; i++) acc += Adc::read_raw(channel);
  return (int16_t)(acc / ADC_AVG);
}

// ===========================================================================
// SHT31
// ===========================================================================
namespace {
  uint8_t sht_crc(const uint8_t *d) {
    uint8_t crc = 0xFF;
    for (int i = 0; i < 2; i++) {
      crc ^= d[i];
      for (int b = 0; b < 8; b++)
        crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x31) : (uint8_t)(crc << 1);
    }
    return crc;
  }
}

bool Sht::begin() {
  if (!i2c_present(ADDR_SHT31)) return false;
  // Soft reset (0x30A2), then break command (0x3093) for periodic mode.
  Wire.beginTransmission(ADDR_SHT31);
  Wire.write(0x30); Wire.write(0xA2);
  Wire.endTransmission();
  delay(10);
  return true;
}

bool Sht::read(float *t_c, float *rh_pct) {
  // High-repeatability, no clock stretching: 0x2400.
  Wire.beginTransmission(ADDR_SHT31);
  Wire.write(0x24); Wire.write(0x00);
  if (Wire.endTransmission() != 0) return false;
  delay(16);  // measurement takes ~15 ms
  if (Wire.requestFrom((int)ADDR_SHT31, 6) != 6) return false;
  uint8_t d[6];
  for (int i = 0; i < 6; i++) d[i] = Wire.read();

  if (sht_crc(d) != d[2] || sht_crc(d + 3) != d[5]) return false;

  uint16_t rawT = (uint16_t)((d[0] << 8) | d[1]);
  uint16_t rawH = (uint16_t)((d[3] << 8) | d[4]);
  *t_c    = -45.0f + 175.0f * ((float)rawT / 65535.0f);
  *rh_pct = 100.0f * ((float)rawH / 65535.0f);
  return true;
}
