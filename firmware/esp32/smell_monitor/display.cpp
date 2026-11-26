// display.cpp - tiny SSD1306 128x64 I2C frame driver.
//
// Design notes:
//  * The SSD1306 is on the master bus (ADDR_DISPLAY), never behind the mux.
//  * No external library, no framebuffer in RAM: each 128-byte page column
//    buffer is built on the stack and pushed in one short Wire transaction.
//  * Wire.setTimeOut() bounds every transfer; there are no delay() calls or
//    busy-wait loops, so a missing / stuck display cannot stall the cycle.
//  * Font covers ASCII 0x20..0x5F (lowercase is folded to uppercase), 5x7,
//    column-major with bit 0 at the top, scaled 2x vertically (5x14 pixels).
#include "display.h"
#include "config.h"
#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <string.h>

namespace {

const uint8_t FONT[64][5] = {
  {0x00,0x00,0x00,0x00,0x00}, // space
  {0x00,0x00,0x5F,0x00,0x00}, // !
  {0x00,0x07,0x00,0x07,0x00}, // "
  {0x14,0x7F,0x14,0x7F,0x14}, // #
  {0x24,0x2A,0x7F,0x2A,0x12}, // $
  {0x23,0x13,0x08,0x64,0x62}, // %
  {0x36,0x49,0x55,0x22,0x50}, // &
  {0x00,0x05,0x03,0x00,0x00}, // '
  {0x00,0x1C,0x22,0x41,0x00}, // (
  {0x00,0x41,0x22,0x1C,0x00}, // )
  {0x08,0x2A,0x1C,0x2A,0x08}, // *
  {0x08,0x08,0x3E,0x08,0x08}, // +
  {0x00,0x50,0x30,0x00,0x00}, // ,
  {0x08,0x08,0x08,0x08,0x08}, // -
  {0x00,0x60,0x60,0x00,0x00}, // .
  {0x20,0x10,0x08,0x04,0x02}, // /
  {0x3E,0x51,0x49,0x45,0x3E}, // 0
  {0x00,0x42,0x7F,0x40,0x00}, // 1
  {0x42,0x61,0x51,0x49,0x46}, // 2
  {0x21,0x41,0x45,0x4B,0x31}, // 3
  {0x18,0x14,0x12,0x7F,0x10}, // 4
  {0x27,0x45,0x45,0x45,0x39}, // 5
  {0x3C,0x4A,0x49,0x49,0x30}, // 6
  {0x01,0x71,0x09,0x05,0x03}, // 7
  {0x36,0x49,0x49,0x49,0x36}, // 8
  {0x06,0x49,0x49,0x29,0x1E}, // 9
  {0x00,0x36,0x36,0x00,0x00}, // :
  {0x00,0x56,0x36,0x00,0x00}, // ;
  {0x00,0x08,0x14,0x22,0x41}, // <
  {0x14,0x14,0x14,0x14,0x14}, // =
  {0x41,0x22,0x14,0x08,0x00}, // >
  {0x02,0x01,0x51,0x09,0x06}, // ?
  {0x32,0x49,0x79,0x41,0x3E}, // @
  {0x7F,0x08,0x08,0x08,0x7F}, // A
  {0x7F,0x49,0x49,0x49,0x36}, // B
  {0x3E,0x41,0x41,0x41,0x22}, // C
  {0x7F,0x41,0x41,0x22,0x1C}, // D
  {0x7F,0x49,0x49,0x49,0x41}, // E
  {0x7F,0x09,0x09,0x01,0x01}, // F
  {0x3E,0x41,0x41,0x51,0x32}, // G
  {0x7F,0x08,0x08,0x08,0x7F}, // H
  {0x00,0x41,0x7F,0x41,0x00}, // I
  {0x20,0x40,0x41,0x3F,0x01}, // J
  {0x7F,0x08,0x14,0x22,0x41}, // K
  {0x7F,0x40,0x40,0x40,0x40}, // L
  {0x7F,0x02,0x04,0x02,0x7F}, // M
  {0x7F,0x04,0x08,0x10,0x7F}, // N
  {0x3E,0x41,0x41,0x41,0x3E}, // O
  {0x7F,0x09,0x09,0x09,0x06}, // P
  {0x3E,0x41,0x51,0x21,0x5E}, // Q
  {0x7F,0x09,0x19,0x29,0x46}, // R
  {0x46,0x49,0x49,0x49,0x31}, // S
  {0x01,0x01,0x7F,0x01,0x01}, // T
  {0x3F,0x40,0x40,0x40,0x3F}, // U
  {0x1F,0x20,0x40,0x20,0x1F}, // V
  {0x3F,0x40,0x38,0x40,0x3F}, // W
  {0x63,0x14,0x08,0x14,0x63}, // X
  {0x03,0x04,0x78,0x04,0x03}, // Y
  {0x61,0x51,0x49,0x45,0x43}, // Z
  {0x00,0x7F,0x41,0x41,0x00}, // [
  {0x02,0x04,0x08,0x10,0x20}, // backslash
  {0x00,0x41,0x41,0x7F,0x00}, // ]
  {0x04,0x02,0x01,0x02,0x04}, // ^
  {0x40,0x40,0x40,0x40,0x40}, // _
};

bool s_ready = false;

// One transaction: control byte (0x00 commands / 0x40 data) then payload.
bool tx(uint8_t control, const uint8_t *data, size_t n) {
  if (!s_ready) return false;
  Wire.beginTransmission(ADDR_DISPLAY);
  Wire.write(control);
  if (n && data) Wire.write(data, n);
  return Wire.endTransmission() == 0;
}

bool cmd(uint8_t c) { return tx(0x00, &c, 1); }

bool set_page(uint8_t page) {
  const uint8_t seq[3] = {
    (uint8_t)(0xB0 | (page & 0x07)),
    0x00,                   // lower column address = 0
    0x10,                   // higher column address = 0
  };
  return tx(0x00, seq, sizeof(seq));
}

// Render one 8-row half of a 16-pixel text row. `marker` fills the spare
// right-hand columns with a solid fault block.
void render_page(const char *text, uint8_t half, uint8_t out[128], bool marker) {
  memset(out, 0, 128);
  for (int ci = 0; ci < 21; ci++) {
    char c = text[ci];
    if (!c) c = ' ';
    if (c >= 'a' && c <= 'z') c = (char)(c - 0x20);
    if (c < 0x20 || c > 0x5F) c = '?';
    const uint8_t *glyph = FONT[(uint8_t)(c - 0x20)];
    for (int gx = 0; gx < 5; gx++) {
      if (!glyph[gx]) continue;
      for (int gy = 0; gy < 7; gy++) {
        if (!(glyph[gx] & (1u << gy))) continue;
        for (int k = 0; k < 2; k++) {
          const int y = 2 * gy + k;       // 2x vertical scale
          if ((y >> 3) != half) continue;
          const int x = ci * 6 + gx;
          if (x < 128) out[x] |= (uint8_t)(1u << (y & 7));
        }
      }
    }
  }
  if (marker && half == 0) {
    for (int x = 120; x < 128; x++) out[x] = 0xFF;
  }
}

void draw_row(uint8_t row, const char *text, bool marker) {
  for (uint8_t half = 0; half < 2; half++) {
    uint8_t col[128];
    render_page(text, half, col, marker);
    if (!set_page((uint8_t)(row * 2 + half))) return;
    tx(0x40, col, sizeof(col));
  }
}

void format_values(char *dst, size_t n, const float *v, uint8_t count) {
  size_t used = 0;
  dst[0] = 0;
  for (uint8_t i = 0; i < count && used + 6 < n; i++) {
    if (!isfinite(v[i])) continue;
    int k = snprintf(dst + used, n - used, "%s%u:%4.1f",
                     used ? " " : "", (unsigned)i, (double)v[i]);
    if (k <= 0 || (size_t)k >= n - used) break;
    used += (size_t)k;
  }
}

} // namespace

