// ota.h - HTTP OTA with EC P-256 manifest signature, SHA-256 image digest
// and monotonic version gate (plus rollback).
//
// The device verifies a host-signed manifest BEFORE downloading a single byte:
//   signature = ECDSA-P256( SHA256("version|sha256|size") )
// The DEPLOYMENT public key is in ota_pubkey.h; the private key is host-only.
// USB serial upload stays available as recovery; OTA is the normal path.
#pragma once

#include <stddef.h>
#include <stdint.h>

void ota_begin();          // boot-time rollback bookkeeping (call early in setup)
void ota_confirm();        // call once setup() completed successfully
bool ota_start(const char *url, const char *sha256_hex);
void ota_loop();           // non-blocking state machine, called from net_loop()
void ota_status(char *buf, size_t n);
void ota_factory_reset();  // clear OTA/rollback NVS
