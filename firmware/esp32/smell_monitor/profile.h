// profile.h - optional interpretation profiles (raw slots stay canonical).
//
// A profile is a small JSON document:
//   {"version":1,"slots":[
//      {"index":0,"model":"MQ-135","zero":0.1,"span":3.0,"label":"AQ"}, ...],
//    "aqi":"mean"|"max"}
//
// It is stored verbatim in Preferences NVS and parsed with a tiny hand-written
// parser (no ArduinoJson). With no profile installed the firmware keeps its
// original raw-only behaviour: derived values and AQI are all null in JSON.
#pragma once

#include <stdint.h>
#include <stddef.h>

struct ProfileResult {
  bool  active;
  char  version[16];       // "v1" when a profile is applied
  float derived[8];        // NaN for slots not configured by the profile
  float aqi;               // NaN when no configured slots
  char  aqi_label[16];     // e.g. "good"
};

namespace Profile {
  bool load();                        // reload raw JSON from NVS at boot
  bool set_json(const char *json);    // validate + persist + activate
  bool clear();                       // remove from NVS, revert to raw-only
  bool get_json(char *buf, size_t n); // copy the stored raw JSON
  bool active();
  const char *label(uint8_t slot);    // "" when the slot has no profile entry
  void compute(const float ao[8], ProfileResult *out);
}
