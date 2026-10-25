"""Tests for tenant credential encryption, decryption, and masking."""

from cryptography.fernet import Fernet

from apps.payments.encryption import (
    decrypt_credential,
    encrypt_credential,
    mask_credential,
)


class TestEncryptionUtilities:
    """Test suite for credential encryption and safe screen masking."""

    def test_encrypt_and_decrypt_roundtrip(self, settings):
        settings.TENANT_CREDENTIALS_KEY = "test_key_for_fernet_123456789012"
        plaintext = "CHASECK_TEST-secret_key_value_abcdef"

        ciphertext = encrypt_credential(plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) > 20

        decrypted = decrypt_credential(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_empty_returns_empty(self):
        assert encrypt_credential("") == ""
        assert encrypt_credential(None) == ""
        assert decrypt_credential("") == ""
        assert decrypt_credential(None) == ""

    def test_decrypt_invalid_ciphertext_returns_empty(self, settings):
        settings.TENANT_CREDENTIALS_KEY = "test_key_for_fernet_123456789012"
        corrupted = "not-a-valid-fernet-token"
        assert decrypt_credential(corrupted) == ""

    def test_standard_fernet_key_compatibility(self, settings):
        key = Fernet.generate_key().decode("ascii")
        settings.TENANT_CREDENTIALS_KEY = key

        token = encrypt_credential("CHAPUBK_TEST-998877")
        assert decrypt_credential(token) == "CHAPUBK_TEST-998877"

    def test_mask_credential_with_standard_prefix(self):
        assert mask_credential("CHAPUBK_TEST-abc123xyz789") == "CHAPUBK_TEST-****z789"
        assert mask_credential("CHASECK-secretvalue1234") == "CHASECK-****1234"

    def test_mask_credential_short_or_empty(self):
        assert mask_credential("") == ""
        assert mask_credential("12") == "****"
        assert mask_credential("abcdefgh") == "****efgh"
