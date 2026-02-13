# Canonicalization (Canonical Bytes) — ATR Core Spec

**File:** `specs/canonicalization.md`
**Status:** Normative (MUST)
**Version:** `2.0.0`

## 1) Canonicalization input

Canonicalization input is exactly:

```json
{"header": header, "meta": meta_or_empty_object, "payload": payload}
```

Excluded from canonicalization:
- `signature`
- transport metadata
- any transient server fields

## 2) Canonical format

ATR Core v2 canonicalization uses RFC 8785 JSON Canonicalization Scheme (JCS) semantics:
- UTF-8 output bytes
- lexicographic key sorting at every object level
- no extra whitespace
- JSON-compliant escaping
- deterministic number encoding
- array order preserved

## 3) Strict guards

Canonicalization MUST reject:
- `NaN`, `+Inf`, `-Inf`
- non-string map keys
- unsupported runtime types (e.g. `bytes`, `set`, `complex`)

Canonicalization failure reasons:
- `CANON_INVALID_NUMBER`
- `CANON_NON_STRING_KEY`
- `CANON_FORBIDDEN_TYPE`
- `CANON_ENCODING_ERROR`

## 4) Hashing and signing

- `canonical_hash = BLAKE3(canonical_bytes)` (32 bytes)
- `signature = Ed25519.sign(canonical_hash)`
- signature encoding for v2: **base64url without padding**

Verification MUST compute canonical bytes then BLAKE3 hash, then verify signature against `header.source_agent`.

## 5) Determinism vectors

Reference vectors are committed at:
- `specs/vectors/canonical_bytes_001.txt`
- `specs/vectors/canonical_hash_001.hex`
