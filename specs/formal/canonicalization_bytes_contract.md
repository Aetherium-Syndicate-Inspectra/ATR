# Canonicalization Bytes Contract

1. Input must be normalized with Unicode NFC for all string keys/values.
2. Object keys are ordered by raw UTF-8 byte sequence.
3. JSON output has no insignificant whitespace and uses `,` / `:` separators only.
4. Signature digest MUST be derived from these canonical bytes only.
