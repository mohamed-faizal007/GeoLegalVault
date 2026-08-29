"""SHA-256 fingerprinting (Plan Part 13).

Chosen for the avalanche effect (a 1-byte change produces a completely
different digest) and because a 32-byte hash fits `bytes32` on-chain
(Phase 5). Hashing happens on the exact bytes written to storage at upload,
and again on the exact bytes read back at verify (Phase 7).
"""

import hashlib

_CHUNK_SIZE = 1024 * 1024  # 1 MiB — bounds each hashlib.update() call


def sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    view = memoryview(data)
    for offset in range(0, len(view), _CHUNK_SIZE):
        digest.update(view[offset : offset + _CHUNK_SIZE])
    return digest.hexdigest()
