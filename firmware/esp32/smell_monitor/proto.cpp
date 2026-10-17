// proto.cpp - build the JSON record by hand (no external JSON dependency).
//
// One fixed-shape object per completed measurement.  Field order:
//   ts, cycle_id, phase, t, rh, ao[4], adc[4], do[4], digital[4]
// Non-finite floats (e.g. an SHT31 read failure) are emitted as JSON `null`,
// never as `nan`, so every transport always carries parseable JSON.
#include "proto.h"
#include <Arduino.h>
#include <math.h>

const char *phase_name(uint8_t phase) {
  switch (phase) {
    case PH_IDLE:   return "idle";
    case PH_INTAKE: return "intake";
    case PH_HOLD:   return "hold";
    case PH_PURGE:  return "purge";
    case PH_REPORT: return "report";
    default:        return "?";
  }
}

// snprintf that never writes a non-JSON token.
static int fmt_num(char *dst, size_t n, float v, int prec) {
  if (!isfinite(v)) return snprintf(dst, n, "null");
  return snprintf(dst, n, "%.*f", prec, (double)v);
}

int proto_to_json(const Record *r, char *buf, size_t n) {
  int off = 0;
  int w;
  char tmp[32];

  fmt_num(tmp, sizeof(tmp), r->t, 2);
  int off_t = off + snprintf(buf + off, n - off,
                             "{\"ts\":%lu,\"cycle_id\":%u,\"phase\":\"%s\",\"t\":%s,",
                             (unsigned long)r->ts, (unsigned)r->cycle_id,
                             phase_name(r->phase), tmp);
  if ((size_t)off_t >= n) return -1;
  off = off_t;

  // ao[] - slot voltage (post 2:1 divider x2), volts
  w = snprintf(buf + off, n - off, "\"rh\":");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  w = fmt_num(buf + off, n - off, r->rh, 2);
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  w = snprintf(buf + off, n - off, ",\"ao\":[");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  for (int i = 0; i < 4; i++) {
    if (i) { if ((size_t)(off + 1) >= n) return -1; buf[off++] = ','; }
    w = fmt_num(buf + off, n - off, r->ao[i], 3);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
  }
  w = snprintf(buf + off, n - off, "]");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // adc[] - raw ADS1115 counts
  w = snprintf(buf + off, n - off, ",\"adc\":[");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  for (int i = 0; i < 4; i++) {
    w = snprintf(buf + off, n - off, "%s%d", i ? "," : "", r->adc[i]);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
  }
  w = snprintf(buf + off, n - off, "]");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // do[] - analog-slot DO pin state (0/1)
  w = snprintf(buf + off, n - off, ",\"do\":[");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  for (int i = 0; i < 4; i++) {
    w = snprintf(buf + off, n - off, "%s%d", i ? "," : "", r->do_[i]);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
  }
  w = snprintf(buf + off, n - off, "]");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // digital[] - detected module identity per digital slot
  w = snprintf(buf + off, n - off, ",\"digital\":[");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  for (int i = 0; i < 4; i++) {
    w = snprintf(buf + off, n - off, "%s\"%s\"", i ? "," : "", r->digital[i]);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
  }
  w = snprintf(buf + off, n - off, "]}");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  return off;
}
