"""
SnehDistribuors Desktop Sync Agent - Security & Credential Storage Module

Sensitive configuration fields (passwords, JWT tokens) never reach agent_config.json
in plaintext. Storage preference:
  1. OS credential vault via `keyring` (Windows Credential Manager / DPAPI,
     macOS Keychain, Secret Service). The config file only holds a "keyring:<account>"
     reference, so a copied or committed config file contains no secret at all.
  2. Machine-bound Fernet encryption ("enc:fn:...") when no vault is available.
  3. Otherwise the secret is NOT persisted (the user must log in again) - there is
     no weak or plaintext fallback.
"""

import os
import sys
import base64
import hashlib
import platform
import uuid
import logging
from typing import Optional

logger = logging.getLogger("SyncSecurity")

# Constant application salt used for key derivation
_APP_SALT = b"SnehDistribuors-Tally-Sync-SecureVault-Salt-v1"
_CIPHER_PREFIX = "enc:fn:"
_LEGACY_PREFIX = "enc:"
_KEYRING_PREFIX = "keyring:"
_KEYRING_SERVICE = "SnehDistribuorsSyncAgent"

# Cached Fernet instance
_fernet_instance = None
_crypto_available = None


def _get_keyring():
    """Returns the keyring module if a real OS credential vault backend is available, else None."""
    try:
        import keyring
        backend = keyring.get_keyring()
        # The 'fail' and 'null' backends mean no usable vault (e.g. headless Linux without Secret Service)
        if type(backend).__module__ in ("keyring.backends.fail", "keyring.backends.null"):
            return None
        return keyring
    except Exception:
        return None


def is_keyring_reference(value: Optional[str]) -> bool:
    """Returns True if the stored config value points at an OS credential vault entry."""
    return isinstance(value, str) and value.startswith(_KEYRING_PREFIX)


def store_secret(account: str, plain_text: Optional[str]) -> str:
    """
    Persists a secret and returns the value that is safe to write into agent_config.json:
    a "keyring:<account>" reference, or Fernet ciphertext when no vault is available.
    An empty value removes any existing vault entry.
    """
    kr = _get_keyring()
    if not plain_text:
        if kr is not None:
            try:
                kr.delete_password(_KEYRING_SERVICE, account)
            except Exception:
                pass
        return ""

    if kr is not None:
        try:
            kr.set_password(_KEYRING_SERVICE, account, plain_text)
            return f"{_KEYRING_PREFIX}{account}"
        except Exception as e:
            logger.warning(f"⚠️ OS credential vault unavailable ({e}). Falling back to machine-bound encryption.")

    return encrypt_secret(plain_text)


def load_secret(stored: Optional[str]) -> str:
    """Resolves a value read from agent_config.json (vault reference, ciphertext or legacy plaintext)."""
    if not stored or not isinstance(stored, str):
        return ""
    if is_keyring_reference(stored):
        kr = _get_keyring()
        if kr is None:
            logger.warning("⚠️ Credential is stored in the OS vault but no vault backend is available.")
            return ""
        try:
            return kr.get_password(_KEYRING_SERVICE, stored[len(_KEYRING_PREFIX):]) or ""
        except Exception as e:
            logger.warning(f"⚠️ Failed to read credential from OS vault: {e}")
            return ""
    return decrypt_secret(stored)


def needs_storage_upgrade(stored: Optional[str]) -> bool:
    """True if a stored value is plaintext, or is file-encrypted while an OS vault is now available."""
    if not stored or not isinstance(stored, str) or is_keyring_reference(stored):
        return False
    if not is_encrypted(stored):
        return True
    return _get_keyring() is not None


def _get_machine_identifier() -> bytes:
    """
    Constructs a machine-specific, user-account-specific identifier.
    Bound to the local hardware and OS user profile so stolen config files
    cannot be decrypted on a different machine or user profile.
    """
    parts = []

    # 1. Windows MachineGuid from Registry (if on Windows)
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if guid:
                parts.append(str(guid))
        except Exception:
            pass

    # 2. Network Node / MAC Address
    try:
        parts.append(str(uuid.getnode()))
    except Exception:
        pass

    # 3. Hostname & OS Architecture
    try:
        parts.append(platform.node() or "default-node")
        parts.append(platform.machine() or "default-arch")
    except Exception:
        pass

    # 4. User Profile / Username
    username = (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or "default-user"
    )
    parts.append(username)

    raw_id = "|".join(parts).encode("utf-8")
    return raw_id


