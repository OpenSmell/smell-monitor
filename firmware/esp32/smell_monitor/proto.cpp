// proto.cpp - build the JSON record by hand (no external JSON dependency).
//
// One fixed-shape object per completed measurement, matching the locked
// `.osmell` live-record schema (opensmell/schemas/osmell.v1.schema.json).
//
// Field order:
//   format, version, hardware_id, timestamp_ms, cycle, environment, slots,
//   user_metadata
//
// Non-finite floats are emitted as JSON `null`, never as `nan`, so every
// transport always carries parseable JSON. qc_flags and user_metadata are left
// empty here: they are injected by Osmograph's live stream processor and by the
// user's annotation surface respectively.
#include "proto.h"
#include <Arduino.h>
#include <math.h>

#ifndef OS_HARDWARE_ID
#define OS_HARDWARE_ID "OpenSmell_Monitor_v1.1"
#endif

const char *phase_name(uint8_t phase) {
  switch (phase) {
    case PH_IDLE:   return "idle";
    case PH_INTAKE: return "intake";
    case PH_HOLD:   return "hold";
    case PH_PURGE:  return "purge";
    case PH_REPORT: return "report";
    default:        return "idle";
  }
}

// Nominal phase duration in seconds (blueprint 7.1).
static float phase_duration_s(uint8_t phase) {
  switch (phase) {
    case PH_INTAKE: return 10.0f;
    case PH_HOLD:   return 10.0f;
    case PH_PURGE:  return 20.0f;
    default:        return 0.0f;
  }
}

// snprintf that never writes a non-JSON token.
static int fmt_num(char *dst, size_t n, float v, int prec) {
  if (!isfinite(v)) return snprintf(dst, n, "null");
  return snprintf(dst, n, "%.*f", prec, (double)v);
}

// Write a JSON string (double-quoted, escaped). Returns bytes written.
static int fmt_str(char *dst, size_t n, const char *s) {
  if (!s) s = "";
  size_t used = 0;
  if ((used + 1) >= n) return -1;
  dst[used++] = '"';
  for (const char *p = s; *p && (used + 6) < n; p++) {
    char c = *p;
    if (c == '"' || c == '\\') {
      dst[used++] = '\\'; dst[used++] = c;
    } else if (c == '\n') { dst[used++] = '\\'; dst[used++] = 'n'; }
    else if (c == '\r') { dst[used++] = '\\'; dst[used++] = 'r'; }
    else if (c == '\t') { dst[used++] = '\\'; dst[used++] = 't'; }
    else { dst[used++] = c; }
  }
  if ((used + 1) >= n) return -1;
  dst[used++] = '"';
  dst[used] = 0;
  return (int)used;
}

// Null literal.
static int fmt_null(char *dst, size_t n) {
  if ((size_t)4 >= n) return -1;
  memcpy(dst, "null", 4);
  dst[4] = 0;
  return 4;
}

int proto_to_json(const Record *r, char *buf, size_t n) {
  int off = 0;
  int w;
  char tmp[32];

  if ((size_t)(w = snprintf(buf + off, n - off,
        "{\"format\":\".osmell\",\"version\":\"1.0\","
        "\"hardware_id\":%s,"
        "\"timestamp_ms\":%lu,",
        fmt_str(tmp, sizeof(tmp), OS_HARDWARE_ID) >= 0 ? tmp : "\"OpenSmell_Monitor_v1.1\"",
        (unsigned long)r->ts)) < 0 || (size_t)w >= n) return -1;
  off += w;

  // cycle
  w = snprintf(buf + off, n - off,
        "\"cycle\":{\"id\":%u,\"phase\":%s,\"duration_s\":%.*f},",
        (unsigned)r->cycle_id,
        fmt_str(tmp, sizeof(tmp), phase_name(r->phase)) >= 0 ? tmp : "\"idle\"",
        2, (double)phase_duration_s(r->phase));
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // environment
  w = snprintf(buf + off, n - off,
        "\"environment\":{\"temperature_c\":%s,\"humidity_pct\":%s,\"sensor_id\":%s},",
        fmt_num(tmp, sizeof(tmp), r->t, 2) >= 0 ? tmp : "null",
        fmt_num(tmp, sizeof(tmp), r->rh, 2) >= 0 ? tmp : "null",
        fmt_str(tmp, sizeof(tmp), "SHT31") >= 0 ? tmp : "\"SHT31\"");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // slots (8 on v1.1: 0-3 analog, 4-7 digital)
  w = snprintf(buf + off, n - off, "\"slots\":[");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  const int SLOTS = 8;
  const float AO_DIVIDER = 2.0f;
  for (int i = 0; i < SLOTS; i++) {
    if (i) { if ((size_t)(off + 1) >= n) return -1; buf[off++] = ','; }

    bool analog = i < 4;
    int ai = analog ? i : i - 4;   // index into ao/adc/do_ or digital[]

    w = snprintf(buf + off, n - off,
          "{\"index\":%d,\"sensor_type\":%s,\"sensor_model\":%s,"
          "\"eeprom_id\":null,\"calibration_date\":null,"
          "\"readings\":{",
          i,
          analog ? "\"MOX\"" : "\"MEMS\"",
          (analog || r->digital[ai][0] == 0 || !strcmp(r->digital[ai], "none"))
            ? "null" : "");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    if (!analog && r->digital[ai][0] && strcmp(r->digital[ai], "none")) {
      w = fmt_str(buf + off, n - off, r->digital[ai]);
      if (w < 0 || (size_t)(off + w) >= n) return -1;
      off += w;
    } else {
      w = fmt_null(buf + off, n - off);
      if (w < 0 || (size_t)(off + w) >= n) return -1;
      off += w;
    }

    // readings
    w = snprintf(buf + off, n - off, "},"
          "\"readings\":{\"analog_value_v\":");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
    if (analog) {
      w = fmt_num(buf + off, n - off, r->ao[ai] * AO_DIVIDER, 3);
    } else {
      w = fmt_null(buf + off, n - off);
    }
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    w = snprintf(buf + off, n - off, ",\"digital_value\":");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
    if (analog) {
      w = snprintf(buf + off, n - off, "%d", r->adc[ai]);
    } else {
      w = fmt_null(buf + off, n - off);
    }
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    w = snprintf(buf + off, n - off, ",\"unit\":%s}",
          analog ? "\"V\"" : "\"ppm\"");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    // qc_flags (empty - injected by Osmograph)
    w = snprintf(buf + off, n - off, ",\"qc_flags\":[]}");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
  }

  w = snprintf(buf + off, n - off, "],\"user_metadata\":{}}");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  return off;
}
