"""Tests for PKI certificate management."""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Skip all tests if cryptography is not available
pytest.importorskip("cryptography")

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from megaraptor_mcp.deployment.security import (
    CertificateManager,
    CertificateBundle,
)


@pytest.mark.unit
class TestCertificateBundle:
    """Tests for CertificateBundle dataclass."""

    def test_to_dict_without_private_keys(self):
        """Test converting bundle to dict without private keys."""
        bundle = CertificateBundle(
            ca_cert="CA_CERT",
            ca_key="CA_KEY",
            server_cert="SERVER_CERT",
            server_key="SERVER_KEY",
            api_cert="API_CERT",
            api_key="API_KEY",
            ca_fingerprint="ABC123",
        )

        result = bundle.to_dict(include_private_keys=False)

        assert result["ca_cert"] == "CA_CERT"
        assert result["server_cert"] == "SERVER_CERT"
        assert result["api_cert"] == "API_CERT"
        assert result["ca_fingerprint"] == "ABC123"
        assert "ca_key" not in result
        assert "server_key" not in result
        assert "api_key" not in result

    def test_to_dict_with_private_keys(self):
        """Test converting bundle to dict with private keys included."""
        bundle = CertificateBundle(
            ca_cert="CA_CERT",
            ca_key="CA_KEY",
            server_cert="SERVER_CERT",
            server_key="SERVER_KEY",
            api_cert="API_CERT",
            api_key="API_KEY",
            ca_fingerprint="ABC123",
        )

        result = bundle.to_dict(include_private_keys=True)

        assert result["ca_key"] == "CA_KEY"
        assert result["server_key"] == "SERVER_KEY"
        assert result["api_key"] == "API_KEY"


