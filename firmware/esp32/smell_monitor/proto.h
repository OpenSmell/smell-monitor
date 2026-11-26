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
  uint32_t ts;          // ms since boot (kept for schema compatibility)
  // Persistent, monotonic record id allocated when the record is generated;
  // survives reboots and is used by the NVS ring /data?since= replay.
  uint32_t seq;
  // ISO-8601 UTC ("YYYY-MM-DDTHH:MM:SSZ"), empty when SNTP never synced.
  char     wall_clock[25];
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

  // Optional interpretation profile (additive, schema version stays "1.0").
  // Raw `ao` values above remain canonical; these are host/display convenience
  // fields only. Empty version / NaN values are emitted as JSON null.
  char     profile_version[16];  // "v1" when a profile was applied
  float    derived[8];           // per-slot derived values, NaN = unconfigured
  float    aqi;                  // aggregate over configured slots
  char     aqi_label[16];        // e.g. "good"
};

// Serialise `r` into `buf` as one JSON object (no trailing newline added here).
// Returns the number of bytes written (excluding the terminating NUL), or -1
// if the buffer is too small.
int proto_to_json(const Record *r, char *buf, size_t n);

const char *phase_name(uint8_t phase);
