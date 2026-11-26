// profile.cpp - minimal JSON profile parser + derived-value computation.
//
// Deliberately hand-written: only the keys documented in profile.h are read,
// unknown keys are skipped, and a malformed document is rejected before it is
// allowed anywhere near NVS. The raw AO readings remain the canonical data;
// identity / calibration fields in the record are untouched and stay null.
#include "profile.h"
#include <Arduino.h>
#include <Preferences.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace {

const size_t RAW_MAX = 1024;

struct SlotCfg {
  float zero;
  float span;
  bool  used;
  char  label[16];
  char  model[24];
};

SlotCfg s_slots[8];
int     s_mode = 0;              // 0 = mean, 1 = max
bool    s_active = false;
char    s_raw[RAW_MAX];

struct Parser {
  const char *p;
  explicit Parser(const char *s) : p(s) {}

  void ws() {
    while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
  }
  bool take(char c) { ws(); if (*p == c) { p++; return true; } return false; }
  bool expect(char c) { return take(c); }

  bool string(char *out, size_t n) {
    ws();
    if (*p != '"') return false;
    p++;
    size_t k = 0;
    while (*p && *p != '"') {
      char c = *p++;
      if (c == '\\') {
        char e = *p++;
        switch (e) {
          case 'n': c = '\n'; break;
          case 'r': c = '\r'; break;
          case 't': c = '\t'; break;
          case '0': c = '\0'; break;
          default:  c = e;    break;
        }
      }
      if (k + 1 < n) out[k++] = c;
    }
    if (*p != '"') return false;
    p++;
    out[k < n ? k : n - 1] = 0;
    return true;
  }

  bool integer(int *out) {
    ws();
    char *end = nullptr;
    long v = strtol(p, &end, 10);
    if (end == p) return false;
    p = end;
    *out = (int)v;
    return true;
  }

  bool number(float *out) {
    ws();
    char *end = nullptr;
    float v = strtof(p, &end);
    if (end == p) return false;
    p = end;
    *out = v;
    return true;
  }

  bool skip_value() {
    ws();
    if (*p == '"') {
      char tmp[64];
      return string(tmp, sizeof(tmp));
    }
    if (*p == '{' || *p == '[') {
      const char open = *p;
      const char close = (open == '{') ? '}' : ']';
      int depth = 0;
      while (*p) {
        if (*p == '"') { char tmp[64]; if (!string(tmp, sizeof(tmp))) return false; continue; }
        if (*p == open) depth++;
        else if (*p == close) {
          depth--;
          if (depth == 0) { p++; return true; }
        }
        p++;
      }
      return false;
    }
    while (*p && *p != ',' && *p != '}' && *p != ']') p++;
    return true;
  }
};

void reset_slots(SlotCfg out[8]) { memset(out, 0, 8 * sizeof(SlotCfg)); }

bool parse_slot(Parser &ps, SlotCfg out[8]) {
  if (!ps.expect('{')) return false;
  int index = -1;
  float zero = 0.0f, span = 1.0f;
  char label[16] = "", model[24] = "";
  while (true) {
    char key[24];
    if (!ps.string(key, sizeof(key)) || !ps.expect(':')) return false;
    if (!strcmp(key, "index")) {
      if (!ps.integer(&index)) return false;
    } else if (!strcmp(key, "zero")) {
      if (!ps.number(&zero)) return false;
    } else if (!strcmp(key, "span")) {
      if (!ps.number(&span)) return false;
    } else if (!strcmp(key, "label")) {
      if (!ps.string(label, sizeof(label))) return false;
    } else if (!strcmp(key, "model")) {
      if (!ps.string(model, sizeof(model))) return false;
    } else if (!ps.skip_value()) {
      return false;
    }
    if (ps.take('}')) break;
    if (!ps.expect(',')) return false;
  }
  if (index < 0 || index >= 8) return false;
  if (!isfinite(zero) || !isfinite(span) || span <= 0.0f) return false;
  out[index].zero = zero;
  out[index].span = span;
  out[index].used = true;
  strncpy(out[index].label, label, sizeof(out[index].label) - 1);
  strncpy(out[index].model, model, sizeof(out[index].model) - 1);
  return true;
}

