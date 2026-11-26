// store.h - NVS ring of generated measurement records (power-fail journal).
#pragma once

#include "proto.h"
#include <Arduino.h>   // String
#include <stdint.h>

// Load the persistent sequence and ring bookkeeping.  A layout change resets
// the ring but NOT the sequence (ids must stay monotonic across firmware OTA).
void store_begin();

// Allocate and immediately persist the next 1-based sequence id.
uint32_t store_next_sequence();
uint32_t store_last_sequence();

// Append one generated record to the 32-slot ring and flush it to NVS before
// returning (no external filesystem, no deferred write).
void store_append(const Record &r);

// Ring contents in ascending sequence order, oldest surviving record first.
uint32_t store_count();
bool store_get(uint32_t index, Record *out);

// Build a JSON array of records with sequence > since (oldest first).
size_t store_write_replay(uint32_t since, String &out);

// Factory reset: drop all ring blobs (the sequence lives in "opensmell",
// which the caller clears too).
void store_factory_reset();
