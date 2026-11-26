// ota.cpp - field firmware update over plain HTTP.
//
// Host-side contract (see comments in ota.h / net.cpp command dispatcher):
//   ota <url> <sha256>
//   <url>.json must be a small manifest:
//     {"version":"1.3.0","sha256":"<64 hex>","size":123456,
//      "signature":"<base64 DER ECDSA-P256>"}
// The signature covers the ASCII canonical string  version|sha256|size
// (lowercase hex digest, decimal size).  It is checked on the DEVICE with the
// embedded DEPLOYMENT public key (ota_pubkey.h) before any image bytes are
// fetched.  The command-line digest must equal the manifest digest, the
// manifest version must be greater than FW_VERSION, and the image must hash
// to that digest (Update.setSHA256()) and match the manifest size.
//
// This is device-side authenticity for the OTA payload.  ESP32 secure boot /
// flash encryption are a separate chain of trust and remain out of scope.
//
// Rollback: Update.end() switches the boot partition only after the digest has
// passed. The new image calls ota_confirm() at the end of a successful setup();
// esp_ota_mark_app_valid_cancel_rollback() marks it valid there (when the
// bootloader has rollback support compiled in). A small NVS try-counter gives
// a software fallback: after three boots that never confirm, the previous
// partition is selected again. USB serial flashing always remains available.
#include "ota.h"
#include "config.h"
#include "ota_pubkey.h"
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <Update.h>
#include <esp_err.h>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <mbedtls/base64.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>
#include <mbedtls/sha256.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace {

enum OtaState {
  OTA_IDLE = 0,
  OTA_MANIFEST,
  OTA_DOWNLOAD,
  OTA_VERIFY,
  OTA_REBOOT,
  OTA_ERROR,
};

const uint32_t HTTP_TIMEOUT_MS = 3000;
const uint32_t DOWNLOAD_TIMEOUT_MS = 180000;
const size_t   CHUNK = 512;
const uint8_t  MAX_TRIES = 3;
const uint32_t MAX_IMAGE_SIZE = 2031616;   // no_fs: 2 MB app slot

OtaState     s_state = OTA_IDLE;
char         s_url[160] = "";
char         s_digest[65] = "";
char         s_manifest_version[24] = "";
char         s_error[80] = "";
uint32_t     s_manifest_size = 0;
uint32_t     s_total = 0;
uint32_t     s_progress = 0;
uint32_t     s_entered = 0;
uint32_t     s_last_report = 0;
HTTPClient  *s_http = nullptr;
NetworkClient *s_stream = nullptr;
bool         s_image_open = false;

const char *state_name(OtaState s) {
  switch (s) {
    case OTA_IDLE:     return "idle";
    case OTA_MANIFEST: return "manifest";
    case OTA_DOWNLOAD: return "downloading";
    case OTA_VERIFY:   return "verifying";
    case OTA_REBOOT:   return "rebooting";
    case OTA_ERROR:    return "error";
    default:           return "unknown";
  }
}

void set_state(OtaState s) {
  s_state = s;
  s_entered = millis();
}

void fail(const char *msg) {
  strncpy(s_error, msg, sizeof(s_error) - 1);
  s_error[sizeof(s_error) - 1] = 0;
  if (s_image_open) { Update.abort(); s_image_open = false; }
  if (s_http) { s_http->end(); delete s_http; s_http = nullptr; }
  s_stream = nullptr;
  set_state(OTA_ERROR);
  Serial.print("OTA error: ");
  Serial.println(s_error);
}

bool hex64(const char *s, char out[65]) {
  if (!s || strlen(s) != 64) return false;
  for (int i = 0; i < 64; i++) {
    char c = s[i];
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
          (c >= 'A' && c <= 'F'))) return false;
    out[i] = (c >= 'A' && c <= 'F') ? (char)(c - 'A' + 'a') : c;
  }
  out[64] = 0;
  return true;
}

