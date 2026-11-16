"""Content-addressed blob store for raw fetched pages: data/blobs/ab/cdef... (SHA-256 of the bytes).

The same bytes always land at the same path, so writes are idempotent and a frozen snapshot is
just a copy of this directory plus the page index.
"""

import hashlib
from pathlib import Path


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:]

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        path = self._path(digest)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # atomic: a crash never leaves a half-written blob
        return digest

    def get(self, digest: str) -> bytes:
        return self._path(digest).read_bytes()

    def has(self, digest: str) -> bool:
        return self._path(digest).exists()
