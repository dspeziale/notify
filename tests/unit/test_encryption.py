"""Unit tests for AES-256-GCM encryption service and key rotation."""

import pytest
from app.core.encryption import EncryptionService
from app.core.exceptions import CryptoException


def test_encryption_and_decryption(master_key):
    service = EncryptionService(active_version="v1", key_ring={"v1": master_key})
    plaintext = "super-secret-telegram-bot-token:123456789:ABCDEF"

    encrypted = service.encrypt(plaintext)
    assert encrypted.startswith("v1:")
    assert plaintext not in encrypted

    decrypted = service.decrypt(encrypted)
    assert decrypted == plaintext


def test_encryption_tamper_detection(master_key):
    service = EncryptionService(active_version="v1", key_ring={"v1": master_key})
    plaintext = "sensitive-oauth-refresh-token"
    encrypted = service.encrypt(plaintext)

    parts = encrypted.split(":")
    # Tamper with ciphertext
    tampered_ciphertext = parts[2][:-4] + "AAAA"
    tampered_payload = f"{parts[0]}:{parts[1]}:{tampered_ciphertext}"

    with pytest.raises(CryptoException):
        service.decrypt(tampered_payload)


def test_key_rotation_and_re_encryption(master_key, secondary_key):
    # Key ring with v1 and v2
    key_ring = {"v1": master_key, "v2": secondary_key}
    service = EncryptionService(active_version="v2", key_ring=key_ring)

    # Payload encrypted with old v1 key
    old_service = EncryptionService(active_version="v1", key_ring={"v1": master_key})
    plaintext = "critical_production_secret"
    payload_v1 = old_service.encrypt(plaintext)
    assert payload_v1.startswith("v1:")

    # Service with v2 can still decrypt v1
    assert service.decrypt(payload_v1) == plaintext

    # Re-encrypt if needed to v2
    new_payload, was_rotated = service.re_encrypt_if_needed(payload_v1, target_version="v2")
    assert was_rotated is True
    assert new_payload.startswith("v2:")
    assert service.decrypt(new_payload) == plaintext

    # Calling re-encrypt on v2 again does nothing
    unchanged_payload, was_rotated2 = service.re_encrypt_if_needed(new_payload, target_version="v2")
    assert was_rotated2 is False
    assert unchanged_payload == new_payload