@pytest.mark.unit
class TestCertificateManager:
    """Tests for CertificateManager class."""

    def test_init_with_custom_path(self, temp_certs_dir):
        """Test initializing with a custom storage path."""
        manager = CertificateManager(storage_path=temp_certs_dir)
        assert manager.storage_path == temp_certs_dir

    def test_init_creates_default_path(self, tmp_path, monkeypatch):
        """Test that default storage path is determined correctly."""
        # Note: conftest.py sets XDG_DATA_HOME to tmp_path / "data"
        # We need to check against what the fixture actually sets
        data_home = tmp_path / "data"
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

        manager = CertificateManager()

        expected = data_home / "megaraptor-mcp" / "certs"
        assert manager.storage_path == expected

    def test_generate_ca(self, temp_certs_dir):
        """Test CA certificate generation."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        cert, key = manager.generate_ca(
            common_name="Test CA",
            organization="Test Org",
        )

        # Verify certificate attributes
        assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "Test CA"
        assert cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value == "Test Org"

        # Verify CA extension
        basic_constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert basic_constraints.value.ca is True

        # Verify validity period
        now = datetime.now(timezone.utc)
        assert cert.not_valid_before_utc <= now
        assert cert.not_valid_after_utc > now

    def test_generate_ca_custom_validity(self, temp_certs_dir):
        """Test CA generation with custom validity period."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        cert, key = manager.generate_ca(validity_days=365)

        # Check validity is approximately 1 year
        validity = cert.not_valid_after_utc - cert.not_valid_before_utc
        assert 364 <= validity.days <= 366

    def test_generate_server_cert(self, temp_certs_dir):
        """Test server certificate generation."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        # First generate CA
        ca_cert, ca_key = manager.generate_ca()

        # Generate server cert
        server_cert, server_key = manager.generate_server_cert(
            ca_cert=ca_cert,
            ca_key=ca_key,
            common_name="server.test.local",
            san_dns=["server.test.local", "localhost"],
            san_ips=["127.0.0.1", "192.168.1.100"],
        )

        # Verify subject
        cn = server_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        assert cn == "server.test.local"

        # Verify issuer matches CA
        assert server_cert.issuer == ca_cert.subject

        # Verify not a CA
        basic_constraints = server_cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert basic_constraints.value.ca is False

        # Verify extended key usage
        eku = server_cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert ExtendedKeyUsageOID.SERVER_AUTH in eku.value

        # Verify SANs
        san = server_cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san.value.get_values_for_type(x509.DNSName)
        assert "server.test.local" in dns_names
        assert "localhost" in dns_names

    def test_generate_client_cert(self, temp_certs_dir):
        """Test client certificate generation."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        # First generate CA
        ca_cert, ca_key = manager.generate_ca()

        # Generate client cert
        client_cert, client_key = manager.generate_client_cert(
            ca_cert=ca_cert,
            ca_key=ca_key,
            common_name="api_client",
        )

        # Verify subject
        cn = client_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        assert cn == "api_client"

        # Verify issuer matches CA
        assert client_cert.issuer == ca_cert.subject

        # Verify not a CA
        basic_constraints = client_cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert basic_constraints.value.ca is False

        # Verify extended key usage
        eku = client_cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert ExtendedKeyUsageOID.CLIENT_AUTH in eku.value

    def test_generate_bundle(self, temp_certs_dir):
        """Test complete bundle generation."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(
            server_hostname="test.velociraptor.local",
            san_dns=["alt.velociraptor.local"],
            san_ips=["10.0.0.1"],
        )

        # Verify all components are present
        assert bundle.ca_cert.startswith("-----BEGIN CERTIFICATE-----")
        assert bundle.ca_key.startswith("-----BEGIN PRIVATE KEY-----")
        assert bundle.server_cert.startswith("-----BEGIN CERTIFICATE-----")
        assert bundle.server_key.startswith("-----BEGIN PRIVATE KEY-----")
        assert bundle.api_cert.startswith("-----BEGIN CERTIFICATE-----")
        assert bundle.api_key.startswith("-----BEGIN PRIVATE KEY-----")

        # Verify fingerprint is hex format
        assert len(bundle.ca_fingerprint) == 64  # SHA256 = 32 bytes = 64 hex chars

    def test_generate_bundle_rapid_mode(self, temp_certs_dir):
        """Test bundle generation with rapid mode (short validity)."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(
            server_hostname="rapid.test.local",
            rapid=True,
        )

        # Parse server cert and check validity
        cert = x509.load_pem_x509_certificate(bundle.server_cert.encode())
        validity = cert.not_valid_after_utc - cert.not_valid_before_utc

        # Rapid mode should use 7 days
        assert validity.days == 7

    def test_save_and_load_bundle(self, temp_certs_dir):
        """Test saving and loading a certificate bundle."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        # Generate bundle
        original_bundle = manager.generate_bundle(
            server_hostname="save-load.test.local",
        )

        # Save bundle
        deployment_id = "test-deployment-001"
        bundle_path = manager.save_bundle(original_bundle, deployment_id)

        # Verify files were created
        assert (bundle_path / "ca.crt").exists()
        assert (bundle_path / "ca.key").exists()
        assert (bundle_path / "server.crt").exists()
        assert (bundle_path / "server.key").exists()
        assert (bundle_path / "api_client.crt").exists()
        assert (bundle_path / "api_client.key").exists()
        assert (bundle_path / "ca.fingerprint").exists()

        # Load bundle
        loaded_bundle = manager.load_bundle(deployment_id)

        # Verify contents match
        assert loaded_bundle is not None
        assert loaded_bundle.ca_cert == original_bundle.ca_cert
        assert loaded_bundle.ca_key == original_bundle.ca_key
        assert loaded_bundle.server_cert == original_bundle.server_cert
        assert loaded_bundle.server_key == original_bundle.server_key
        assert loaded_bundle.api_cert == original_bundle.api_cert
        assert loaded_bundle.api_key == original_bundle.api_key
        assert loaded_bundle.ca_fingerprint == original_bundle.ca_fingerprint

    def test_load_bundle_not_found(self, temp_certs_dir):
        """Test loading a non-existent bundle returns None."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        result = manager.load_bundle("nonexistent-deployment")

        assert result is None

    def test_delete_bundle(self, temp_certs_dir):
        """Test deleting a certificate bundle."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        # Generate and save bundle
        bundle = manager.generate_bundle(server_hostname="delete.test.local")
        deployment_id = "test-delete-001"
        bundle_path = manager.save_bundle(bundle, deployment_id)

        # Verify bundle exists
        assert bundle_path.exists()

        # Delete bundle
        result = manager.delete_bundle(deployment_id)

        # Verify deletion
        assert result is True
        assert not bundle_path.exists()

    def test_delete_bundle_not_found(self, temp_certs_dir):
        """Test deleting a non-existent bundle returns False."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        result = manager.delete_bundle("nonexistent")

        assert result is False

    @pytest.mark.skipif(os.name == "nt", reason="Unix file permissions only")
    def test_private_key_permissions(self, temp_certs_dir):
        """Test that private key files have restrictive permissions."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(server_hostname="perms.test.local")
        deployment_id = "test-perms-001"
        bundle_path = manager.save_bundle(bundle, deployment_id)

        # Check permissions on private key files
        for key_file in ["ca.key", "server.key", "api_client.key"]:
            file_path = bundle_path / key_file
            mode = file_path.stat().st_mode & 0o777
            assert mode == 0o600, f"{key_file} should have 0600 permissions"

    def test_key_to_pem_format(self, temp_certs_dir):
        """Test that generated keys are in PKCS8 PEM format."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(server_hostname="format.test.local")

        # Verify keys can be parsed as PKCS8
        for key_pem in [bundle.ca_key, bundle.server_key, bundle.api_key]:
            key = serialization.load_pem_private_key(key_pem.encode(), password=None)
            assert key is not None

    def test_cert_chain_validation(self, temp_certs_dir):
        """Test that server cert is properly signed by CA."""
        from cryptography.hazmat.primitives.asymmetric import padding

        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(server_hostname="chain.test.local")

        # Load certificates
        ca_cert = x509.load_pem_x509_certificate(bundle.ca_cert.encode())
        server_cert = x509.load_pem_x509_certificate(bundle.server_cert.encode())

        # Verify issuer matches CA subject
        assert server_cert.issuer == ca_cert.subject

        # Verify signature (using CA public key)
        ca_public_key = ca_cert.public_key()
        try:
            # Use PKCS1v15 padding and SHA256 for RSA signature verification
            ca_public_key.verify(
                server_cert.signature,
                server_cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                server_cert.signature_hash_algorithm,
            )
        except Exception as e:
            pytest.fail(f"Server cert signature verification failed: {e}")

    def test_localhost_always_in_sans(self, temp_certs_dir):
        """Test that localhost is always included in server SANs."""
        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(
            server_hostname="custom.test.local",
            san_dns=["other.test.local"],
        )

        cert = x509.load_pem_x509_certificate(bundle.server_cert.encode())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san.value.get_values_for_type(x509.DNSName)

        assert "localhost" in dns_names

    def test_loopback_always_in_sans(self, temp_certs_dir):
        """Test that 127.0.0.1 is always included in server SANs."""
        from ipaddress import ip_address

        manager = CertificateManager(storage_path=temp_certs_dir)

        bundle = manager.generate_bundle(
            server_hostname="custom.test.local",
            san_ips=["10.0.0.1"],
        )

        cert = x509.load_pem_x509_certificate(bundle.server_cert.encode())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        ip_addresses = san.value.get_values_for_type(x509.IPAddress)

        assert ip_address("127.0.0.1") in ip_addresses
