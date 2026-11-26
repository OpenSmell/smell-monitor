// ota_pubkey.h - DEPLOYMENT public key for signed OTA manifests.
//
// This is the ONLY key material compiled into the device.  It verifies the
// base64 DER ECDSA P-256 signature in <image-url>.json over the ASCII string
//     version|sha256|size
// (sha256 lowercase hex, size decimal, no added whitespace).
//
// The matching private key is held host-side and must never be committed.
// Generate a new deployment keypair with (host, outside the repo):
//     python firmware/esp32/smell_monitor/tools/sign_manifest.py keygen \
//         --key <secret-path>/ota_deploy.hex
// keygen prints the PEM to paste here.  Sign manifests with:
//     python firmware/esp32/smell_monitor/tools/sign_manifest.py sign \
//         --key <secret-path>/ota_deploy.hex --version <v> \
//         --sha256 <hex> --size <bytes> --out <image-url>.json
// Rolling this key requires flashing firmware over USB serial (the recovery
// path); OTA cannot replace the trust root.
#pragma once

static const char OS_OTA_PUBLIC_KEY_PEM[] =
    "-----BEGIN PUBLIC KEY-----\n"
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEGf6SpwrrfZqOisfphnpE9CNp1GOk\n"
    "m1bdnJ4psTcALds2qU6MpwFS1ETXEaAiJxDALO1pjQ412dmDe7zIznW0iw==\n"
    "-----END PUBLIC KEY-----\n";
