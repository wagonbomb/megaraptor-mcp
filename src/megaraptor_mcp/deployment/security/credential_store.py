"""
Encrypted credential storage for deployment secrets.

Uses AES-256-GCM for encryption with key derivation from a master password
or machine-specific key file.
"""

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


@dataclass
class StoredCredential:
    """A stored credential with metadata.

    Attributes:
        id: Unique credential identifier
        name: Human-readable name
        credential_type: Type of credential (api_key, password, certificate)
        created_at: When the credential was created
        expires_at: When the credential expires (None = never)
        deployment_id: Associated deployment ID
        data: The credential data (encrypted at rest)
    """
    id: str
    name: str
    credential_type: str
    created_at: str
    expires_at: Optional[str]
    deployment_id: Optional[str]
    data: dict[str, Any]

    def is_expired(self) -> bool:
        """Check if the credential has expired."""
        if not self.expires_at:
            return False
        expiry = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > expiry

    def to_dict(self) -> dict:
        """Convert to dictionary (excludes sensitive data)."""
        return {
            "id": self.id,
            "name": self.name,
            "credential_type": self.credential_type,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "deployment_id": self.deployment_id,
            "is_expired": self.is_expired(),
        }


class CredentialStore:
    """AES-256-GCM encrypted credential storage.

    Credentials are stored in a JSON file encrypted with a key derived from
    either a master password or a machine-specific key file.
    """

    SALT_SIZE = 16
    NONCE_SIZE = 12
    KEY_SIZE = 32  # 256 bits
    ITERATIONS = 600_000  # OWASP recommendation for PBKDF2-SHA256

    def __init__(self, store_path: Optional[Path] = None, key_file: Optional[Path] = None):
        """Initialize the credential store.

        Args:
            store_path: Path to the encrypted store file
            key_file: Path to the key file (created if not exists)
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography package required for credential storage. "
                "Install with: pip install cryptography"
            )

        self.store_path = store_path or self._default_store_path()
        self.key_file = key_file or self._default_key_file()
        self._encryption_key: Optional[bytes] = None

    @staticmethod
    def _default_store_path() -> Path:
        """Get the default credential store path."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", "~"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return base.expanduser() / "megaraptor-mcp" / "credentials.enc"

    @staticmethod
    def _default_key_file() -> Path:
        """Get the default key file path."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", "~"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return base.expanduser() / "megaraptor-mcp" / ".keyfile"

    def _ensure_key(self) -> bytes:
        """Ensure the encryption key exists and return it."""
        if self._encryption_key:
            return self._encryption_key

        self.key_file.parent.mkdir(parents=True, exist_ok=True)

        if self.key_file.exists():
            # Load existing key
            self._encryption_key = self.key_file.read_bytes()
        else:
            # Generate new random key
            self._encryption_key = secrets.token_bytes(self.KEY_SIZE)
            # Save with restrictive permissions
            self.key_file.write_bytes(self._encryption_key)
            if os.name != "nt":
                os.chmod(self.key_file, 0o600)

        return self._encryption_key

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        return kdf.derive(password.encode())

    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt data using AES-256-GCM."""
        key = self._ensure_key()
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt data using AES-256-GCM."""
        key = self._ensure_key()
        nonce = data[:self.NONCE_SIZE]
        ciphertext = data[self.NONCE_SIZE:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _load_store(self) -> dict[str, dict]:
        """Load and decrypt the credential store."""
        if not self.store_path.exists():
            return {}

        encrypted = self.store_path.read_bytes()
        if not encrypted:
            return {}

        try:
            decrypted = self._decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception:
            # Store may be corrupted or key changed
            return {}

    def _save_store(self, store: dict[str, dict]) -> None:
        """Encrypt and save the credential store."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(store).encode()
        encrypted = self._encrypt(data)
        self.store_path.write_bytes(encrypted)
        if os.name != "nt":
            os.chmod(self.store_path, 0o600)

    def store(self, credential: StoredCredential) -> str:
        """Store a credential.

        Args:
            credential: The credential to store

        Returns:
            The credential ID
        """
        store = self._load_store()
        store[credential.id] = asdict(credential)
        self._save_store(store)
        return credential.id

    def get(self, credential_id: str) -> Optional[StoredCredential]:
        """Retrieve a credential by ID.

        Args:
            credential_id: The credential ID

        Returns:
            The credential, or None if not found
        """
        store = self._load_store()
        data = store.get(credential_id)
        if not data:
            return None
        return StoredCredential(**data)

    def delete(self, credential_id: str) -> bool:
        """Delete a credential.

        Args:
            credential_id: The credential ID

        Returns:
            True if deleted, False if not found
        """
        store = self._load_store()
        if credential_id not in store:
            return False
        del store[credential_id]
        self._save_store(store)
        return True

    def list_credentials(
        self,
        deployment_id: Optional[str] = None,
        include_expired: bool = False,
    ) -> list[StoredCredential]:
        """List stored credentials.

        Args:
            deployment_id: Filter by deployment ID
            include_expired: Include expired credentials

        Returns:
            List of credentials (without sensitive data in data field)
        """
        store = self._load_store()
        credentials = []

        for data in store.values():
            cred = StoredCredential(**data)
            if deployment_id and cred.deployment_id != deployment_id:
                continue
            if not include_expired and cred.is_expired():
                continue
            # Return credential info without sensitive data
            cred.data = {"_redacted": True}
            credentials.append(cred)

        return credentials

    def cleanup_expired(self) -> int:
        """Remove all expired credentials.

        Returns:
            Number of credentials removed
        """
        store = self._load_store()
        initial_count = len(store)

        store = {
            k: v for k, v in store.items()
            if not StoredCredential(**v).is_expired()
        }

        self._save_store(store)
        return initial_count - len(store)

    def clear_deployment(self, deployment_id: str) -> int:
        """Remove all credentials for a deployment.

        Args:
            deployment_id: The deployment ID

        Returns:
            Number of credentials removed
        """
        store = self._load_store()
        initial_count = len(store)

        store = {
            k: v for k, v in store.items()
            if v.get("deployment_id") != deployment_id
        }

        self._save_store(store)
        return initial_count - len(store)


def generate_credential_id() -> str:
    """Generate a unique credential ID."""
    return f"cred_{secrets.token_hex(8)}"


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def generate_password(length: int = 24) -> str:
    """Generate a secure random password.

    Args:
        length: Password length (default 24)

    Returns:
        A cryptographically secure random password
    """
    # Use a mix of letters, digits, and safe special characters
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))