bool parse(const char *json, SlotCfg out[8], int *mode) {
  if (!json || !*json) return false;
  Parser ps(json);
  if (!ps.expect('{')) return false;
  bool have_version = false;
  while (true) {
    char key[24];
    if (!ps.string(key, sizeof(key)) || !ps.expect(':')) return false;
    if (!strcmp(key, "version")) {
      int v = 0;
      if (!ps.integer(&v) || v != 1) return false;
      have_version = true;
    } else if (!strcmp(key, "aqi")) {
      char a[16];
      if (!ps.string(a, sizeof(a))) return false;
      if      (!strcmp(a, "mean")) *mode = 0;
      else if (!strcmp(a, "max"))  *mode = 1;
      else return false;
    } else if (!strcmp(key, "slots")) {
      if (!ps.expect('[')) return false;
      while (true) {
        if (ps.take(']')) break;
        if (!parse_slot(ps, out)) return false;
        if (ps.take(']')) break;
        if (!ps.expect(',')) return false;
      }
    } else if (!ps.skip_value()) {
      return false;
    }
    if (ps.take('}')) break;
    if (!ps.expect(',')) return false;
  }
  ps.ws();
  return have_version && *ps.p == 0;
}

void label_for_aqi(float aqi, char *out, size_t n) {
  const char *s;
  if      (!isfinite(aqi))   s = "";
  else if (aqi < 50.0f)      s = "good";
  else if (aqi < 100.0f)     s = "moderate";
  else if (aqi < 150.0f)     s = "sensitive";
  else if (aqi < 200.0f)     s = "unhealthy";
  else                       s = "hazardous";
  strncpy(out, s, n - 1);
  out[n - 1] = 0;
}

} // namespace

namespace Profile {

bool load() {
  char raw[RAW_MAX];
  raw[0] = 0;
  Preferences prefs;
  prefs.begin("opensmellpf", true);
  prefs.getString("raw", raw, sizeof(raw));
  prefs.end();
  if (!raw[0]) {
    memset(s_slots, 0, sizeof(s_slots));
    s_active = false;
    s_raw[0] = 0;
    return false;
  }
  return set_json(raw);
}

bool set_json(const char *json) {
  if (!json || strlen(json) >= RAW_MAX) return false;
  SlotCfg slots[8];
  int mode = 0;
  reset_slots(slots);
  if (!parse(json, slots, &mode)) return false;

  Preferences prefs;
  prefs.begin("opensmellpf", false);
  prefs.putString("raw", json);
  prefs.end();

  memcpy(s_slots, slots, sizeof(s_slots));
  s_mode = mode;
  strncpy(s_raw, json, sizeof(s_raw) - 1);
  s_raw[sizeof(s_raw) - 1] = 0;
  s_active = true;
  return true;
}

bool clear() {
  Preferences prefs;
  prefs.begin("opensmellpf", false);
  prefs.remove("raw");
  prefs.end();
  memset(s_slots, 0, sizeof(s_slots));
  s_raw[0] = 0;
  s_active = false;
  return true;
}

bool get_json(char *buf, size_t n) {
  if (!n) return false;
  strncpy(buf, s_raw, n - 1);
  buf[n - 1] = 0;
  return s_raw[0] != 0;
}

bool active() { return s_active; }

const char *label(uint8_t slot) {
  if (!s_active || slot >= 8 || !s_slots[slot].used) return "";
  return s_slots[slot].label;
}

void compute(const float ao[8], ProfileResult *out) {
  memset(out, 0, sizeof(*out));
  for (int i = 0; i < 8; i++) out->derived[i] = NAN;
  out->aqi = NAN;
  if (!s_active) return;

  strcpy(out->version, "v1");
  float sum = 0.0f, hi = -INFINITY;
  int n = 0;
  for (int i = 0; i < 8; i++) {
    if (!s_slots[i].used) continue;
    float v = (ao[i] - s_slots[i].zero) * s_slots[i].span;
    if (v < 0.0f || !isfinite(v)) v = 0.0f;
    out->derived[i] = v;
    sum += v;
    if (v > hi) hi = v;
    n++;
  }
  if (n) out->aqi = (s_mode == 1) ? hi : (sum / n);
  label_for_aqi(out->aqi, out->aqi_label, sizeof(out->aqi_label));
}

} // namespace Profile