// Read a simple string value from a flat JSON object.
bool json_string(const char *json, const char *key, char *out, size_t n) {
  char needle[32];
  snprintf(needle, sizeof(needle), "\"%s\"", key);
  const char *p = strstr(json, needle);
  if (!p) return false;
  p = strchr(p + strlen(needle), ':');
  if (!p) return false;
  p++;
  while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
  if (*p != '"') return false;
  p++;
  size_t k = 0;
  while (*p && *p != '"') {
    if (k + 1 >= n) return false;
    out[k++] = *p++;
  }
  if (*p != '"') return false;
  out[k] = 0;
  return true;
}

// Read a decimal JSON number (used for the signed "size" field).
bool json_uint(const char *json, const char *key, uint32_t *out) {
  char needle[32];
  snprintf(needle, sizeof(needle), "\"%s\"", key);
  const char *p = strstr(json, needle);
  if (!p) return false;
  p = strchr(p + strlen(needle), ':');
  if (!p) return false;
  p++;
  while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
  if (*p < '0' || *p > '9') return false;
  char *end = nullptr;
  unsigned long v = strtoul(p, &end, 10);
  if (end == p || v == 0 || v > 0xFFFFFFFFUL) return false;
  *out = (uint32_t)v;
  return true;
}

// Device-side verification of the manifest signature.  Everything signed is
// taken from the manifest itself; no host-supplied value is trusted here.
bool verify_manifest_signature(const char *version, const char *sha256_hex,
                               uint32_t size, const char *signature_b64) {
  char canonical[128];
  int n = snprintf(canonical, sizeof(canonical), "%s|%s|%lu",
                   version, sha256_hex, (unsigned long)size);
  if (n <= 0 || (size_t)n >= sizeof(canonical)) return false;

  unsigned char hash[32];
  if (mbedtls_sha256((const unsigned char *)canonical, (size_t)n, hash, 0) != 0)
    return false;

  unsigned char sig[256];
  size_t sig_len = 0;
  if (mbedtls_base64_decode(sig, sizeof(sig), &sig_len,
                            (const unsigned char *)signature_b64,
                            strlen(signature_b64)) != 0 || sig_len == 0)
    return false;

  mbedtls_pk_context pk;
  mbedtls_pk_init(&pk);
  int ret = mbedtls_pk_parse_public_key(
      &pk, (const unsigned char *)OS_OTA_PUBLIC_KEY_PEM,
      strlen(OS_OTA_PUBLIC_KEY_PEM) + 1);
  if (ret == 0 && !mbedtls_pk_can_do(&pk, MBEDTLS_PK_ECDSA))
    ret = -1;
  if (ret == 0)
    ret = mbedtls_pk_verify(&pk, MBEDTLS_MD_SHA256, hash, sizeof(hash),
                           sig, sig_len);
  mbedtls_pk_free(&pk);
  return ret == 0;
}

// Strictly greater dotted version (up to three components), e.g. 1.2.0 < 1.3.0.
bool version_greater(const char *a, const char *b) {
  int av[3] = {0, 0, 0}, bv[3] = {0, 0, 0};
  if (sscanf(a, "%d.%d.%d", &av[0], &av[1], &av[2]) < 1) return false;
  if (sscanf(b, "%d.%d.%d", &bv[0], &bv[1], &bv[2]) < 1) return false;
  for (int i = 0; i < 3; i++) {
    if (av[i] != bv[i]) return av[i] > bv[i];
  }
  return false;
}

