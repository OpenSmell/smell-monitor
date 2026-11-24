// proto.cpp - build the JSON record by hand (no external JSON dependency).
//
// One fixed-shape object per completed measurement, matching the locked
// `.osmell` live-record schema.  Every slot is the same OSM-1 slot: the record
// does not encode an "analog bank" or a "digital bank".  Gas readings come from
// all eight slots, pH comes from an optional pluggable ISFET cartridge, and
// T/H comes from the soldered SHT31 - all in one record.
//
// Field order:
//   format, version, hardware_id, timestamp_ms, cycle, environment, ph, slots,
//   user_metadata
//
// Non-finite floats are emitted as JSON `null`, never as `nan`, so every
// transport always carries parseable JSON.  qc_flags and user_metadata are
// injected by Osmograph and by the user's annotation surface respectively.
#include "proto.h"
#include <Arduino.h>
#include <math.h>
#include <string.h>

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
    } else if (c == '\n') dst[used++] = '\\', dst[used++] = 'n';
    else if (c == '\r') dst[used++] = '\\', dst[used++] = 'r';
    else if (c == '\t') dst[used++] = '\\', dst[used++] = 't';
    else dst[used++] = c;
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

static bool i2c_model_present(const Record *r, int i) {
  return r->digital[i][0] && strcmp(r->digital[i], "none");
}

int proto_to_json(const Record *r, char *buf, size_t n) {
  int off = 0;
  int w;
  char tmp[32], tmp_where[24], tmp_kind[24], tmp_t[24], tmp_rh[24], tmp_id[24];

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

  // environment (T/H is a soldered reference, never a module)
  w = snprintf(buf + off, n - off,
        "\"environment\":{\"temperature_c\":%s,\"humidity_pct\":%s,\"sensor_id\":%s},",
        fmt_num(tmp_t, sizeof(tmp_t), r->t, 2) >= 0 ? tmp_t : "null",
        fmt_num(tmp_rh, sizeof(tmp_rh), r->rh, 2) >= 0 ? tmp_rh : "null",
        fmt_str(tmp_id, sizeof(tmp_id), "SHT31") >= 0 ? tmp_id : "\"SHT31\"");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // pH: an optional liquid ISFET cartridge, never a base-board sensor.
  w = snprintf(buf + off, n - off, "\"ph\":{\"value\":");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  if (r->ph_slot >= 0 && isfinite(r->ph_value)) {
    w = fmt_num(buf + off, n - off, r->ph_value, 2);
  } else {
    w = fmt_null(buf + off, n - off);
  }
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  w = snprintf(buf + off, n - off, ",\"slot\":");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  if (r->ph_slot >= 0) w = snprintf(buf + off, n - off, "%d", (int)r->ph_slot);
  else w = fmt_null(buf + off, n - off);
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;
  w = snprintf(buf + off, n - off, ",\"unit\":\"pH\"},");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  // slots: eight identical OSM-1 positions.  Slots 0..3 sit on the left wall,
  // slots 4..7 on the right; both rows face the same central channel.
  w = snprintf(buf + off, n - off, "\"slots\":[");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  for (int i = 0; i < 8; i++) {
    if (i) { if ((size_t)(off + 1) >= n) return -1; buf[off++] = ','; }

    const bool i2c = i2c_model_present(r, i);
    const char *kind = i2c ? "I2C" : (r->ao[i] > 0.01f ? "ANALOG" : "EMPTY");
    const char *where = (i >= 4) ? "right" : "left";
    w = snprintf(buf + off, n - off,
          "{\"index\":%d,\"flow_position\":%s,\"sensor_type\":%s,\"sensor_model\":",
          i,
          fmt_str(tmp_where, sizeof(tmp_where), where) >= 0 ? tmp_where : "\"left\"",
          fmt_str(tmp_kind, sizeof(tmp_kind), kind) >= 0 ? tmp_kind : "\"EMPTY\"");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    // Reuse tmp only after the previous snprintf has consumed it.
    if (i2c) w = fmt_str(buf + off, n - off, r->digital[i]);
    else w = fmt_null(buf + off, n - off);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    w = snprintf(buf + off, n - off,
          ",\"eeprom_id\":null,\"calibration_date\":null,"
          "\"readings\":{\"analog_value_v\":");
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
    w = fmt_num(buf + off, n - off, r->ao[i], 3);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;

    w = snprintf(buf + off, n - off,
          ",\"adc_counts\":%d,\"digital_pin\":%d,\"unit\":\"V\"},"
          "\"qc_flags\":[]}",
          (int)r->adc[i], (int)r->do_[i]);
    if (w < 0 || (size_t)(off + w) >= n) return -1;
    off += w;
  }

  w = snprintf(buf + off, n - off, "],\"user_metadata\":{}}");
  if (w < 0 || (size_t)(off + w) >= n) return -1;
  off += w;

  return off;
}
