"""
PKI certificate management for Velociraptor deployments.

Generates and manages CA, server, and client certificates for mTLS.
"""

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PrivateFormat,
        NoEncryption,
    )
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


@dataclass
class CertificateBundle:
    """A bundle of related certificates and keys.

    Attributes:
        ca_cert: CA certificate PEM
        ca_key: CA private key PEM
        server_cert: Server certificate PEM
        server_key: Server private key PEM
        api_cert: API client certificate PEM
        api_key: API client private key PEM
        ca_fingerprint: SHA256 fingerprint of CA cert (for pinning)
    """
    ca_cert: str
    ca_key: str
    server_cert: str
    server_key: str
    api_cert: str
    api_key: str
    ca_fingerprint: str

    def to_dict(self, include_private_keys: bool = False) -> dict:
        """Convert to dictionary.

        Args:
            include_private_keys: Include private keys in output

        Returns:
            Dictionary representation
        """
        result = {
            "ca_cert": self.ca_cert,
            "server_cert": self.server_cert,
            "api_cert": self.api_cert,
            "ca_fingerprint": self.ca_fingerprint,
        }
        if include_private_keys:
            result["ca_key"] = self.ca_key
            result["server_key"] = self.server_key
            result["api_key"] = self.api_key
        return result


class CertificateManager:
    """Manages PKI certificates for Velociraptor deployments."""

    DEFAULT_KEY_SIZE = 4096
    DEFAULT_CA_VALIDITY_DAYS = 3650  # 10 years
    DEFAULT_CERT_VALIDITY_DAYS = 365  # 1 year
    RAPID_CERT_VALIDITY_DAYS = 7  # 1 week for rapid deployments

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the certificate manager.

        Args:
            storage_path: Path to store certificate bundles
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography package required for certificate management. "
                "Install with: pip install cryptography"
            )

        self.storage_path = storage_path or self._default_storage_path()

    @staticmethod
    def _default_storage_path() -> Path:
        """Get the default certificate storage path."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", "~"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return base.expanduser() / "megaraptor-mcp" / "certs"

    def _generate_private_key(self, key_size: int = None) -> rsa.RSAPrivateKey:
        """Generate an RSA private key."""
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size or self.DEFAULT_KEY_SIZE,
        )

    def _key_to_pem(self, key: rsa.RSAPrivateKey) -> str:
        """Convert private key to PEM string."""
        return key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        ).decode()

    def _cert_to_pem(self, cert: x509.Certificate) -> str:
        """Convert certificate to PEM string."""
        return cert.public_bytes(Encoding.PEM).decode()

    def _get_fingerprint(self, cert: x509.Certificate) -> str:
        """Get SHA256 fingerprint of certificate."""
        fingerprint = cert.fingerprint(hashes.SHA256())
        return fingerprint.hex().upper()

    def generate_ca(
        self,
        common_name: str = "Velociraptor CA",
        organization: str = "Megaraptor MCP",
        validity_days: int = None,
    ) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generate a CA certificate and key.

        Args:
            common_name: CA common name
            organization: Organization name
            validity_days: Certificate validity in days

        Returns:
            Tuple of (certificate, private_key)
        """
        validity_days = validity_days or self.DEFAULT_CA_VALIDITY_DAYS

        # Generate key
        key = self._generate_private_key()

        # Build certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=1),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        return cert, key

    def generate_server_cert(
        self,
        ca_cert: x509.Certificate,
        ca_key: rsa.RSAPrivateKey,
        common_name: str,
        san_dns: list[str] = None,
        san_ips: list[str] = None,
        validity_days: int = None,
    ) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generate a server certificate signed by the CA.

        Args:
            ca_cert: CA certificate
            ca_key: CA private key
            common_name: Server common name (hostname)
            san_dns: List of DNS SANs
            san_ips: List of IP SANs
            validity_days: Certificate validity in days

        Returns:
            Tuple of (certificate, private_key)
        """
        from ipaddress import ip_address

        validity_days = validity_days or self.DEFAULT_CERT_VALIDITY_DAYS

        # Generate key
        key = self._generate_private_key()

        # Build subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Build SANs
        san_list = []
        if san_dns:
            san_list.extend([x509.DNSName(dns) for dns in san_dns])
        if san_ips:
            san_list.extend([x509.IPAddress(ip_address(ip)) for ip in san_ips])
        if not san_list:
            san_list.append(x509.DNSName(common_name))

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        return cert, key

    def generate_client_cert(
        self,
        ca_cert: x509.Certificate,
        ca_key: rsa.RSAPrivateKey,
        common_name: str,
        validity_days: int = None,
    ) -> Tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generate a client certificate signed by the CA.

        Args:
            ca_cert: CA certificate
            ca_key: CA private key
            common_name: Client common name (e.g., "api_client")
            validity_days: Certificate validity in days

        Returns:
            Tuple of (certificate, private_key)
        """
        validity_days = validity_days or self.DEFAULT_CERT_VALIDITY_DAYS

        # Generate key
        key = self._generate_private_key()

        # Build subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        return cert, key

    def generate_bundle(
        self,
        server_hostname: str,
        san_dns: list[str] = None,
        san_ips: list[str] = None,
        ca_validity_days: int = None,
        cert_validity_days: int = None,
        rapid: bool = False,
    ) -> CertificateBundle:
        """Generate a complete certificate bundle for deployment.

        Args:
            server_hostname: Server hostname
            san_dns: Additional DNS SANs
            san_ips: IP addresses for SANs
            ca_validity_days: CA certificate validity
            cert_validity_days: Server/client cert validity
            rapid: Use short validity for rapid deployment

        Returns:
            Complete certificate bundle
        """
        if rapid:
            cert_validity_days = cert_validity_days or self.RAPID_CERT_VALIDITY_DAYS

        # Generate CA
        ca_cert, ca_key = self.generate_ca(
            validity_days=ca_validity_days,
        )

        # Prepare SANs
        all_dns = [server_hostname]
        if san_dns:
            all_dns.extend(san_dns)
        all_dns.append("localhost")  # Always include localhost

        all_ips = ["127.0.0.1"]
        if san_ips:
            all_ips.extend(san_ips)

        # Generate server cert
        server_cert, server_key = self.generate_server_cert(
            ca_cert=ca_cert,
            ca_key=ca_key,
            common_name=server_hostname,
            san_dns=all_dns,
            san_ips=all_ips,
            validity_days=cert_validity_days,
        )

        # Generate API client cert
        api_cert, api_key = self.generate_client_cert(
            ca_cert=ca_cert,
            ca_key=ca_key,
            common_name="megaraptor_api_client",
            validity_days=cert_validity_days,
        )

        return CertificateBundle(
            ca_cert=self._cert_to_pem(ca_cert),
            ca_key=self._key_to_pem(ca_key),
            server_cert=self._cert_to_pem(server_cert),
            server_key=self._key_to_pem(server_key),
            api_cert=self._cert_to_pem(api_cert),
            api_key=self._key_to_pem(api_key),
            ca_fingerprint=self._get_fingerprint(ca_cert),
        )

    def save_bundle(
        self,
        bundle: CertificateBundle,
        deployment_id: str,
    ) -> Path:
        """Save a certificate bundle to disk.

        Args:
            bundle: The certificate bundle
            deployment_id: Deployment identifier

        Returns:
            Path to the bundle directory
        """
        bundle_path = self.storage_path / deployment_id
        bundle_path.mkdir(parents=True, exist_ok=True)

        # Save each file
        (bundle_path / "ca.crt").write_text(bundle.ca_cert)
        (bundle_path / "ca.key").write_text(bundle.ca_key)
        (bundle_path / "server.crt").write_text(bundle.server_cert)
        (bundle_path / "server.key").write_text(bundle.server_key)
        (bundle_path / "api_client.crt").write_text(bundle.api_cert)
        (bundle_path / "api_client.key").write_text(bundle.api_key)

        # Set restrictive permissions on private keys
        if os.name != "nt":
            os.chmod(bundle_path / "ca.key", 0o600)
            os.chmod(bundle_path / "server.key", 0o600)
            os.chmod(bundle_path / "api_client.key", 0o600)

        # Save fingerprint for reference
        (bundle_path / "ca.fingerprint").write_text(bundle.ca_fingerprint)

        return bundle_path

    def load_bundle(self, deployment_id: str) -> Optional[CertificateBundle]:
        """Load a certificate bundle from disk.

        Args:
            deployment_id: Deployment identifier

        Returns:
            The certificate bundle, or None if not found
        """
        bundle_path = self.storage_path / deployment_id

        if not bundle_path.exists():
            return None

        try:
            return CertificateBundle(
                ca_cert=(bundle_path / "ca.crt").read_text(),
                ca_key=(bundle_path / "ca.key").read_text(),
                server_cert=(bundle_path / "server.crt").read_text(),
                server_key=(bundle_path / "server.key").read_text(),
                api_cert=(bundle_path / "api_client.crt").read_text(),
                api_key=(bundle_path / "api_client.key").read_text(),
                ca_fingerprint=(bundle_path / "ca.fingerprint").read_text().strip(),
            )
        except FileNotFoundError:
            return None

    def delete_bundle(self, deployment_id: str) -> bool:
        """Delete a certificate bundle.

        Args:
            deployment_id: Deployment identifier

        Returns:
            True if deleted, False if not found
        """
        import shutil

        bundle_path = self.storage_path / deployment_id
        if not bundle_path.exists():
            return False

        shutil.rmtree(bundle_path)
        return True