void do_manifest() {
  if (WiFi.status() != WL_CONNECTED) { fail("wifi offline"); return; }

  String manifest_url = String(s_url) + ".json";
  HTTPClient h;
  h.setTimeout(HTTP_TIMEOUT_MS);
  if (!h.begin(manifest_url)) { fail("manifest connect failed"); return; }
  int code = h.GET();
  if (code != 200) {
    h.end();
    snprintf(s_error, sizeof(s_error), "manifest HTTP %d", code);
    set_state(OTA_ERROR);
    Serial.print("OTA error: "); Serial.println(s_error);
    return;
  }
  String body = h.getString();
  h.end();
  if (body.length() == 0 || body.length() > 512) { fail("manifest empty/invalid"); return; }

  char mver[24] = "", msha[65] = "", msig[160] = "";
  uint32_t msize = 0;
  if (!json_string(body.c_str(), "version", mver, sizeof(mver)) ||
      !json_string(body.c_str(), "sha256", msha, sizeof(msha)) ||
      !json_uint(body.c_str(), "size", &msize) ||
      !json_string(body.c_str(), "signature", msig, sizeof(msig))) {
    fail("manifest fields missing");
    return;
  }
  char want[65];
  if (!hex64(msha, want) || strcmp(want, s_digest) != 0) {
    fail("manifest digest mismatch");
    return;
  }
  if (!version_greater(mver, FW_VERSION)) { fail("manifest version not newer"); return; }
  if (msize == 0 || msize > MAX_IMAGE_SIZE) { fail("manifest size invalid"); return; }

  // DEVICE-SIDE TRUST GATE: reject a rewritten manifest before any download.
  if (!verify_manifest_signature(mver, want, msize, msig)) {
    fail("manifest signature invalid");
    return;
  }

  strncpy(s_manifest_version, mver, sizeof(s_manifest_version) - 1);
  s_manifest_version[sizeof(s_manifest_version) - 1] = 0;
  s_manifest_size = msize;

  // Image transfer requires a plain HTTP server sending Content-Length
  // (identity encoding). Direct TCP reads do not decompress chunked bodies.
  s_http = new HTTPClient();
  s_http->setTimeout(HTTP_TIMEOUT_MS);
  s_http->setReuse(false);
  if (!s_http->begin(s_url)) { fail("image connect failed"); return; }
  int image_code = s_http->GET();
  if (image_code != 200) {
    snprintf(s_error, sizeof(s_error), "image HTTP %d", image_code);
    s_http->end(); delete s_http; s_http = nullptr;
    set_state(OTA_ERROR);
    Serial.print("OTA error: "); Serial.println(s_error);
    return;
  }
  s_total = (s_http->getSize() > 0) ? (uint32_t)s_http->getSize() : 0;
  if (s_total && s_total != s_manifest_size) {
    fail("image size does not match signed manifest");
    return;
  }
  s_progress = 0;
  s_stream = s_http->getStreamPtr();
  if (!s_stream) { fail("image stream unavailable"); return; }

  if (!Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) { fail("update begin failed"); return; }
  if (!Update.setSHA256(s_digest)) { fail("invalid sha256"); return; }
  s_image_open = true;
  set_state(OTA_DOWNLOAD);
  Serial.printf("OTA downloading %s -> %s\n", s_manifest_version, s_url);
}

void do_download() {
  if (!s_stream) { fail("stream lost"); return; }
  if (millis() - s_entered > DOWNLOAD_TIMEOUT_MS) { fail("download timeout"); return; }

  int avail = s_stream->available();
  if (avail > 0) {
    uint8_t buf[CHUNK];
    size_t want = (size_t)avail;
    if (want > CHUNK) want = CHUNK;
    int got = s_stream->read(buf, want);
    if (got > 0) {
      size_t written = Update.write(buf, (size_t)got);
      if (written != (size_t)got) { fail("flash write failed"); return; }
      s_progress += written;
      if (s_progress - s_last_report >= (256 * 1024)) {
        s_last_report = s_progress;
        Serial.printf("OTA %u bytes\n", (unsigned)s_progress);
      }
    }
    return;
  }
  if (s_total && s_progress >= s_total) { set_state(OTA_VERIFY); return; }
  if (!s_stream->connected()) {
    if (s_total && s_progress < s_total) { fail("short download"); return; }
    set_state(OTA_VERIFY);
  }
}

