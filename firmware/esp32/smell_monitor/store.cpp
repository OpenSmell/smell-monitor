// store.cpp - fixed 32-record binary blob ring in ESP32 NVS (Preferences).
//
// Every generated record is journalled here, whether or not a transport was
// enabled when it was produced.  The write is synchronous: putBytes() commits
// before store_append() returns, so an immediate power loss after generation
// still leaves the record recoverable via /data or `replay <since>`.
//
// Layout (no filesystem):
//   namespace "opensmell"   key "seq"   uint32  last allocated sequence id
//   namespace "opensmellrec":
//       "fmt"   uint32  ring layout version (bump when Record changes)
//       "head"  uint8   next slot to overwrite
//       "count" uint8   valid entries (<= 32)
//       "r00".."r31"    sizeof(Record)-byte blobs
//
// With the current 344-byte Record this is ~11 KB of the 20 KB NVS partition
// (no_fs scheme), comfortably below the per-blob NVS limit (~4 KB).
#include "store.h"
#include <Arduino.h>
#include <Preferences.h>
#include <stdio.h>
#include <string.h>

static_assert(sizeof(Record) <= 400,
              "Record grew too large for the 32-slot NVS ring; increase NVS");

namespace {

const uint8_t  RING_SLOTS = 32;
const uint32_t RING_FMT   = 3;       // bump whenever struct Record changes

uint32_t g_seq = 0;                  // mirrored from Preferences "opensmell"/"seq"
uint8_t  g_head = 0;
uint8_t  g_count = 0;

void ring_key(char *out, size_t n, uint8_t slot) {
  snprintf(out, n, "r%02u", (unsigned)(slot % RING_SLOTS));
}

} // namespace

void store_begin() {
  Preferences p;
  p.begin("opensmell", true);
  g_seq = p.getUInt("seq", 0);
  p.end();

  p.begin("opensmellrec", false);
  if (p.getUInt("fmt", 0) != RING_FMT) {
    // Old/incompatible layout: drop stale blobs, keep the sequence counter.
    p.clear();
    p.putUInt("fmt", RING_FMT);
    p.putUChar("head", 0);
    p.putUChar("count", 0);
    g_head = g_count = 0;
  } else {
    g_head = (uint8_t)(p.getUChar("head", 0) % RING_SLOTS);
    uint8_t count = p.getUChar("count", 0);
    g_count = count > RING_SLOTS ? RING_SLOTS : count;
  }
  p.end();
}

uint32_t store_last_sequence() { return g_seq; }

uint32_t store_next_sequence() {
  uint32_t next = g_seq + 1;
  if (next == 0) next = 1;           // ignore the wrap marker at UINT32_MAX

  Preferences p;
  p.begin("opensmell", false);
  size_t wrote = p.putUInt("seq", next);
  p.end();
  // Keep the in-RAM counter moving even if the NVS write fails, so sequence
  // ids stay unique within this boot.
  g_seq = next;
  if (wrote != sizeof(uint32_t)) Serial.println("store: sequence persist failed");
  return next;
}

void store_append(const Record &r) {
  Preferences p;
  p.begin("opensmellrec", false);
  char key[4];
  ring_key(key, sizeof(key), g_head);
  size_t wrote = p.putBytes(key, &r, sizeof(r));
  if (wrote == sizeof(r)) {
    uint8_t head = (uint8_t)((g_head + 1) % RING_SLOTS);
    uint8_t count = g_count < RING_SLOTS ? (uint8_t)(g_count + 1) : RING_SLOTS;
    p.putUChar("head", head);
    p.putUChar("count", count);
    p.end();
    g_head = head;
    g_count = count;
  } else {
    p.end();
    Serial.printf("store: ring write failed (%u/%u bytes)\n",
                  (unsigned)wrote, (unsigned)sizeof(r));
  }
}

uint32_t store_count() { return g_count; }

bool store_get(uint32_t index, Record *out) {
  if (!out || index >= g_count) return false;

  uint8_t start = (uint8_t)((g_head + RING_SLOTS - g_count) % RING_SLOTS);
  char key[4];
  ring_key(key, sizeof(key), (uint8_t)((start + index) % RING_SLOTS));

  Preferences p;
  p.begin("opensmellrec", true);
  size_t got = p.getBytes(key, out, sizeof(*out));
  p.end();
  return got == sizeof(*out);
}

size_t store_write_replay(uint32_t since, String &out) {
  char json[2048];
  size_t emitted = 0;
  out.reserve(4096);
  out += '[';
  for (uint32_t i = 0; i < g_count; i++) {
    Record r;
    if (!store_get(i, &r) || r.seq <= since) continue;
    int n = proto_to_json(&r, json, sizeof(json));
    if (n <= 0) continue;
    if (emitted) out += ',';
    out += json;
    emitted++;
  }
  out += ']';
  return emitted;
}

void store_factory_reset() {
  Preferences p;
  p.begin("opensmellrec", false);
  p.clear();
  p.end();
  g_seq = 0;
  g_head = 0;
  g_count = 0;
}
