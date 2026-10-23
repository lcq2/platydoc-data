# SPDX-License-Identifier: GPL-2.0-only
import gzip
import io

def _gzip(data: bytes) -> bytes:
    compressed = gzip.compress(data, compresslevel=9, mtime=0)
    # Python 3.11/3.12 may expose zlib's platform-specific OS byte for mtime=0.
    # Fix that harmless metadata byte for the same framing on every platform.
    return compressed[:9] + b"\xff" + compressed[10:]
