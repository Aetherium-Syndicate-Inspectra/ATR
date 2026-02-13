from __future__ import annotations

import base64
import binascii
import hashlib

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

try:
    import blake3  # type: ignore
except ImportError:  # pragma: no cover
    blake3 = None


def canonical_hash(canonical_bytes: bytes) -> bytes:
    if blake3 is not None:
        return blake3.blake3(canonical_bytes).digest()
    return hashlib.sha256(canonical_bytes).digest()


def _decode_base64url(signature: str) -> bytes:
    padding = "=" * ((4 - len(signature) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(signature + padding)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64url signature") from exc


def verify_signature(source_agent: str, digest: bytes, signature: str) -> bool:
    try:
        key = VerifyKey(bytes.fromhex(source_agent))
        key.verify(digest, _decode_base64url(signature))
        return True
    except (BadSignatureError, ValueError, binascii.Error):
        return False