bool display_begin() {
  // Bound every I2C transfer. This is global to Wire but all other bus users
  // are short register accesses, so 30 ms is generous for them too.
  Wire.setTimeOut(30);

  Wire.beginTransmission(ADDR_DISPLAY);
  if (Wire.endTransmission() != 0) return false;   // no display fitted

  static const uint8_t init[] = {
    0xAE,             // display off
    0xD5, 0x80,       // default divide ratio / oscillator
    0xA8, 0x3F,       // 64 mux rows
    0xD3, 0x00,       // no display offset
    0x40,             // start line 0
    0x8D, 0x14,       // charge pump on
    0x20, 0x00,       // horizontal addressing
    0xA1,             // segment remap
    0xC8,             // COM scan direction
    0xDA, 0x12,       // COM pins alternate
    0x81, 0x7F,       // contrast
    0xA4,             // ignore RAM content? no: use RAM
    0xA6,             // normal (not inverse) video
    0xAF,             // display on
  };
  if (!tx(0x00, init, sizeof(init))) return false;
  s_ready = true;

  uint8_t blank[128] = {0};
  for (uint8_t p = 0; p < 8; p++) {
    if (!set_page(p)) break;
    tx(0x40, blank, sizeof(blank));
  }
  return s_ready;
}

void display_show(const DisplayView &view) {
  if (!s_ready) return;
  cmd(0xAF);   // wake after display_off()

  char rows[4][17];
  for (int r = 0; r < 4; r++) {
    strncpy(rows[r], view.line[r], sizeof(rows[r]) - 1);
    rows[r][sizeof(rows[r]) - 1] = 0;
  }
  if (view.value_count) format_values(rows[3], sizeof(rows[3]),
                                      view.values, view.value_count);
  if (view.fault && !view.value_count) strncpy(rows[3], "FAULT", sizeof(rows[3]) - 1);

  for (uint8_t r = 0; r < 4; r++) draw_row(r, rows[r], view.fault);
}

void display_show(const char *l1, const char *l2, const char *l3,
                  const char *l4, const float *values, uint8_t value_count,
                  bool fault) {
  DisplayView v;
  memset(&v, 0, sizeof(v));
  strncpy(v.line[0], l1 ? l1 : "", sizeof(v.line[0]) - 1);
  strncpy(v.line[1], l2 ? l2 : "", sizeof(v.line[1]) - 1);
  strncpy(v.line[2], l3 ? l3 : "", sizeof(v.line[2]) - 1);
  strncpy(v.line[3], l4 ? l4 : "", sizeof(v.line[3]) - 1);
  if (values) {
    for (uint8_t i = 0; i < value_count && i < 8; i++) v.values[i] = values[i];
    v.value_count = value_count > 8 ? 8 : value_count;
  }
  v.fault = fault;
  display_show(v);
}

void display_off() {
  if (s_ready) cmd(0xAE);
}

void display_test() {
  if (!s_ready) return;
  cmd(0xAF);
  for (uint8_t p = 0; p < 8; p++) {
    if (!set_page(p)) return;
    uint8_t pattern[128];
    for (int x = 0; x < 128; x++) pattern[x] = (x / 8) & 1 ? 0xAA : 0x55;
    tx(0x40, pattern, sizeof(pattern));
  }
}
