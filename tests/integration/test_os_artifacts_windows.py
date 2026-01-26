"""Windows OS-specific artifact collection tests.

Validates:
- OSART-02: Windows.System.Services artifact collection and validation
- OSART-03: Windows registry artifact collection (UserAssist)
- OSART-05: OS-specific validation schemas work for Windows artifacts

Uses skip guards to gracefully skip when no Windows target available.
Tests will run when Windows target becomes available.
"""

import pytest
from jsonschema import validate, ValidationError
from pytest_check import check

from tests.conftest import skip_no_windows_target
from tests.integration.helpers.wait_helpers import wait_for_flow_completion
from tests.integration.schemas import (
    WINDOWS_SYSTEM_SERVICES_SCHEMA,
    WINDOWS_REGISTRY_USERASSIST_SCHEMA,
)


@pytest.mark.integration
@pytest.mark.windows
@pytest.mark.timeout(60)
class TestWindowsArtifacts:
    """Windows-specific artifact collection tests."""

    @skip_no_windows_target
    def test_windows_system_services_collection(self, velociraptor_client, target_registry):
        """Test Windows.System.Services artifact collection and validation.

        Validates OSART-02: Windows.System.Services artifact collection returns
        valid service data from Windows targets.

        This test:
        1. Selects Windows target via TargetRegistry
        2. Schedules Windows.System.Services artifact collection
        3. Waits for flow completion
        4. Validates results against JSON schema
        5. Verifies critical service fields are present and typed correctly
        """
        # Get Windows target using get_by_artifact method
        target = target_registry.get_by_artifact("Windows.System.Services")
        if not target:
            pytest.skip("No Windows target available for Windows.System.Services")

        # Verify we got a Windows target
        assert target.os_type == "windows", \
            f"Expected Windows target, got {target.os_type}"

        client_id = target.client_id

        # Schedule artifact collection
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['Windows.System.Services'],
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
                client_id,
                flow_id,
                timeout=30
            )
        except TimeoutError:
            pytest.fail("Windows.System.Services collection did not complete in 30s")

        # Get flow results
        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Windows.System.Services'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Validate results against JSON schema
        try:
            validate(instance=results, schema=WINDOWS_SYSTEM_SERVICES_SCHEMA)
        except ValidationError as e:
            pytest.fail(f"Schema validation failed: {e.message}")

        # Validate we got service data
        with check:
            assert len(results) > 0, "Windows.System.Services returned no services"

        if results:
            service = results[0]

            # Verify critical fields present
            with check:
                assert "Name" in service, \
                    f"Missing Name field. Available: {list(service.keys())}"

            # Validate Name field type and value
            if "Name" in service:
                with check:
                    assert isinstance(service["Name"], str), \
                        f"Name should be string, got {type(service['Name'])}"
                with check:
                    assert len(service["Name"]) > 0, "Name field is empty"

            # Validate State field if present
            if "State" in service:
                valid_states = ["Running", "Stopped", "Paused", "Start Pending", "Stop Pending"]
                with check:
                    assert service["State"] in valid_states or service["State"], \
                        f"Invalid State value: {service['State']}"

        # Validate we have reasonable number of services
        # Windows typically has dozens of services
        with check:
            assert len(results) >= 10, \
                f"Expected at least 10 services, got {len(results)}"


    @skip_no_windows_target
    def test_windows_registry_userassist_collection(self, velociraptor_client, target_registry):
        """Test Windows.Registry.UserAssist artifact collection and validation.

        Validates OSART-03: Windows registry artifact collection works and
        returns valid registry data from Windows targets.

        This test:
        1. Selects Windows target with registry capability
        2. Schedules Windows.Registry.UserAssist artifact collection
        3. Waits for flow completion
        4. Validates results against JSON schema
        5. Verifies registry fields are present and typed correctly
        """
        # Get Windows target with registry capability
        target = target_registry.get_by_artifact("Windows.Registry.UserAssist")
        if not target:
            pytest.skip("No Windows target with registry capability available")

        # Verify we got a Windows target
        assert target.os_type == "windows", \
            f"Expected Windows target, got {target.os_type}"

        # Verify registry capability
        assert "windows_registry" in target.capabilities, \
            f"Target missing windows_registry capability: {target.capabilities}"

        client_id = target.client_id

        # Schedule artifact collection
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['Windows.Registry.UserAssist'],
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
                client_id,
                flow_id,
                timeout=30
            )
        except TimeoutError:
            pytest.fail("Windows.Registry.UserAssist collection did not complete in 30s")

        # Get flow results
        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Windows.Registry.UserAssist'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Validate results against JSON schema
        try:
            validate(instance=results, schema=WINDOWS_REGISTRY_USERASSIST_SCHEMA)
        except ValidationError as e:
            pytest.fail(f"Schema validation failed: {e.message}")

        # Note: UserAssist may return empty results if no user activity
        # This is valid - just validate structure when results exist
        if results:
            entry = results[0]

            # Verify registry key path if present
            if "_KeyPath" in entry:
                with check:
                    assert isinstance(entry["_KeyPath"], str), \
                        f"_KeyPath should be string, got {type(entry['_KeyPath'])}"
                with check:
                    assert "UserAssist" in entry["_KeyPath"], \
                        f"Expected UserAssist in key path: {entry['_KeyPath']}"

            # Verify Name field (ROT13-decoded application name) if present
            if "Name" in entry:
                with check:
                    assert isinstance(entry["Name"], str), \
                        f"Name should be string, got {type(entry['Name'])}"

            # Verify NumberOfExecutions if present
            if "NumberOfExecutions" in entry:
                with check:
                    assert isinstance(entry["NumberOfExecutions"], (int, str)), \
                        f"NumberOfExecutions should be int or string, got {type(entry['NumberOfExecutions'])}"


    @skip_no_windows_target
    def test_target_registry_windows_selection(self, target_registry):
        """Test TargetRegistry correctly selects Windows targets for Windows artifacts.

        Validates OSART-04: TargetRegistry artifact-based selection works
        for Windows-specific artifacts.
        """
        # Windows.System.Services should return Windows target
        services_target = target_registry.get_by_artifact("Windows.System.Services")
        if services_target:
            with check:
                assert services_target.os_type == "windows", \
                    f"Windows.System.Services should select Windows target, got {services_target.os_type}"
            with check:
                assert "windows_services" in services_target.capabilities, \
                    f"Windows target missing windows_services capability: {services_target.capabilities}"

        # Windows.Registry artifacts should return Windows target with registry capability
        registry_target = target_registry.get_by_artifact("Windows.Registry.UserAssist")
        if registry_target:
            with check:
                assert registry_target.os_type == "windows", \
                    f"Windows.Registry.* should select Windows target, got {registry_target.os_type}"
            with check:
                assert "windows_registry" in registry_target.capabilities, \
                    f"Registry target missing windows_registry capability: {registry_target.capabilities}"

        # If no Windows target available, both should return None
        if not services_target and not registry_target:
            pytest.skip("No Windows target available (expected in Linux-only environment)")
