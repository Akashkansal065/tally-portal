"""AES-256-GCM encryption at rest for backups held on the server (WS-13).

File layout (all integers big endian):

    "MTBKENC1" | key_id length (1) | key_id | base nonce (8)
    then records:  final flag (1) | ciphertext length (4) | ciphertext
    each record holds up to SEGMENT_BYTES of plaintext; its nonce is base nonce || record number (4) and its
    associated data is the header || record number || final flag, so segments cannot be reordered, dropped
    from the end, or moved to another file.

Keys come from settings: BACKUP_ENCRYPTION_KEYS ("id:base64,id2:base64" with 32-byte keys) and
BACKUP_ENCRYPTION_ACTIVE_KEY_ID. New files use the active key; every key listed can still read, so rotation
is: add the new key, make it active, run the re-wrap, then drop the old key once `backup_crypto rewrap` reports
nothing left on it. A file without the magic is a plain backup (a ZIP starts with "PK").
"""
import base64
import os
import struct
from pathlib import Path
from typing import Dict, Iterator, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

MAGIC = b"MTBKENC1"
SEGMENT_BYTES = 4 * 1024 * 1024


class CryptoError(Exception):
    pass


def _keys() -> Dict[str, bytes]:
    keys: Dict[str, bytes] = {}
    for part in (settings.BACKUP_ENCRYPTION_KEYS or "").split(","):
        part = part.strip()
        if not part:
            continue
        key_id, _, encoded = part.partition(":")
        try:
            raw = base64.b64decode(encoded.strip(), validate=True)
        except Exception:
            raise CryptoError(f"Backup encryption key '{key_id}' is not valid base64.")
        if len(raw) != 32:
            raise CryptoError(f"Backup encryption key '{key_id}' must be 32 bytes (AES-256).")
        if not key_id or len(key_id) > 64:
            raise CryptoError("A backup encryption key needs an id of 1 to 64 characters.")
        keys[key_id.strip()] = raw
    return keys


def active_key_id() -> Optional[str]:
    """The key new backups are written with, or None when encryption at rest is not switched on."""
    wanted = (settings.BACKUP_ENCRYPTION_ACTIVE_KEY_ID or "").strip()
    if not wanted:
        return None
    if wanted not in _keys():
        raise CryptoError(f"BACKUP_ENCRYPTION_ACTIVE_KEY_ID '{wanted}' is not among BACKUP_ENCRYPTION_KEYS.")
    return wanted


def _key(key_id: str) -> bytes:
    keys = _keys()
    if key_id not in keys:
        raise CryptoError(f"This backup is encrypted with key '{key_id}', which this server no longer has.")
    return keys[key_id]


def generate_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def read_header(path: Path) -> Optional[str]:
    """The key id a file is encrypted with, or None when it is a plain file."""
    with open(path, "rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            return None
        n = f.read(1)
        if not n:
            raise CryptoError("The encrypted backup is cut off.")
        key_id = f.read(n[0]).decode("utf-8", "replace")
    return key_id


def _header(key_id: str, base_nonce: bytes) -> bytes:
    kid = key_id.encode()
    return MAGIC + bytes([len(kid)]) + kid + base_nonce


def _aad(header: bytes, counter: int, final: bool) -> bytes:
    return header + struct.pack(">IB", counter, 1 if final else 0)


def encrypt_file(src: Path, dst: Path, key_id: str) -> None:
    """Encrypt src into dst (written whole; the caller moves it into place)."""
    aes = AESGCM(_key(key_id))
    base = os.urandom(8)
    header = _header(key_id, base)
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fout.write(header)
        counter, current = 0, fin.read(SEGMENT_BYTES)
        while True:
            following = fin.read(SEGMENT_BYTES) if len(current) == SEGMENT_BYTES else b""
            final = not following
            ct = aes.encrypt(base + struct.pack(">I", counter), current, _aad(header, counter, final))
            fout.write(struct.pack(">BI", 1 if final else 0, len(ct)) + ct)
            if final:
                break
            counter, current = counter + 1, following
        fout.flush()
        os.fsync(fout.fileno())


def decrypt_stream(path: Path) -> Iterator[bytes]:
    """The plaintext of an encrypted file, segment by segment. Raises CryptoError for a wrong key, a damaged or a
    truncated file."""
    with open(path, "rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            raise CryptoError("This file is not an encrypted backup.")
        n = f.read(1)
        key_id = f.read(n[0]).decode("utf-8", "replace")
        base = f.read(8)
        header = _header(key_id, base)
        aes = AESGCM(_key(key_id))
        counter, saw_final = 0, False
        while True:
            head = f.read(5)
            if not head:
                break
            if saw_final or len(head) != 5:
                raise CryptoError("The encrypted backup has data after its end or is damaged.")
            final, length = struct.unpack(">BI", head)
            body = f.read(length)
            if len(body) != length:
                raise CryptoError("The encrypted backup is cut off.")
            try:
                yield aes.decrypt(base + struct.pack(">I", counter), body, _aad(header, counter, bool(final)))
            except InvalidTag:
                raise CryptoError("The encrypted backup failed its integrity check (wrong key or damaged file).")
            saw_final = bool(final)
            counter += 1
        if not saw_final:
            raise CryptoError("The encrypted backup is cut off.")


def decrypt_to(path: Path, dst: Path) -> None:
    with open(dst, "wb") as out:
        for block in decrypt_stream(path):
            out.write(block)


def rewrap_file(path: Path, new_key_id: str) -> bool:
    """Re-encrypt an encrypted file under new_key_id, in place and atomically. Returns False when it already is.
    Repeat-safe: the original stays until the new file has been written and read back."""
    if read_header(path) == new_key_id:
        return False
    plain = path.with_suffix(path.suffix + ".rewrap.plain")
    fresh = path.with_suffix(path.suffix + ".rewrap.new")
    try:
        decrypt_to(path, plain)
        encrypt_file(plain, fresh, new_key_id)
        for _ in decrypt_stream(fresh):         # read it back before it replaces anything
            pass
        os.replace(fresh, path)
    finally:
        for leftover in (plain, fresh):
            try:
                leftover.unlink()
            except FileNotFoundError:
                pass
    return True
