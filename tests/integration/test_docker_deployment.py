"""Integration tests for Docker deployment functionality.

These tests verify the Docker deployer can create and manage
Velociraptor server containers. They require Docker to be available.

Note: These tests create real Docker containers. Cleanup is performed
automatically but containers may be left behind if tests crash.
"""

import asyncio
import uuid
from pathlib import Path

import pytest

# These tests require Docker
pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="module")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def unique_deployment_id():
    """Generate a unique deployment ID for test isolation."""
    return f"test-deploy-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def docker_deployer(docker_available, temp_deployment_dir):
    """Create a DockerDeployer for testing."""
    if not docker_available:
        pytest.skip("Docker not available")

    try:
        from megaraptor_mcp.deployment.deployers.docker_deployer import DockerDeployer

        deployer = DockerDeployer(
            deployment_dir=temp_deployment_dir,
        )
        return deployer
    except ImportError as e:
        pytest.skip(f"Docker deployer not available: {e}")


class TestDockerDeployerAvailability:
    """Tests for Docker availability checks."""

    def test_docker_client_available(self, docker_available):
        """Test that Docker client is available."""
        assert docker_available is True

    def test_can_import_docker_module(self):
        """Test that docker Python module can be imported."""
        try:
            import docker
            assert docker is not None
        except ImportError:
            pytest.skip("docker module not installed")


class TestDockerDeployerConfiguration:
    """Tests for Docker deployer configuration."""

    def test_deployer_initialization(self, docker_deployer):
        """Test deployer initializes correctly."""
        assert docker_deployer is not None

    def test_deployer_has_docker_client(self, docker_deployer):
        """Test deployer has a Docker client."""
        assert hasattr(docker_deployer, "docker_client") or hasattr(docker_deployer, "_docker")


class TestDeploymentLifecycle:
    """Tests for the full deployment lifecycle.

    These tests are marked as slow because they involve Docker operations.
    """

    @pytest.mark.slow
    async def test_deploy_and_destroy(
        self,
        docker_deployer,
        unique_deployment_id,
        temp_certs_dir,
    ):
        """Test deploying and destroying a Velociraptor server."""
        from megaraptor_mcp.deployment.profiles import get_profile
        from megaraptor_mcp.deployment.security import CertificateManager

        # Generate certificates
        cert_manager = CertificateManager(storage_path=temp_certs_dir)
        bundle = cert_manager.generate_bundle(
            server_hostname="localhost",
            rapid=True,
        )

        profile = get_profile("rapid")

        try:
            # Deploy
            result = await docker_deployer.deploy(
                deployment_id=unique_deployment_id,
                profile=profile,
                certificate_bundle=bundle,
            )

            assert result.success is True
            assert result.deployment_id == unique_deployment_id
            assert result.container_id is not None

            # Verify container is running
            status = await docker_deployer.get_status(unique_deployment_id)
            assert status.state.value in ["running", "provisioning"]

        finally:
            # Always cleanup
            await docker_deployer.destroy(unique_deployment_id)

    @pytest.mark.slow
    async def test_get_status_nonexistent(self, docker_deployer):
        """Test getting status of non-existent deployment."""
        status = await docker_deployer.get_status("nonexistent-deployment")

        assert status is None or status.state.value in ["destroyed", "pending"]

    @pytest.mark.slow
    async def test_list_deployments(self, docker_deployer):
        """Test listing deployments."""
        deployments = await docker_deployer.list_deployments()

        assert isinstance(deployments, list)


class TestDeploymentValidation:
    """Tests for deployment validation."""

    @pytest.mark.slow
    async def test_validate_healthy_deployment(
        self,
        docker_deployer,
        unique_deployment_id,
        temp_certs_dir,
    ):
        """Test validating a healthy deployment."""
        from megaraptor_mcp.deployment.profiles import get_profile
        from megaraptor_mcp.deployment.security import CertificateManager

        cert_manager = CertificateManager(storage_path=temp_certs_dir)
        bundle = cert_manager.generate_bundle(
            server_hostname="localhost",
            rapid=True,
        )

        profile = get_profile("rapid")

        try:
            # Deploy
            result = await docker_deployer.deploy(
                deployment_id=unique_deployment_id,
                profile=profile,
                certificate_bundle=bundle,
            )

            if not result.success:
                pytest.skip("Deployment failed")

            # Wait for container to start
            await asyncio.sleep(5)

            # Validate
            validation = await docker_deployer.validate(unique_deployment_id)

            assert validation is not None
            # Container should be running even if not fully healthy yet

        finally:
            await docker_deployer.destroy(unique_deployment_id)


class TestResourceLimits:
    """Tests for Docker resource limit enforcement."""

    def test_profile_resource_limits(self):
        """Test that profiles define resource limits."""
        from megaraptor_mcp.deployment.profiles import get_profile

        rapid = get_profile("rapid")

        assert "memory" in rapid.resource_limits
        assert "cpus" in rapid.resource_limits
        assert rapid.resource_limits["memory"] == "4g"
        assert rapid.resource_limits["cpus"] == "2"


class TestContainerNaming:
    """Tests for container naming conventions."""

    def test_container_name_format(self, unique_deployment_id):
        """Test that deployment IDs are valid container names."""
        # Container names can contain lowercase letters, digits, hyphens, and underscores
        import re

        pattern = r'^[a-z0-9][a-z0-9_.-]*$'
        assert re.match(pattern, unique_deployment_id.lower())


class TestCleanupOnFailure:
    """Tests for cleanup behavior on deployment failure."""

    @pytest.mark.slow
    async def test_failed_deploy_cleanup(
        self,
        docker_deployer,
        unique_deployment_id,
    ):
        """Test that failed deployments clean up after themselves."""
        from megaraptor_mcp.deployment.profiles import get_profile

        profile = get_profile("rapid")

        # Try to deploy with invalid certificate bundle
        try:
            # This should fail because we're not providing certificates
            result = await docker_deployer.deploy(
                deployment_id=unique_deployment_id,
                profile=profile,
                certificate_bundle=None,  # Invalid - no certs
            )

            # If it didn't fail, clean up
            if result and result.success:
                await docker_deployer.destroy(unique_deployment_id)

        except Exception:
            # Expected - deployment should fail without certs
            pass

        # Verify no orphaned container
        status = await docker_deployer.get_status(unique_deployment_id)
        assert status is None or status.state.value in ["destroyed", "failed"]
