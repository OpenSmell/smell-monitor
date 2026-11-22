// proto.h - one measurement record, serialised to JSON for every transport.
#pragma once

#include <stdint.h>
#include <stddef.h>

enum Phase : uint8_t {
  PH_IDLE = 0,
  PH_INTAKE,
  PH_HOLD,
  PH_PURGE,
  PH_REPORT,
};

struct Record {
  uint32_t ts;          // ms since boot
  uint8_t  phase;       // cycle phase of the record ("report" when published)
  uint16_t cycle_id;
  float    ao[8];       // all eight slots, volts at the SLOT (ADC node x 2)
  int16_t  adc[8];      // raw ADS1115 counts
  int16_t  do_[8];      // slot DO pin read (0/1, -1 = not present)
  float    t;           // degC  (SHT31)
  float    rh;          // %RH   (SHT31)
  // detected module identity per slot ("none" when empty); gas cells are
  // identified by AO/DO behaviour, I2C modules by mux-channel probe.
  char     digital[8][16];
  // Cartridge EEPROM / identity. The ID net is wired (shared 1-Wire bus on
  // OS_PIN_ONEWIRE), but the eight ID pins are in parallel, so a single bus
  // cannot address individual ROMs.  Emitted null until a per-slot ID read
  // is implemented; kept for the .osmell schema.
  char     eeprom_id[16];
  char     calibration_date[16];
  // Optional liquid pH from a pluggable ISFET OSM-1 cartridge.  The base board
  // has no pH sensor: ph_slot = -1 and ph_value = NAN until an ISFET cartridge
  // driver supplies a reading.  Gas, pH and T/H therefore travel in one record.
  int8_t   ph_slot;
  float    ph_value;
};

// Serialise `r` into `buf` as one JSON object (no trailing newline added here).
// Returns the number of bytes written (excluding the terminating NUL), or -1
// if the buffer is too small.
int proto_to_json(const Record *r, char *buf, size_t n);

const char *phase_name(uint8_t phase);
