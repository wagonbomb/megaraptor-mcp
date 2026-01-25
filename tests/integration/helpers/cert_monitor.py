"""Certificate expiration monitoring for test infrastructure.

Checks certificate expiration dates to prevent cryptic x509 errors
when test infrastructure certificates expire.
"""

import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# cryptography is optional - only needed for cert monitoring
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


def get_cert_expiry_days(cert_pem: str) -> int:
    """Get number of days until certificate expires.

    Args:
        cert_pem: PEM-encoded certificate string

    Returns:
        Number of days until expiration (negative if already expired)

    Raises:
        ImportError: If cryptography library not installed
        ValueError: If certificate cannot be parsed
    """
    if not HAS_CRYPTOGRAPHY:
        raise ImportError(
            "cryptography library required for certificate monitoring. "
            "Install with: pip install cryptography"
        )

    try:
        cert = x509.load_pem_x509_certificate(
            cert_pem.encode(),
            default_backend()
        )
        expiry = cert.not_valid_after_utc
        now = datetime.now(expiry.tzinfo)
        delta = expiry - now
        return delta.days
    except Exception as e:
        raise ValueError(f"Failed to parse certificate: {e}")


def check_cert_expiration(
    config_path: str,
    warn_days: int = 30,
    error_days: int = 7,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Check certificate expiration from Velociraptor config file.

    Reads the certificate from a Velociraptor server or API client config
    and checks if it's close to expiration.

    Args:
        config_path: Path to Velociraptor config YAML file
        warn_days: Days before expiration to issue warning (default 30)
        error_days: Days before expiration to issue error (default 7)

    Returns:
        Tuple of (is_valid, days_remaining, message)
        - is_valid: True if certificate is valid for more than error_days
        - days_remaining: Number of days until expiration (None if check failed)
        - message: Warning or error message (None if OK)

    Note:
        Issues Python warning if certificate expires within warn_days.
    """
    if not HAS_CRYPTOGRAPHY:
        # Can't check without cryptography library
        return True, None, "Certificate check skipped (cryptography not installed)"

    config_file = Path(config_path)
    if not config_file.exists():
        return True, None, f"Config file not found: {config_path}"

    try:
        import yaml

        with open(config_file) as f:
            config = yaml.safe_load(f)

        # Try different config structures
        cert_pem = None

        # API client config format
        if "ca_certificate" in config:
            cert_pem = config.get("ca_certificate")
        # Server config format
        elif "Frontend" in config:
            cert_pem = config.get("Frontend", {}).get("certificate")
        # Client config format
        elif "Client" in config:
            cert_pem = config.get("Client", {}).get("ca_certificate")

        if not cert_pem:
            return True, None, "No certificate found in config"

        days_left = get_cert_expiry_days(cert_pem)

        if days_left < 0:
            msg = (
                f"CERTIFICATE EXPIRED {abs(days_left)} days ago! "
                f"Regenerate with: ./scripts/test-lab.sh generate-config"
            )
            return False, days_left, msg

        if days_left <= error_days:
            msg = (
                f"CERTIFICATE EXPIRES IN {days_left} DAYS! "
                f"Regenerate with: ./scripts/test-lab.sh generate-config"
            )
            return False, days_left, msg

        if days_left <= warn_days:
            msg = (
                f"Certificate expires in {days_left} days. "
                f"Consider regenerating with: ./scripts/test-lab.sh generate-config"
            )
            warnings.warn(msg, UserWarning)
            return True, days_left, msg

        return True, days_left, None

    except yaml.YAMLError as e:
        return True, None, f"Failed to parse config YAML: {e}"
    except Exception as e:
        return True, None, f"Certificate check failed: {e}"


def check_test_infrastructure_certs(
    fixtures_dir: str = "tests/fixtures",
) -> bool:
    """Check all test infrastructure certificates.

    Convenience function to check server and API client certificates.

    Args:
        fixtures_dir: Path to fixtures directory containing configs

    Returns:
        True if all certificates are valid
    """
    fixtures = Path(fixtures_dir)
    all_valid = True

    configs = [
        fixtures / "server.config.yaml",
        fixtures / "api_client.yaml",
    ]

    for config_path in configs:
        if config_path.exists():
            is_valid, days, msg = check_cert_expiration(str(config_path))
            if not is_valid:
                print(f"ERROR: {config_path.name}: {msg}")
                all_valid = False
            elif msg and days is not None:
                print(f"WARNING: {config_path.name}: {msg}")

    return all_valid
