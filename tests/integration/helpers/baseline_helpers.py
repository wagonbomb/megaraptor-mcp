"""Helper functions for baseline operations in forensic validation testing.

Baselines are known-good artifact collection results used to validate that
artifact collection produces consistent, correct output. These helpers support:
- Deterministic hash computation for validation
- Loading baseline fixtures from disk
- Accessing baseline metadata and expected hashes
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


# Path to baseline fixtures directory
BASELINES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "baselines"


def compute_forensic_hash(data: Any, algorithm: str = 'sha256') -> str:
    """Compute deterministic hash of data for forensic validation.

    Uses normalized JSON serialization (sorted keys, consistent separators)
    to ensure semantically equal data produces identical hashes regardless
    of key order or formatting.

    Args:
        data: Any JSON-serializable data (dict, list, etc.)
        algorithm: Hash algorithm to use (default: 'sha256')

    Returns:
        Hex-encoded hash string

    Example:
        >>> compute_forensic_hash({'z': 1, 'a': 2})
        '8a8de823d5ed3e12746a62ef169bcf372be0ca44f0a1236abc35df05d96928e1'
        >>> compute_forensic_hash({'a': 2, 'z': 1})  # Same hash despite different order
        '8a8de823d5ed3e12746a62ef169bcf372be0ca44f0a1236abc35df05d96928e1'
    """
    # Normalize JSON: sort keys, consistent separators (no spaces)
    normalized_json = json.dumps(data, sort_keys=True, separators=(',', ':'))

    # Compute hash of normalized representation
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(normalized_json.encode('utf-8'))

    return hash_obj.hexdigest()


def load_baseline(artifact_name: str) -> Any:
    """Load baseline fixture for an artifact.

    Converts artifact name to filename using convention:
    - Linux.Sys.Users -> linux_sys_users.json
    - Generic.Client.Info -> generic_client_info.json

    Args:
        artifact_name: Velociraptor artifact name (e.g., 'Linux.Sys.Users')

    Returns:
        Parsed JSON data from baseline file

    Raises:
        FileNotFoundError: If baseline file doesn't exist
        json.JSONDecodeError: If baseline file contains invalid JSON
    """
    # Convert artifact name to filename: Linux.Sys.Users -> linux_sys_users.json
    filename = artifact_name.replace('.', '_').lower() + '.json'
    baseline_path = BASELINES_DIR / filename

    with open(baseline_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_baseline_metadata() -> Dict[str, Any]:
    """Load baseline metadata containing hashes and test conditions.

    Returns:
        Parsed metadata.json dictionary

    Raises:
        FileNotFoundError: If metadata.json doesn't exist
        json.JSONDecodeError: If metadata.json contains invalid JSON
    """
    metadata_path = BASELINES_DIR / 'metadata.json'

    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_baseline_hash(artifact_name: str) -> Optional[str]:
    """Get expected hash for an artifact baseline from metadata.

    Args:
        artifact_name: Velociraptor artifact name (e.g., 'Linux.Sys.Users')

    Returns:
        Expected SHA-256 hash string, or None if not yet computed

    Raises:
        KeyError: If artifact not found in metadata
    """
    metadata = load_baseline_metadata()

    if artifact_name not in metadata.get('baselines', {}):
        raise KeyError(f"Artifact '{artifact_name}' not found in baseline metadata")

    return metadata['baselines'][artifact_name].get('sha256')
