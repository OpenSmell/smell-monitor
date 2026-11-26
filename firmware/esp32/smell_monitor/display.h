// display.h - minimal SSD1306 128x64 I2C driver (no external library).
//
// The display sits on the MASTER I2C bus at ADDR_DISPLAY (0x3C), not behind
// the TCA9548A.  Four 16-character rows use a built-in 5x7 font, scaled 2x
// vertically.  All transfers are short, checked and non-blocking: Wire's
// timeout guards every transaction and no delay()/wait loop is used.
#pragma once

#include <stdint.h>
#include <stddef.h>

struct DisplayView {
  char    line[4][17];   // 16 visible chars per row, NUL-terminated
  float   values[8];     // derived slot values (NaN = not configured)
  uint8_t value_count;   // 0..8; when > 0 a compact strip is drawn on row 4
  bool    fault;         // draws the fault marker on row 1
};

bool display_begin();                 // probe + init; false if no display fitted
void display_show(const DisplayView &view);
// Convenience form matching display_show(status lines, values, fault).
void display_show(const char *l1, const char *l2, const char *l3,
                  const char *l4, const float *values, uint8_t value_count,
                  bool fault);
void display_off();
void display_test();                  // one static test pattern, no delays
