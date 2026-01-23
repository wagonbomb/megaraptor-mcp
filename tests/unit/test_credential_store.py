"""Tests for encrypted credential storage."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Skip all tests if cryptography is not available
pytest.importorskip("cryptography")

from megaraptor_mcp.deployment.security.credential_store import (
    StoredCredential,
    CredentialStore,
    generate_credential_id,
    generate_api_key,
    generate_password,
)


@pytest.mark.unit
class TestStoredCredential:
    """Tests for StoredCredential dataclass."""

    def test_is_expired_with_no_expiry(self):
        """Test credential without expiry is never expired."""
        cred = StoredCredential(
            id="cred_001",
            name="Test Credential",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
            deployment_id="deploy_001",
            data={"key": "value"},
        )

        assert cred.is_expired() is False

    def test_is_expired_with_future_expiry(self):
        """Test credential with future expiry is not expired."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        cred = StoredCredential(
            id="cred_001",
            name="Test Credential",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=future.isoformat(),
            deployment_id="deploy_001",
            data={"key": "value"},
        )

        assert cred.is_expired() is False

    def test_is_expired_with_past_expiry(self):
        """Test credential with past expiry is expired."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        cred = StoredCredential(
            id="cred_001",
            name="Test Credential",
            credential_type="api_key",
            created_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            expires_at=past.isoformat(),
            deployment_id="deploy_001",
            data={"key": "value"},
        )

        assert cred.is_expired() is True

    def test_to_dict_excludes_data(self):
        """Test to_dict includes metadata but excludes sensitive data."""
        cred = StoredCredential(
            id="cred_001",
            name="Test Credential",
            credential_type="api_key",
            created_at="2024-01-01T00:00:00+00:00",
            expires_at="2024-12-31T23:59:59+00:00",
            deployment_id="deploy_001",
            data={"secret": "sensitive_value"},
        )

        result = cred.to_dict()

        assert result["id"] == "cred_001"
        assert result["name"] == "Test Credential"
        assert result["credential_type"] == "api_key"
        assert result["deployment_id"] == "deploy_001"
        assert "is_expired" in result
        assert "data" not in result


@pytest.mark.unit
class TestCredentialStore:
    """Tests for CredentialStore class."""

    def test_init_with_custom_paths(self, temp_credentials_dir):
        """Test initializing with custom paths."""
        store_path = temp_credentials_dir / "custom.enc"
        key_file = temp_credentials_dir / "custom.key"

        store = CredentialStore(store_path=store_path, key_file=key_file)

        assert store.store_path == store_path
        assert store.key_file == key_file

    def test_init_creates_default_paths(self, tmp_path, monkeypatch):
        """Test that default paths are determined correctly."""
        # Note: conftest.py sets XDG_DATA_HOME to tmp_path / "data"
        data_home = tmp_path / "data"
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

        store = CredentialStore()

        expected_base = data_home / "megaraptor-mcp"
        assert store.store_path == expected_base / "credentials.enc"
        assert store.key_file == expected_base / ".keyfile"

    def test_store_and_get_credential(self, temp_credentials_dir):
        """Test storing and retrieving a credential."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        cred = StoredCredential(
            id="test_cred_001",
            name="Test API Key",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
            deployment_id="deploy_001",
            data={"api_key": "secret_key_12345"},
        )

        # Store credential
        returned_id = store.store(cred)
        assert returned_id == "test_cred_001"

        # Retrieve credential
        retrieved = store.get("test_cred_001")

        assert retrieved is not None
        assert retrieved.id == cred.id
        assert retrieved.name == cred.name
        assert retrieved.data["api_key"] == "secret_key_12345"

    def test_get_nonexistent_credential(self, temp_credentials_dir):
        """Test getting a non-existent credential returns None."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        result = store.get("nonexistent")

        assert result is None

    def test_delete_credential(self, temp_credentials_dir):
        """Test deleting a credential."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        cred = StoredCredential(
            id="to_delete",
            name="Delete Me",
            credential_type="password",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
            deployment_id=None,
            data={"password": "secret"},
        )

        store.store(cred)

        # Verify it exists
        assert store.get("to_delete") is not None

        # Delete it
        result = store.delete("to_delete")

        assert result is True
        assert store.get("to_delete") is None

    def test_delete_nonexistent_credential(self, temp_credentials_dir):
        """Test deleting a non-existent credential returns False."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        result = store.delete("nonexistent")

        assert result is False

    def test_list_credentials(self, temp_credentials_dir):
        """Test listing all credentials."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        # Store multiple credentials
        for i in range(3):
            cred = StoredCredential(
                id=f"cred_{i}",
                name=f"Credential {i}",
                credential_type="api_key",
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at=None,
                deployment_id="deploy_001",
                data={"key": f"value_{i}"},
            )
            store.store(cred)

        # List credentials
        creds = store.list_credentials()

        assert len(creds) == 3
        # Verify sensitive data is redacted
        for cred in creds:
            assert cred.data == {"_redacted": True}

    def test_list_credentials_filter_by_deployment(self, temp_credentials_dir):
        """Test filtering credentials by deployment ID."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        # Store credentials for different deployments
        for deploy_id in ["deploy_A", "deploy_A", "deploy_B"]:
            cred = StoredCredential(
                id=generate_credential_id(),
                name="Test Cred",
                credential_type="api_key",
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at=None,
                deployment_id=deploy_id,
                data={"key": "value"},
            )
            store.store(cred)

        # Filter by deployment
        deploy_a_creds = store.list_credentials(deployment_id="deploy_A")
        deploy_b_creds = store.list_credentials(deployment_id="deploy_B")

        assert len(deploy_a_creds) == 2
        assert len(deploy_b_creds) == 1

    def test_list_credentials_excludes_expired(self, temp_credentials_dir):
        """Test that expired credentials are excluded by default."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        # Store expired and valid credentials
        past = datetime.now(timezone.utc) - timedelta(days=1)
        future = datetime.now(timezone.utc) + timedelta(days=1)

        store.store(StoredCredential(
            id="expired",
            name="Expired",
            credential_type="api_key",
            created_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            expires_at=past.isoformat(),
            deployment_id=None,
            data={},
        ))

        store.store(StoredCredential(
            id="valid",
            name="Valid",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=future.isoformat(),
            deployment_id=None,
            data={},
        ))

        # List without expired
        creds = store.list_credentials(include_expired=False)
        assert len(creds) == 1
        assert creds[0].id == "valid"

        # List with expired
        creds_all = store.list_credentials(include_expired=True)
        assert len(creds_all) == 2

    def test_cleanup_expired(self, temp_credentials_dir):
        """Test removing expired credentials."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        past = datetime.now(timezone.utc) - timedelta(days=1)
        future = datetime.now(timezone.utc) + timedelta(days=1)

        # Store 2 expired and 1 valid
        store.store(StoredCredential(
            id="expired_1",
            name="Expired 1",
            credential_type="api_key",
            created_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            expires_at=past.isoformat(),
            deployment_id=None,
            data={},
        ))
        store.store(StoredCredential(
            id="expired_2",
            name="Expired 2",
            credential_type="api_key",
            created_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            expires_at=past.isoformat(),
            deployment_id=None,
            data={},
        ))
        store.store(StoredCredential(
            id="valid",
            name="Valid",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=future.isoformat(),
            deployment_id=None,
            data={},
        ))

        # Cleanup
        removed = store.cleanup_expired()

        assert removed == 2
        assert store.get("expired_1") is None
        assert store.get("expired_2") is None
        assert store.get("valid") is not None

    def test_clear_deployment(self, temp_credentials_dir):
        """Test removing all credentials for a deployment."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        # Store credentials for different deployments
        for i, deploy_id in enumerate(["deploy_A", "deploy_A", "deploy_B", None]):
            store.store(StoredCredential(
                id=f"cred_{i}",
                name=f"Cred {i}",
                credential_type="api_key",
                created_at=datetime.now(timezone.utc).isoformat(),
                expires_at=None,
                deployment_id=deploy_id,
                data={},
            ))

        # Clear deployment A
        removed = store.clear_deployment("deploy_A")

        assert removed == 2
        assert store.get("cred_0") is None
        assert store.get("cred_1") is None
        assert store.get("cred_2") is not None  # deploy_B
        assert store.get("cred_3") is not None  # None deployment

    def test_encryption_key_persistence(self, temp_credentials_dir):
        """Test that encryption key is persisted and reused."""
        key_file = temp_credentials_dir / "persist.key"

        # Create first store and save credential
        store1 = CredentialStore(
            store_path=temp_credentials_dir / "persist.enc",
            key_file=key_file,
        )

        cred = StoredCredential(
            id="persist_test",
            name="Persistence Test",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
            deployment_id=None,
            data={"secret": "persistent_secret"},
        )
        store1.store(cred)

        # Create second store with same paths
        store2 = CredentialStore(
            store_path=temp_credentials_dir / "persist.enc",
            key_file=key_file,
        )

        # Should be able to read the credential
        retrieved = store2.get("persist_test")

        assert retrieved is not None
        assert retrieved.data["secret"] == "persistent_secret"

    def test_corrupted_store_returns_empty(self, temp_credentials_dir):
        """Test that corrupted store is handled gracefully."""
        store_path = temp_credentials_dir / "corrupt.enc"

        # Write garbage to the store file
        store_path.write_bytes(b"not valid encrypted data")

        store = CredentialStore(
            store_path=store_path,
            key_file=temp_credentials_dir / "test.key",
        )

        # Should return empty list, not crash
        creds = store.list_credentials()

        assert creds == []

    @pytest.mark.skipif(os.name == "nt", reason="Unix file permissions only")
    def test_key_file_permissions(self, temp_credentials_dir):
        """Test that key file has restrictive permissions."""
        store = CredentialStore(
            store_path=temp_credentials_dir / "test.enc",
            key_file=temp_credentials_dir / "test.key",
        )

        # Trigger key creation by storing something
        store.store(StoredCredential(
            id="trigger",
            name="Trigger",
            credential_type="api_key",
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
            deployment_id=None,
            data={},
        ))

        mode = store.key_file.stat().st_mode & 0o777
        assert mode == 0o600


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for credential helper functions."""

    def test_generate_credential_id_format(self):
        """Test credential ID has expected format."""
        cred_id = generate_credential_id()

        assert cred_id.startswith("cred_")
        # 8 bytes = 16 hex characters
        assert len(cred_id) == 5 + 16  # "cred_" + 16 hex chars

    def test_generate_credential_id_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = [generate_credential_id() for _ in range(100)]

        assert len(ids) == len(set(ids))

    def test_generate_api_key_length(self):
        """Test API key has expected length."""
        api_key = generate_api_key()

        # token_urlsafe(32) produces ~43 characters
        assert len(api_key) >= 40

    def test_generate_api_key_uniqueness(self):
        """Test that generated API keys are unique."""
        keys = [generate_api_key() for _ in range(100)]

        assert len(keys) == len(set(keys))

    def test_generate_password_default_length(self):
        """Test password generation with default length."""
        password = generate_password()

        assert len(password) == 24

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        for length in [8, 16, 32, 64]:
            password = generate_password(length=length)
            assert len(password) == length

    def test_generate_password_character_set(self):
        """Test password contains expected character types."""
        # Generate many passwords and check character coverage
        all_chars = set()
        for _ in range(100):
            password = generate_password(length=50)
            all_chars.update(password)

        # Should contain various character types
        has_lower = any(c.islower() for c in all_chars)
        has_upper = any(c.isupper() for c in all_chars)
        has_digit = any(c.isdigit() for c in all_chars)
        has_special = any(c in "!@#$%^&*" for c in all_chars)

        assert has_lower
        assert has_upper
        assert has_digit
        assert has_special

    def test_generate_password_uniqueness(self):
        """Test that generated passwords are unique."""
        passwords = [generate_password() for _ in range(100)]

        assert len(passwords) == len(set(passwords))
