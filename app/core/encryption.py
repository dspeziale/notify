"""AES-256-GCM encryption service with versioned key ring and rotation support."""

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings
from app.core.exceptions import CryptoException


class EncryptionService:
    """Manages symmetric encryption and decryption using AES-256-GCM."""

    def __init__(
        self,
        active_version: str | None = None,
        key_ring: dict[str, str] | None = None,
    ):
        self.active_version = active_version or settings.ACTIVE_KEY_VERSION
        raw_ring = key_ring or settings.get_key_ring()
        self._key_ring: dict[str, bytes] = {}

        for version, b64_key in raw_ring.items():
            try:
                decoded = base64.urlsafe_b64decode(b64_key)
                if len(decoded) != 32:
                    raise ValueError(f"Key for version {version} must be exactly 32 bytes (got {len(decoded)})")
                self._key_ring[version] = decoded
            except Exception as e:
                raise CryptoException(f"Failed to load encryption key for version {version}: {e}")

        if self.active_version not in self._key_ring:
            raise CryptoException(
                f"Active key version '{self.active_version}' is not present in key ring"
            )

    def encrypt(self, plaintext: str, version: str | None = None) -> str:
        """Encrypts plaintext using AES-256-GCM.

        Output format: {version}:{nonce_b64}:{ciphertext_b64}
        (Note: cryptography's AESGCM.encrypt appends the 16-byte authentication tag to the ciphertext).
        """
        if plaintext is None:
            return ""

        ver = version or self.active_version
        key = self._key_ring.get(ver)
        if not key:
            raise CryptoException(f"Encryption key version '{ver}' not found in key ring")

        try:
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)  # 96-bit nonce standard for GCM
            plaintext_bytes = plaintext.encode("utf-8")
            ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)

            nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")
            ciphertext_b64 = base64.urlsafe_b64encode(ciphertext).decode("ascii")

            return f"{ver}:{nonce_b64}:{ciphertext_b64}"
        except Exception as e:
            raise CryptoException(f"Encryption failed: {e}")

    def decrypt(self, encrypted_payload: str) -> str:
        """Decrypts a payload in format {version}:{nonce_b64}:{ciphertext_b64}."""
        if not encrypted_payload:
            return ""

        parts = encrypted_payload.split(":")
        if len(parts) != 3:
            raise CryptoException("Malformed encrypted payload format")

        version, nonce_b64, ciphertext_b64 = parts
        key = self._key_ring.get(version)
        if not key:
            raise CryptoException(f"Key version '{version}' not found for decryption")

        try:
            nonce = base64.urlsafe_b64decode(nonce_b64)
            ciphertext = base64.urlsafe_b64decode(ciphertext_b64)
            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise CryptoException(f"Decryption failed or authentication tag mismatch: {e}")

    def get_payload_version(self, encrypted_payload: str) -> str | None:
        """Extracts the key version tag from an encrypted payload."""
        if not encrypted_payload:
            return None
        parts = encrypted_payload.split(":")
        return parts[0] if len(parts) == 3 else None

    def re_encrypt_if_needed(self, encrypted_payload: str, target_version: str | None = None) -> tuple[str, bool]:
        """Re-encrypts payload if its version differs from the target version.

        Returns: (payload, was_rotated)
        """
        target = target_version or self.active_version
        current_version = self.get_payload_version(encrypted_payload)

        if current_version == target:
            return encrypted_payload, False

        decrypted = self.decrypt(encrypted_payload)
        new_payload = self.encrypt(decrypted, version=target)
        return new_payload, True


# Global default instance
encryption_service = EncryptionService()
