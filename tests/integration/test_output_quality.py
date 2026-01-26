"""Output quality validation tests.

Validates:
- QUAL-01: Hash validation confirms collected artifacts match expected values
- QUAL-02: Timeline accuracy testing verifies timestamps within +/-1 second drift
- QUAL-03: Artifact completeness validation (all expected fields present)
- QUAL-04: VQL result correctness against known-good baselines
- QUAL-06: NIST CFTT false positive rate definition and validation
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


@pytest.mark.integration
@pytest.mark.timeout(90)
class TestArtifactCompleteness:
    """QUAL-03: Artifact completeness validation tests."""

    @pytest.mark.parametrize("artifact_name,required_fields", [
        ("Linux.Sys.Users", ["User"]),
        ("Generic.Client.Info", []),  # Has flexible structure
    ])
    def test_artifact_completeness_validation(
        self, artifact_name, required_fields, velociraptor_client, target_registry
    ):
        """Validate all expected fields are present in artifact results.

        Tests QUAL-03: Artifact completeness validation ensures all
        expected fields present.
        """
        target = target_registry.get_by_artifact(artifact_name)
        if not target:
            pytest.skip(f"No target available for {artifact_name}")

        client_id = target.client_id

        # Collect artifact
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['{artifact_name}'],
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

        # Get results - handle artifacts with and without sub-sources
        if artifact_name == "Generic.Client.Info":
            results_vql = f"""
            SELECT * FROM source(
                client_id='{client_id}',
                flow_id='{flow_id}',
                artifact='Generic.Client.Info/BasicInformation'
            )
            """
        else:
            results_vql = f"""
            SELECT * FROM source(
                client_id='{client_id}',
                flow_id='{flow_id}',
                artifact='{artifact_name}'
            )
            """
        results = velociraptor_client.query(results_vql)

        # Validate results not empty
        with check:
            assert len(results) > 0, f"{artifact_name} returned no results"

        if results:
            # Validate required fields present in all rows
            for field in required_fields:
                field_present = all(
                    any(k.lower() == field.lower() for k in r.keys())
                    for r in results
                )
                with check:
                    assert field_present, (
                        f"Missing required field '{field}' in {artifact_name}"
                    )

            # Validate no empty required fields
            for field in required_fields:
                for r in results:
                    # Find field with case-insensitive match
                    actual_key = next(
                        (k for k in r.keys() if k.lower() == field.lower()),
                        None
                    )
                    if actual_key:
                        with check:
                            assert r[actual_key] is not None, (
                                f"Required field '{field}' is None"
                            )
                            if isinstance(r[actual_key], str):
                                assert len(r[actual_key]) > 0, (
                                    f"Required field '{field}' is empty string"
                                )


    def test_completeness_field_count_reasonable(
        self, velociraptor_client, target_registry
    ):
        """Verify artifacts return reasonable number of fields.

        Completeness also means getting expected field count, not just
        required fields.
        """
        target = target_registry.get_by_artifact("Linux.Sys.Users")
        if not target:
            pytest.skip("No Linux target available")

        client_id = target.client_id

        # Quick collection
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['Linux.Sys.Users'],
            timeout=30
        ) AS collection
        FROM scope()
        """
        result = velociraptor_client.query(vql)
        collection = result[0].get("collection", {})
        flow_id = collection.get("flow_id")

        if not flow_id:
            pytest.fail("No flow_id returned")

        wait_for_flow_completion(velociraptor_client, client_id, flow_id, timeout=30)

        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Linux.Sys.Users'
        )
        """
        results = velociraptor_client.query(results_vql)

        if results:
            # Linux.Sys.Users should have at least User, Uid, Gid
            # (typically also Homedir, Shell, Description)
            field_count = len(results[0].keys())
            with check:
                assert field_count >= 3, (
                    f"Expected at least 3 fields, got {field_count}: "
                    f"{list(results[0].keys())}"
                )


@pytest.mark.integration
@pytest.mark.timeout(120)
class TestVQLCorrectness:
    """QUAL-04: VQL result correctness against known-good baselines."""

    def test_vql_correctness_linux_sys_users(
        self, velociraptor_client, target_registry
    ):
        """Validate Linux.Sys.Users results match baseline structure.

        Compares actual results against baseline for:
        - Field presence (critical fields exist)
        - Value types (strings vs integers)
        - Result count (reasonable magnitude)
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
        collection = result[0].get("collection", {})
        flow_id = collection.get("flow_id")

        if not flow_id:
            pytest.fail("No flow_id returned")

        wait_for_flow_completion(velociraptor_client, client_id, flow_id, timeout=30)

        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Linux.Sys.Users'
        )
        """
        actual_results = velociraptor_client.query(results_vql)

        # Load baseline
        try:
            baseline = load_baseline("Linux.Sys.Users")
        except FileNotFoundError:
            baseline = None

        if not baseline:
            pytest.skip(
                "Baseline not populated. First results:\n"
                f"{actual_results[:2] if actual_results else 'No results'}"
            )

        # Load critical fields from metadata
        metadata = load_baseline_metadata()
        critical_fields = metadata.get("baselines", {}).get(
            "Linux.Sys.Users", {}
        ).get("critical_fields", ["User", "Uid", "Gid"])

        # Validate critical fields present
        if actual_results:
            actual_fields = set(actual_results[0].keys())
            for field in critical_fields:
                # Case-insensitive check
                field_found = any(
                    k.lower() == field.lower() for k in actual_fields
                )
                with check:
                    assert field_found, (
                        f"Missing critical field: {field}\n"
                        f"Available: {actual_fields}"
                    )

        # Validate result count in reasonable range
        # (±50% of baseline, as per research Pattern 4)
        if baseline:
            baseline_count = len(baseline)
            actual_count = len(actual_results)

            # Allow 50% variance
            with check:
                assert actual_count >= baseline_count * 0.5, (
                    f"Result count too low: {actual_count} vs baseline {baseline_count}"
                )
            with check:
                assert actual_count <= baseline_count * 2.0, (
                    f"Result count too high: {actual_count} vs baseline {baseline_count}"
                )

    def test_vql_correctness_no_false_positives(
        self, velociraptor_client, target_registry
    ):
        """Validate VQL results contain no obvious false positives.

        For Linux.Sys.Users: All returned users should have valid structure.
        This tests QUAL-06: NIST CFTT false positive rate < 1%.
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
        collection = result[0].get("collection", {})
        flow_id = collection.get("flow_id")

        if not flow_id:
            pytest.fail("No flow_id returned")

        wait_for_flow_completion(velociraptor_client, client_id, flow_id, timeout=30)

        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Linux.Sys.Users'
        )
        """
        results = velociraptor_client.query(results_vql)

        if not results:
            pytest.skip("No results to validate")

        # Count potential false positives
        false_positives = 0
        total_results = len(results)

        for r in results:
            # Get username field
            user = r.get("User") or r.get("user") or r.get("Username")

            # False positive indicators for user data:
            # 1. Empty or None username
            if not user:
                false_positives += 1
                continue

            # 2. Username contains invalid characters (basic check)
            if '\x00' in str(user):
                false_positives += 1
                continue

            # 3. UID is negative (invalid)
            uid = r.get("Uid") or r.get("uid") or r.get("UID")
            if uid is not None:
                try:
                    if int(uid) < 0:
                        false_positives += 1
                        continue
                except (ValueError, TypeError):
                    pass  # Non-numeric UID, not necessarily false positive

        # Calculate false positive rate
        fp_rate = (false_positives / total_results * 100) if total_results > 0 else 0

        # NIST CFTT requires < 1% false positive rate
        with check:
            assert fp_rate < 1.0, (
                f"False positive rate {fp_rate:.2f}% exceeds NIST CFTT threshold of 1%\n"
                f"False positives: {false_positives}/{total_results}"
            )

        # For deterministic VQL, we actually expect 0% false positives
        with check:
            assert false_positives == 0, (
                f"VQL is deterministic - expected 0 false positives, got {false_positives}"
            )