def _get_fernet():
    """Returns a cached Fernet instance with a machine-bound derived key."""
    global _fernet_instance, _crypto_available
    if _crypto_available is False:
        return None

    if _fernet_instance is not None:
        return _fernet_instance

    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        machine_id = _get_machine_identifier()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_APP_SALT,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(machine_id))
        _fernet_instance = Fernet(derived_key)
        _crypto_available = True
        return _fernet_instance
    except ImportError:
        logger.warning(
            "⚠️ 'cryptography' library not installed. File-based credential encryption is disabled; "
            "install it via 'pip install cryptography'."
        )
        _crypto_available = False
        return None
    except Exception as e:
        logger.error(f"❌ Failed to initialize cryptography engine: {e}")
        _crypto_available = False
        return None


def _fallback_cipher(data: bytes, key: bytes) -> bytes:
    """Legacy XOR-stream cipher. Decrypt-only: lets old 'enc:fb:' configs be read once and migrated."""
    out = bytearray(len(data))
    block_index = 0
    stream = b""
    stream_pos = 0

    for i in range(len(data)):
        if stream_pos >= len(stream):
            # Generate next 32-byte stream block
            stream = hashlib.sha256(key + block_index.to_bytes(4, "big")).digest()
            stream_pos = 0
            block_index += 1
        out[i] = data[i] ^ stream[stream_pos]
        stream_pos += 1

    return bytes(out)


def is_encrypted(value: Optional[str]) -> bool:
    """Returns True if the string is already encrypted."""
    if not value or not isinstance(value, str):
        return False
    return value.startswith(_CIPHER_PREFIX) or value.startswith(_LEGACY_PREFIX)


def encrypt_secret(plain_text: Optional[str]) -> str:
    """
    Encrypts a sensitive string (password or token) using machine-bound Fernet encryption.
    Returns string prefixed with 'enc:fn:'. If the value is already encrypted, returns it unchanged.
    If Fernet is unavailable, returns "" so the secret is never written to disk in plaintext
    or under the legacy XOR cipher (which is only kept below for decrypting old configs).
    """
    if not plain_text or not isinstance(plain_text, str):
        return ""

    # Already encrypted: avoid double-encryption
    if is_encrypted(plain_text):
        return plain_text

    fernet = _get_fernet()
    if fernet is not None:
        try:
            token = fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")
            return f"{_CIPHER_PREFIX}{token}"
        except Exception as e:
            logger.error(f"❌ Fernet encryption failed: {e}")

    logger.error(
        "❌ No secure credential storage available (install 'keyring' and 'cryptography'). "
        "Credential will NOT be saved; you will need to log in again after restart."
    )
    return ""


def decrypt_secret(cipher_text: Optional[str]) -> str:
    """
    Decrypts an encrypted string into plaintext.
    - If empty or None: returns "".
    - If string is unencrypted (legacy config or manual edit): returns string as-is.
    - If encrypted with Fernet or fallback cipher: decrypts using machine-derived key.
    - If decryption fails (e.g. copied to another machine): logs warning and returns "".
    """
    if not cipher_text or not isinstance(cipher_text, str):
        return ""

    # Not encrypted: return as-is for backward compatibility and manual config entry
    if not is_encrypted(cipher_text):
        return cipher_text

    # Case 1: Fernet encrypted ("enc:fn:..." or legacy "enc:...")
    if cipher_text.startswith(_CIPHER_PREFIX):
        raw_token = cipher_text[len(_CIPHER_PREFIX):]
        fernet = _get_fernet()
        if fernet is not None:
            try:
                decrypted = fernet.decrypt(raw_token.encode("utf-8")).decode("utf-8")
                return decrypted
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to decrypt secret using Fernet (possibly created on another machine or user account): {e}"
                )
                return ""
        else:
            logger.warning("⚠️ Cannot decrypt Fernet token: 'cryptography' library is not available.")
            return ""

    # Case 2: Fallback cipher ("enc:fb:...")
    if cipher_text.startswith("enc:fb:"):
        raw_b64 = cipher_text[7:]
        try:
            key = hashlib.sha256(_get_machine_identifier() + _APP_SALT).digest()
            cipher_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
            plain_bytes = _fallback_cipher(cipher_bytes, key)
            return plain_bytes.decode("utf-8")
        except Exception as e:
            logger.warning(f"⚠️ Fallback decryption failed: {e}")
            return ""

    # Case 3: Generic "enc:..." without subprefix (try Fernet first, then fallback)
    if cipher_text.startswith(_LEGACY_PREFIX):
        raw = cipher_text[len(_LEGACY_PREFIX):]
        fernet = _get_fernet()
        if fernet is not None:
            try:
                return fernet.decrypt(raw.encode("utf-8")).decode("utf-8")
            except Exception:
                pass
        # Try fallback
        try:
            key = hashlib.sha256(_get_machine_identifier() + _APP_SALT).digest()
            cipher_bytes = base64.urlsafe_b64decode(raw.encode("utf-8"))
            return _fallback_cipher(cipher_bytes, key).decode("utf-8")
        except Exception:
            pass

        logger.warning("⚠️ Unrecognized or invalid encrypted secret format.")
        return ""

    return cipher_text
