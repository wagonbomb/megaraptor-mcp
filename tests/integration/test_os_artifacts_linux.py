"""Linux OS-specific artifact collection tests.

Validates:
- OSART-01: Linux.Sys.Users artifact collection and validation works
- OSART-04: TargetRegistry artifact-based target selection

Uses the existing Docker container with Linux client for testing.
"""

import pytest
from jsonschema import validate, ValidationError
from pytest_check import check

from tests.integration.helpers.wait_helpers import wait_for_flow_completion
from tests.integration.schemas.os_artifacts import LINUX_SYS_USERS_SCHEMA


@pytest.mark.integration
@pytest.mark.timeout(60)
class TestLinuxArtifacts:
    """Linux-specific artifact collection tests."""

    def test_linux_sys_users_collection(self, velociraptor_client, target_registry):
        """Test Linux.Sys.Users artifact collection and validation.

        Validates OSART-01: Linux.Sys.Users artifact collection returns
        valid user account data from Linux targets.

        This test:
        1. Selects Linux target via TargetRegistry
        2. Schedules Linux.Sys.Users artifact collection
        3. Waits for flow completion
        4. Validates results against JSON schema
        5. Verifies critical user fields are present and typed correctly
        """
        # Get Linux target using new get_by_artifact method (validates OSART-04)
        target = target_registry.get_by_artifact("Linux.Sys.Users")
        if not target:
            pytest.skip("No Linux target available for Linux.Sys.Users")

        # Verify we got a Linux target
        assert target.os_type == "linux", \
            f"Expected Linux target, got {target.os_type}"

        client_id = target.client_id

        # Schedule artifact collection
        vql = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['Linux.Sys.Users'],
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
            pytest.fail("Linux.Sys.Users collection did not complete in 30s")

        # Get flow results
        # Linux.Sys.Users does not have sub-sources (unlike Generic.Client.Info)
        results_vql = f"""
        SELECT * FROM source(
            client_id='{client_id}',
            flow_id='{flow_id}',
            artifact='Linux.Sys.Users'
        )
        """
        results = velociraptor_client.query(results_vql)

        # Validate results against JSON schema
        try:
            validate(instance=results, schema=LINUX_SYS_USERS_SCHEMA)
        except ValidationError as e:
            pytest.fail(f"Schema validation failed: {e.message}")

        # Validate we got user data
        with check:
            assert len(results) > 0, "Linux.Sys.Users returned no users"

        if results:
            user = results[0]

            # Verify critical fields present with flexible matching
            # Field names established from Velociraptor docs
            user_found = any(k in user for k in ["User", "user", "Username", "username"])
            uid_found = any(k in user for k in ["Uid", "uid", "UID"])
            gid_found = any(k in user for k in ["Gid", "gid", "GID"])

            with check:
                assert user_found, \
                    f"Missing user field. Available: {list(user.keys())}"
            with check:
                assert uid_found, \
                    f"Missing UID field. Available: {list(user.keys())}"
            with check:
                assert gid_found, \
                    f"Missing GID field. Available: {list(user.keys())}"

            # Validate User field type and value
            user_key = next((k for k in ["User", "user", "Username", "username"] if k in user), None)
            if user_key:
                with check:
                    assert isinstance(user[user_key], str), \
                        f"User should be string, got {type(user[user_key])}"
                with check:
                    assert len(user[user_key]) > 0, "User field is empty"

            # Linux container should have at least root user
            usernames = [
                r.get("User", r.get("user", r.get("Username", "")))
                for r in results
            ]
            with check:
                assert any(u == "root" for u in usernames), \
                    f"Expected 'root' user in results. Found: {usernames[:5]}"

        # Validate we have reasonable number of users
        # Docker containers typically have at least root, nobody, etc.
        with check:
            assert len(results) >= 1, \
                f"Expected at least 1 user, got {len(results)}"


    def test_target_registry_get_by_artifact(self, target_registry):
        """Test TargetRegistry.get_by_artifact() method.

        Validates OSART-04: TargetRegistry selects appropriate test targets
        based on artifact capabilities.
        """
        # Linux artifacts should return Linux target
        linux_target = target_registry.get_by_artifact("Linux.Sys.Users")
        if linux_target:
            with check:
                assert linux_target.os_type == "linux", \
                    f"Linux artifact should select Linux target, got {linux_target.os_type}"
            with check:
                assert "linux_users" in linux_target.capabilities, \
                    f"Linux target missing linux_users capability: {linux_target.capabilities}"

        # Windows artifacts should return Windows target (or None if unavailable)
        windows_target = target_registry.get_by_artifact("Windows.System.Services")
        if windows_target:
            with check:
                assert windows_target.os_type == "windows", \
                    f"Windows artifact should select Windows target, got {windows_target.os_type}"

        # Windows.Registry artifacts should check registry capability
        registry_target = target_registry.get_by_artifact("Windows.Registry.UserAssist")
        if registry_target:
            with check:
                assert registry_target.os_type == "windows", \
                    f"Registry artifact should select Windows target, got {registry_target.os_type}"
            with check:
                assert "windows_registry" in registry_target.capabilities, \
                    f"Registry target missing windows_registry capability"

        # Generic artifacts should return any target
        generic_target = target_registry.get_by_artifact("Generic.Client.Info")
        with check:
            assert generic_target is not None, \
                "Generic.Client.Info should return a target (any OS works)"
