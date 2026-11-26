#!/usr/bin/env python3
"""Host-side ECDSA P-256 signer for OpenSmell signed OTA manifests.

The firmware embeds only the *public* key (ota_pubkey.h).  The private key
never belongs in this repository: keep it in an operator-controlled file and
pass its path with --key.

Canonical signed string (ASCII, no whitespace, no JSON reformatting):

    <version>|<sha256>|<size>

  * version : manifest "version", exactly as emitted (e.g. 1.3.0)
  * sha256  : manifest "sha256", 64 lowercase hex characters
  * size    : manifest "size", decimal integer with no leading zeros

The signature is SHA-256 with ECDSA on NIST P-256, DER-encoded
(SEQUENCE of two INTEGERs), then standard base64 in the manifest's
"signature" field.  mbedTLS on the device verifies exactly that string.

Pure standard library only (hashlib/hmac/secrets).  The private key file is
raw 32-byte big-endian scalar as 64 hex characters (optionally with a PEM-like
header line); this avoids a dependency on cryptography/openssl on the build
host.  Use `keygen` to create one and to print the PEM public key to embed.

Examples:
    python sign_manifest.py keygen --key $HOME/.opensmell/ota_deploy.hex
    python sign_manifest.py sign --key $HOME/.opensmell/ota_deploy.hex \
        --version 1.3.0 --sha256 <64 hex> --size 123456 --out app.bin.json
    python sign_manifest.py sign --key ... --manifest app.bin.json
    python sign_manifest.py verify --public ota_public.pem --manifest app.bin.json
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys

# --- NIST P-256 (secp256r1) -------------------------------------------------
P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
A = P - 3
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
GX = 0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296
GY = 0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1 + A) * pow(2 * y1 % P, -1, P) % P
    else:
        lam = (y2 - y1) * pow((x2 - x1) % P, -1, P) % P
    x3 = (lam * lam - x1 - x2) % P
    return (x3, (lam * (x1 - x3) - y1) % P)


def _mul(k, point=(GX, GY)):
    k %= N
    result = None
    while k:
        if k & 1:
            result = _add(result, point)
        point = _add(point, point)
        k >>= 1
    return result


def _int_to_bytes(v, size=32):
    return v.to_bytes(size, "big")


def _der_len(n):
    if n < 128:
        return bytes([n])
    b = _int_to_bytes(n).lstrip(b"\x00") or b"\x00"
    return bytes([0x80 | len(b)]) + b


def _der_int(v):
    b = _int_to_bytes(v).lstrip(b"\x00") or b"\x00"
    if b[0] & 0x80:
        b = b"\x00" + b
    return b"\x02" + _der_len(len(b)) + b


def der_signature(r, s):
    body = _der_int(r) + _der_int(s)
    return b"\x30" + _der_len(len(body)) + body


def _pem(der, label):
    b64 = base64.b64encode(der).decode("ascii")
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN %s-----\n%s\n-----END %s-----\n" % (
        label, "\n".join(lines), label)


def public_pem(private_int):
    """SPKI PEM for the P-256 public point, matching mbedtls_pk_parse_public_key."""
    qx, qy = _mul(private_int)
    alg = bytes.fromhex("301306072a8648ce3d020106082a8648ce3d030107")
    point = b"\x00\x04" + _int_to_bytes(qx) + _int_to_bytes(qy)
    bitstr = b"\x03" + _der_len(len(point)) + point
    spki = alg + bitstr
    return _pem(b"\x30" + _der_len(len(spki)) + spki, "PUBLIC KEY")


def _rfc6979_k(private_int, digest):
    """Deterministic nonce per RFC 6979 (HMAC-SHA256)."""
    h1 = _int_to_bytes(private_int) + digest
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        t = b""
        while len(t) < 32:
            v = hmac.new(k, v, hashlib.sha256).digest()
            t += v
        candidate = int.from_bytes(t[:32], "big")
        if 1 <= candidate < N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign(private_int, message):
    digest = hashlib.sha256(message.encode("ascii")).digest()
    z = int.from_bytes(digest, "big")
    while True:
        k = _rfc6979_k(private_int, digest)
        rx, _ = _mul(k)
        r = rx % N
        if r == 0:
            continue
        s = (pow(k, -1, N) * (z + r * private_int)) % N
        if s != 0:
            return der_signature(r, s)


def verify(public_point, message, signature):
    """Local self-check; the device uses mbedTLS, not this function."""
    r, s = _parse_der_signature(signature)
    if not (1 <= r < N and 1 <= s < N):
        return False
    z = int.from_bytes(hashlib.sha256(message.encode("ascii")).digest(), "big")
    w = pow(s, -1, N)
    u1, u2 = z * w % N, r * w % N
    point = _add(_mul(u1), _mul(u2, public_point))
    return point is not None and point[0] % N == r


def _parse_der_signature(der):
    if len(der) < 8 or der[0] != 0x30:
        raise ValueError("signature is not a DER SEQUENCE")
    i = 1
    n = der[i]
    i += 1
    if n & 0x80:
        cnt = n & 0x7F
        n = int.from_bytes(der[i:i + cnt], "big")
        i += cnt
    if i + n != len(der):
        raise ValueError("bad DER length")
    vals = []
    for _ in range(2):
        if der[i] != 0x02:
            raise ValueError("signature integers missing")
        i += 1
        ln = der[i]
        i += 1
        vals.append(int.from_bytes(der[i:i + ln], "big"))
        i += ln
    if i != len(der):
        raise ValueError("trailing DER bytes")
    return vals[0], vals[1]


def _parse_pem_public(text):
    m = re.search(r"-----BEGIN PUBLIC KEY-----(.*?)-----END PUBLIC KEY-----", text, re.S)
    if not m:
        raise ValueError("public PEM not found")
    der = base64.b64decode("".join(m.group(1).split()))
    # SPKI for P-256: 30 59 30 13 ... 03 42 00 04 X(32) Y(32)
    point = der[-65:]
    if point[0] != 0x04 or len(point) != 65:
        raise ValueError("unexpected public point encoding")
    return (int.from_bytes(point[1:33], "big"),
            int.from_bytes(point[33:65], "big"))


def load_private(path):
    text = open(path, encoding="ascii").read()
    hexes = re.findall(r"\b[0-9a-fA-F]{64}\b", text)
    if not hexes:
        raise ValueError("private key file must contain 64 hex characters")
    d = int(hexes[-1], 16)
    if not 1 <= d < N:
        raise ValueError("private scalar out of range")
    return d


def canonical(version, sha256_hex, size):
    sha256_hex = sha256_hex.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256_hex):
        raise ValueError("sha256 must be 64 hex characters")
    if not re.fullmatch(r"\d+", str(size)) or int(size) <= 0:
        raise ValueError("size must be a positive decimal integer")
    return "%s|%s|%d" % (version, sha256_hex, int(size))


def manifest_dict(version, sha256_hex, size, signature):
    return {"version": version, "sha256": sha256_hex.lower(),
            "size": int(size), "signature": signature}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    kg = sub.add_parser("keygen", help="create a deployment private key (off-device)")
    kg.add_argument("--key", required=True, help="private key OUTPUT path (keep secret)")

    sg = sub.add_parser("sign", help="sign a manifest with a private key path")
    sg.add_argument("--key", required=True, help="private key file (64 hex characters)")
    sg.add_argument("--version", help="firmware version, e.g. 1.3.0")
    sg.add_argument("--sha256", help="firmware image SHA-256 (64 hex)")
    sg.add_argument("--size", type=int, help="firmware image size in bytes")
    sg.add_argument("--manifest", help="read version/sha256/size from an existing JSON manifest")
    sg.add_argument("--out", help="write signed manifest JSON here (default: stdout)")

    vf = sub.add_parser("verify", help="locally verify a signed manifest (self-check)")
    vf.add_argument("--public", required=True, help="PEM public key path")
    vf.add_argument("--manifest", required=True, help="signed manifest JSON path")

    args = ap.parse_args()

    if args.cmd == "keygen":
        d = secrets.randbelow(N - 1) + 1
        directory = os.path.dirname(os.path.abspath(args.key))
        if directory:
            os.makedirs(directory, exist_ok=True)
        oldmask = None
        if hasattr(os, "umask"):
            oldmask = os.umask(0o077)
        try:
            with open(args.key, "w", encoding="ascii", newline="\n") as f:
                f.write("# OpenSmell OTA deployment private key - NEVER commit\n")
                f.write(_int_to_bytes(d).hex() + "\n")
        finally:
            if oldmask is not None:
                os.umask(oldmask)
        print("wrote private key to %s (keep it off-device and out of git)" % args.key)
        print(public_pem(d), end="")
        return

    if args.cmd == "sign":
        d = load_private(args.key)
        if args.manifest:
            src = json.load(open(args.manifest, encoding="utf-8"))
            version = args.version or src["version"]
            sha = args.sha256 or src["sha256"]
            size = args.size if args.size is not None else src["size"]
        else:
            if args.version is None or args.sha256 is None or args.size is None:
                ap.error("sign needs --version --sha256 --size or --manifest")
            version, sha, size = args.version, args.sha256, args.size
        msg = canonical(version, sha, size)
        sig = base64.b64encode(sign(d, msg)).decode("ascii")
        text = json.dumps(manifest_dict(version, sha, size, sig),
                          separators=(",", ":")) + "\n"
        if args.out:
            with open(args.out, "w", encoding="ascii", newline="\n") as f:
                f.write(text)
            print("signed manifest -> %s" % args.out)
        else:
            sys.stdout.write(text)
        return

    if args.cmd == "verify":
        point = _parse_pem_public(open(args.public, encoding="ascii").read())
        src = json.load(open(args.manifest, encoding="utf-8"))
        msg = canonical(src["version"], src["sha256"], src["size"])
        ok = verify(point, msg, base64.b64decode(src["signature"]))
        print("manifest signature %s" % ("OK" if ok else "INVALID"))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