void do_verify() {
  if (s_http) { s_http->end(); delete s_http; s_http = nullptr; }
  s_stream = nullptr;
  if (!s_image_open) { fail("no image to verify"); return; }
  if (s_progress != s_manifest_size ||
      (s_total && s_progress != s_total)) { fail("size mismatch"); return; }
  if (Update.hasError()) { fail("image check failed"); return; }

  char prev[16] = "";
  const esp_partition_t *boot = esp_ota_get_boot_partition();
  if (boot) strncpy(prev, boot->label, sizeof(prev) - 1);

  // end() verifies the SHA-256 and switches the boot partition only on success.
  if (!Update.end(false)) { s_image_open = false; fail("update end failed"); return; }
  s_image_open = false;

  Preferences prefs;
  prefs.begin("opensmellota", false);
  prefs.putBool("pending", true);
  prefs.putUChar("tries", 0);
  prefs.putString("prev", prev);
  prefs.end();
  set_state(OTA_REBOOT);
  Serial.println("OTA verified; rebooting into new firmware");
}

} // namespace

void ota_begin() {
  Preferences prefs;
  prefs.begin("opensmellota", false);
  if (!prefs.getBool("pending", false)) { prefs.end(); return; }

  char prev[16] = "";
  prefs.getString("prev", prev, sizeof(prev));
  const esp_partition_t *running = esp_ota_get_running_partition();
  // Already running the previous (rolled-back) image: clear stale bookkeeping.
  if (running && prev[0] && !strcmp(running->label, prev)) {
    prefs.putBool("pending", false);
    prefs.putUChar("tries", 0);
    prefs.end();
    return;
  }

  uint8_t tries = (uint8_t)(prefs.getUChar("tries", 0) + 1);
  if (tries >= MAX_TRIES && prev[0]) {
    const esp_partition_t *p = esp_partition_find_first(
        ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_ANY, prev);
    if (p) esp_ota_set_boot_partition(p);
    prefs.putBool("pending", false);
    prefs.putUChar("tries", 0);
    prefs.end();
    Serial.println("OTA: boot confirmation failed; rolling back");
    ESP.restart();
  }
  prefs.putUChar("tries", tries);
  prefs.end();
  Serial.printf("OTA: awaiting boot confirmation (%u/%u)\n",
                (unsigned)tries, (unsigned)MAX_TRIES);
}

void ota_confirm() {
  // Returns ESP_ERR_NOT_SUPPORTED when the bootloader was built without
  // rollback support; the NVS try-counter fallback is always cleared too.
  esp_ota_mark_app_valid_cancel_rollback();
  Preferences prefs;
  prefs.begin("opensmellota", false);
  prefs.putBool("pending", false);
  prefs.putUChar("tries", 0);
  prefs.end();
}

bool ota_start(const char *url, const char *sha256_hex) {
  if (s_state != OTA_IDLE && s_state != OTA_ERROR) return false;
  if (!url || strncmp(url, "http://", 7) || strlen(url) >= sizeof(s_url)) return false;
  char want[65];
  if (!hex64(sha256_hex, want)) return false;

  strncpy(s_url, url, sizeof(s_url) - 1);
  s_url[sizeof(s_url) - 1] = 0;
  strcpy(s_digest, want);
  s_manifest_version[0] = 0;
  s_error[0] = 0;
  s_manifest_size = 0;
  s_total = s_progress = s_last_report = 0;
  set_state(OTA_MANIFEST);
  return true;
}

void ota_loop() {
  switch (s_state) {
    case OTA_MANIFEST: do_manifest(); break;
    case OTA_DOWNLOAD: do_download(); break;
    case OTA_VERIFY:   do_verify();   break;
    case OTA_REBOOT:
      if (millis() - s_entered > 500) ESP.restart();
      break;
    default: break;
  }
}

void ota_status(char *buf, size_t n) {
  snprintf(buf, n,
           "{\"state\":\"%s\",\"version\":\"%s\",\"progress\":%u,"
           "\"size\":%u,\"error\":\"%s\"}",
           state_name(s_state), s_manifest_version,
           (unsigned)s_progress, (unsigned)s_total, s_error);
}

void ota_factory_reset() {
  Preferences prefs;
  prefs.begin("opensmellota", false);
  prefs.clear();
  prefs.end();
  s_state = OTA_IDLE;
  s_url[0] = s_digest[0] = s_error[0] = 0;
}
