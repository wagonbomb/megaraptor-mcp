"""Artifact collection smoke tests.

Validates:
- SMOKE-02: Generic.Client.Info artifact collection works against live container
- SMOKE-03: Process list artifact collection returns valid process list structure

Unlike the parametrized MCP tool tests, these tests actually wait for
artifact collections to complete and validate the returned data structure.

Note: source() VQL function requires specific source names, not just artifact names.
For example: source(artifact='Generic.Client.Info', source='BasicInformation')
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
        3. Validates returned metadata structure from BasicInformation source
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

        # Get flow results - use specific source name (BasicInformation)
        # The source() function requires artifact + source, not just artifact name
        results_vql = f"""
        SELECT * FROM source(
            client_id='{enrolled_client_id}',
            flow_id='{flow_id}',
            artifact='Generic.Client.Info',
            source='BasicInformation'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Validate results structure
        with check:
            assert len(results) > 0, "Generic.Client.Info/BasicInformation returned no results"

        if results:
            info = results[0]

            # Check critical fields that AI assistants need
            # Field names may vary by Velociraptor version
            hostname_found = any(k in info for k in ["Hostname", "hostname", "Fqdn"])
            os_found = any(k in info for k in ["OS", "os", "System", "Platform"])

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

    def test_process_list_artifact(self, velociraptor_client, enrolled_client_id):
        """Smoke test: Process list artifact collection.

        Validates SMOKE-03: Process list artifact returns valid process list
        structure (PID, name, command line).

        Note: Generic.System.Pslist does not exist in Velociraptor 0.75.x.
        This test uses Linux.Sys.Pslist for Linux clients.
        Phase 4 (OS-Specific) will properly handle Windows/macOS variants.

        This test:
        1. Determines correct artifact for target OS
        2. Schedules process list collection
        3. Waits for flow to complete
        4. Validates returned process list structure
        """
        # Determine which Pslist artifact to use based on available artifacts
        # Generic.System.Pslist doesn't exist in Velociraptor 0.75.x
        # Use Linux.Sys.Pslist for Linux clients
        artifact_vql = """
        SELECT name FROM artifact_definitions()
        WHERE name = 'Linux.Sys.Pslist'
        """
        available = velociraptor_client.query(artifact_vql)

        if not available:
            pytest.skip("No Pslist artifact available for this OS")

        artifact_name = "Linux.Sys.Pslist"

        # Schedule artifact collection
        vql = f"""
        SELECT collect_client(
            client_id='{enrolled_client_id}',
            artifacts=['{artifact_name}'],
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
            pytest.fail(f"{artifact_name} collection did not complete in 30s")

        # Get flow results - Linux.Sys.Pslist doesn't have sub-sources
        results_vql = f"""
        SELECT * FROM source(
            client_id='{enrolled_client_id}',
            flow_id='{flow_id}',
            artifact='{artifact_name}'
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
            # Command line is expected for Linux.Sys.Pslist
            with check:
                assert cmdline_found, \
                    f"Missing CommandLine field. Available: {list(process.keys())}"

            # Validate PID is numeric (may be string in VQL)
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

        # Note: Velociraptor client container runs minimal processes
        # Don't assert many processes - even 1 is valid for smoke test
        with check:
            assert len(results) >= 1, \
                f"Expected at least 1 process, got {len(results)}"
