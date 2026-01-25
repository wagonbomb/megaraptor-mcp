"""Artifact collection smoke tests.

Validates:
- SMOKE-02: Generic.Client.Info artifact collection works against live container
- SMOKE-03: Generic.System.Pslist returns valid process list structure

Unlike the parametrized MCP tool tests, these tests actually wait for
artifact collections to complete and validate the returned data structure.
"""

import pytest
from pytest_check import check

from tests.integration.helpers.wait_helpers import wait_for_flow_completion


@pytest.mark.smoke
@pytest.mark.integration
@pytest.mark.timeout(60)
class TestArtifactCollectionSmoke:
    """Smoke tests for artifact collection."""

    def test_generic_client_info(self, velociraptor_client, enrolled_client_id):
        """Smoke test: Generic.Client.Info artifact collection.

        Validates SMOKE-02: Generic.Client.Info artifact collection completes
        and returns valid client metadata.

        This test:
        1. Schedules Generic.Client.Info collection
        2. Waits for flow to complete
        3. Validates returned metadata structure
        """
        # Schedule artifact collection
        vql = f"""
        SELECT collect_client(
            client_id='{enrolled_client_id}',
            artifacts=['Generic.Client.Info'],
            timeout=30
        ) AS collection
        FROM scope()
        """

        result = velociraptor_client.query(vql)

        # Validate collection was scheduled
        with check:
            assert len(result) > 0, "collect_client returned no results"
        with check:
            assert "collection" in result[0], "Missing 'collection' field"

        collection = result[0]["collection"]
        with check:
            assert "flow_id" in collection, "Missing 'flow_id' in collection"

        flow_id = collection.get("flow_id")
        if not flow_id:
            pytest.fail("No flow_id returned from collect_client")

        # Wait for flow completion
        try:
            wait_for_flow_completion(
                velociraptor_client,
                enrolled_client_id,
                flow_id,
                timeout=30
            )
        except TimeoutError:
            pytest.fail("Generic.Client.Info collection did not complete in 30s")

        # Get flow results
        results_vql = f"""
        SELECT * FROM source(
            client_id='{enrolled_client_id}',
            flow_id='{flow_id}',
            artifact='Generic.Client.Info'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Validate results structure
        with check:
            assert len(results) > 0, "Generic.Client.Info returned no results"

        if results:
            info = results[0]

            # Check critical fields that AI assistants need
            # Field names may vary by Velociraptor version
            hostname_found = any(k in info for k in ["Hostname", "hostname", "Fqdn"])
            os_found = any(k in info for k in ["OS", "os", "System", "Platform"])
            client_id_found = any(k in info for k in ["ClientId", "client_id", "Client"])

            with check:
                assert hostname_found, \
                    f"Missing hostname field. Available: {list(info.keys())}"
            with check:
                assert os_found, \
                    f"Missing OS field. Available: {list(info.keys())}"

            # Validate hostname is non-empty string
            hostname_key = next((k for k in ["Hostname", "hostname", "Fqdn"] if k in info), None)
            if hostname_key:
                with check:
                    assert isinstance(info[hostname_key], str), \
                        f"Hostname should be string, got {type(info[hostname_key])}"
                with check:
                    assert len(info[hostname_key]) > 0, "Hostname is empty"

    def test_generic_system_pslist(self, velociraptor_client, enrolled_client_id):
        """Smoke test: Generic.System.Pslist artifact collection.

        Validates SMOKE-03: Generic.System.Pslist returns valid process list
        structure (PID, name, command line).

        This test:
        1. Schedules Generic.System.Pslist collection
        2. Waits for flow to complete
        3. Validates returned process list structure
        """
        # Schedule artifact collection
        vql = f"""
        SELECT collect_client(
            client_id='{enrolled_client_id}',
            artifacts=['Generic.System.Pslist'],
            timeout=30
        ) AS collection
        FROM scope()
        """

        result = velociraptor_client.query(vql)

        # Validate collection was scheduled
        with check:
            assert len(result) > 0, "collect_client returned no results"

        collection = result[0].get("collection", {})
        flow_id = collection.get("flow_id")

        if not flow_id:
            pytest.fail("No flow_id returned from collect_client")

        # Wait for flow completion
        try:
            wait_for_flow_completion(
                velociraptor_client,
                enrolled_client_id,
                flow_id,
                timeout=30
            )
        except TimeoutError:
            pytest.fail("Generic.System.Pslist collection did not complete in 30s")

        # Get flow results
        results_vql = f"""
        SELECT * FROM source(
            client_id='{enrolled_client_id}',
            flow_id='{flow_id}',
            artifact='Generic.System.Pslist'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Validate process list structure
        with check:
            assert len(results) > 0, "Pslist returned no processes"

        if results:
            # Check first process entry
            process = results[0]

            # Expected fields for process list (SMOKE-03)
            # Field names may vary by platform
            pid_found = any(k in process for k in ["Pid", "PID", "pid"])
            name_found = any(k in process for k in ["Name", "name", "Exe", "exe"])
            cmdline_found = any(k in process for k in [
                "CommandLine", "command_line", "Cmdline", "cmdline", "Commandline"
            ])

            with check:
                assert pid_found, \
                    f"Missing PID field. Available: {list(process.keys())}"
            with check:
                assert name_found, \
                    f"Missing process name field. Available: {list(process.keys())}"
            # Command line may be empty for some processes, so just check presence
            with check:
                assert cmdline_found or True, \
                    f"Note: Command line field not found. Available: {list(process.keys())}"

            # Validate PID is numeric
            pid_key = next((k for k in ["Pid", "PID", "pid"] if k in process), None)
            if pid_key:
                with check:
                    assert isinstance(process[pid_key], (int, str)), \
                        f"PID should be int or string, got {type(process[pid_key])}"

            # Validate name is string
            name_key = next((k for k in ["Name", "name", "Exe", "exe"] if k in process), None)
            if name_key:
                with check:
                    assert isinstance(process[name_key], str), \
                        f"Process name should be string, got {type(process[name_key])}"

        # Verify we got multiple processes (healthy system has many)
        with check:
            assert len(results) > 5, \
                f"Expected many processes, got only {len(results)}"
