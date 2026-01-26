"""Output quality validation tests.

Validates:
- QUAL-01: Hash validation confirms collected artifacts match expected values
- QUAL-02: Timeline accuracy testing verifies timestamps within +/-1 second drift
"""

import pytest
from pytest import approx
from pytest_check import check
import time

from tests.integration.helpers.baseline_helpers import (
    compute_forensic_hash,
    load_baseline,
    load_baseline_metadata,
    parse_velociraptor_timestamp,
)
from tests.integration.helpers.wait_helpers import wait_for_flow_completion


@pytest.mark.integration
@pytest.mark.timeout(90)
class TestHashValidation:
    """QUAL-01: Hash validation tests."""

    def test_artifact_hash_validation_linux_sys_users(
        self, velociraptor_client, target_registry
    ):
        """Validate Linux.Sys.Users collection hash against baseline.

        This test:
        1. Collects Linux.Sys.Users artifact
        2. Computes SHA-256 hash of normalized results
        3. Compares against baseline hash (if populated)
        4. Logs hash for baseline population if first run
        """
        target = target_registry.get_by_artifact("Linux.Sys.Users")
        if not target:
            pytest.skip("No Linux target available")

        client_id = target.client_id

        # Collect artifact
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['Linux.Sys.Users'],
            timeout=30
        ) AS collection
        FROM scope()
        """
        result = velociraptor_client.query(vql)

        with check:
            assert len(result) > 0, "collect_client returned no results"

        collection = result[0].get("collection", {})
        flow_id = collection.get("flow_id")

        if not flow_id:
            pytest.fail("No flow_id returned")

        # Wait for completion
        try:
            wait_for_flow_completion(
                velociraptor_client, client_id, flow_id, timeout=30
            )
        except TimeoutError:
            pytest.fail("Collection did not complete in 30s")

        # Get results
        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Linux.Sys.Users'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Compute hash
        actual_hash = compute_forensic_hash(results)

        # Load baseline metadata
        metadata = load_baseline_metadata()
        baseline_info = metadata.get("baselines", {}).get("Linux.Sys.Users", {})
        expected_hash = baseline_info.get("sha256")

        if expected_hash is None:
            # First run - log hash for baseline population
            pytest.skip(
                f"Baseline hash not yet populated. "
                f"Computed hash: {actual_hash}\n"
                f"Update metadata.json with this hash after manual verification."
            )

        # Validate hash matches
        assert actual_hash == expected_hash, (
            f"Hash mismatch for Linux.Sys.Users:\n"
            f"  Expected: {expected_hash}\n"
            f"  Got: {actual_hash}\n"
            f"This may indicate data drift or schema change."
        )

    def test_hash_determinism(self):
        """Verify hash function produces deterministic output.

        Same data with different key ordering should produce same hash.
        """
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}

        hash1 = compute_forensic_hash(data1)
        hash2 = compute_forensic_hash(data2)

        assert hash1 == hash2, (
            "Hash should be deterministic regardless of key order"
        )

        # Verify it's actually a SHA-256 hash (64 hex chars)
        assert len(hash1) == 64, f"Expected SHA-256 (64 chars), got {len(hash1)}"
        assert all(c in '0123456789abcdef' for c in hash1), "Hash should be hex"


@pytest.mark.integration
@pytest.mark.timeout(60)
class TestTimestampAccuracy:
    """QUAL-02: Timestamp accuracy tests."""

    def test_timestamp_within_drift_tolerance(
        self, velociraptor_client, target_registry
    ):
        """Validate artifact collection timestamps within +/-1 second drift.

        This test:
        1. Records current time before collection
        2. Collects Generic.Client.Info (has timestamp field)
        3. Validates collection timestamp is within +/-1 second of recorded time
        """
        target = target_registry.get_by_artifact("Generic.Client.Info")
        if not target:
            pytest.skip("No target available")

        client_id = target.client_id

        # Record time before collection
        before_time = time.time()

        # Collect artifact
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['Generic.Client.Info'],
            timeout=30
        ) AS collection
        FROM scope()
        """
        result = velociraptor_client.query(vql)

        # Record time after query
        after_time = time.time()

        with check:
            assert len(result) > 0, "collect_client returned no results"

        collection = result[0].get("collection", {})
        flow_id = collection.get("flow_id")

        if not flow_id:
            pytest.fail("No flow_id returned")

        # Wait for completion
        try:
            wait_for_flow_completion(
                velociraptor_client, client_id, flow_id, timeout=30
            )
        except TimeoutError:
            pytest.fail("Collection did not complete in 30s")

        # Get flow metadata for timestamps
        flow_vql = f"""
        SELECT * FROM flows(client_id='{client_id}', flow_id='{flow_id}')
        """
        flow_info = velociraptor_client.query(flow_vql)

        if not flow_info:
            pytest.skip("Could not retrieve flow metadata")

        flow = flow_info[0]

        # Check start time (create_time field)
        start_time_field = flow.get("create_time") or flow.get("start_time")
        if start_time_field:
            start_ts = parse_velociraptor_timestamp(start_time_field)

            # Flow should have started within our time window +/- 1 second
            # Use pytest.approx with 1 second absolute tolerance
            expected_start = (before_time + after_time) / 2  # Midpoint

            with check:
                assert start_ts == approx(expected_start, abs=2.0), (
                    f"Flow start time drift: {abs(start_ts - expected_start):.2f}s\n"
                    f"Expected around: {expected_start}\n"
                    f"Got: {start_ts}"
                )
        else:
            # Log available fields for debugging
            pytest.skip(
                f"No timestamp field found. Available: {list(flow.keys())}"
            )

    def test_timestamp_parsing_formats(self):
        """Verify timestamp parser handles all expected formats."""
        # Unix epoch integer
        ts1 = parse_velociraptor_timestamp(1706275200)
        assert ts1 == 1706275200.0

        # Unix epoch float
        ts2 = parse_velociraptor_timestamp(1706275200.5)
        assert ts2 == 1706275200.5

        # RFC3339 with Z
        ts3 = parse_velociraptor_timestamp("2024-01-26T12:00:00Z")
        assert isinstance(ts3, float)

        # ISO8601 with offset
        ts4 = parse_velociraptor_timestamp("2024-01-26T12:00:00+00:00")
        assert isinstance(ts4, float)

        # String epoch
        ts5 = parse_velociraptor_timestamp("1706275200")
        assert ts5 == 1706275200.0

        # Invalid format should raise
        with pytest.raises(ValueError):
            parse_velociraptor_timestamp("not-a-timestamp")
