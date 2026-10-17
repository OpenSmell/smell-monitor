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
  float    ao[4];       // analog slots, volts at the SLOT (ADC node x 2)
  int16_t  adc[4];      // raw ADS1115 counts
  int16_t  do_[4];      // analog-slot DO pin read (0/1, -1 = not present)
  float    t;           // degC  (SHT31)
  float    rh;          // %RH   (SHT31)
  // detected module identity per digital slot ("none" when empty)
  char     digital[4][16];
};

// Serialise `r` into `buf` as one JSON object (no trailing newline added here).
// Returns the number of bytes written (excluding the terminating NUL), or -1
// if the buffer is too small.
int proto_to_json(const Record *r, char *buf, size_t n);

const char *phase_name(uint8_t phase);
