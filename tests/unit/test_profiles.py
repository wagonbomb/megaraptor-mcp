"""Tests for deployment profiles."""

import pytest

from megaraptor_mcp.deployment.profiles import (
    DeploymentTarget,
    DeploymentState,
    DeploymentProfile,
    PROFILES,
    get_profile,
)


@pytest.mark.unit
class TestDeploymentTarget:
    """Tests for DeploymentTarget enum."""

    def test_all_targets_defined(self):
        """Test that all expected targets are defined."""
        assert DeploymentTarget.DOCKER.value == "docker"
        assert DeploymentTarget.BINARY.value == "binary"
        assert DeploymentTarget.AWS.value == "aws"
        assert DeploymentTarget.AZURE.value == "azure"

    def test_target_count(self):
        """Test total number of deployment targets."""
        targets = list(DeploymentTarget)
        assert len(targets) == 4


@pytest.mark.unit
class TestDeploymentState:
    """Tests for DeploymentState enum."""

    def test_all_states_defined(self):
        """Test that all expected states are defined."""
        assert DeploymentState.PENDING.value == "pending"
        assert DeploymentState.PROVISIONING.value == "provisioning"
        assert DeploymentState.RUNNING.value == "running"
        assert DeploymentState.STOPPING.value == "stopping"
        assert DeploymentState.STOPPED.value == "stopped"
        assert DeploymentState.FAILED.value == "failed"
        assert DeploymentState.DESTROYED.value == "destroyed"

    def test_state_count(self):
        """Test total number of deployment states."""
        states = list(DeploymentState)
        assert len(states) == 7


@pytest.mark.unit
class TestDeploymentProfile:
    """Tests for DeploymentProfile dataclass."""

    def test_default_values(self):
        """Test profile is created with sensible defaults."""
        profile = DeploymentProfile(
            name="test",
            description="Test profile",
        )

        assert profile.name == "test"
        assert profile.description == "Test profile"
        assert profile.auto_destroy_hours is None
        assert profile.default_target == DeploymentTarget.DOCKER
        assert profile.allowed_targets == []
        assert profile.max_clients is None
        assert profile.enable_monitoring is True
        assert profile.enable_ssl_pinning is True
        assert profile.credential_expiry_hours is None
        assert profile.log_retention_days == 30
        assert profile.resource_limits == {}

    def test_allows_target_when_allowed(self):
        """Test allows_target returns True for allowed targets."""
        profile = DeploymentProfile(
            name="test",
            description="Test",
            allowed_targets=[DeploymentTarget.DOCKER, DeploymentTarget.AWS],
        )

        assert profile.allows_target(DeploymentTarget.DOCKER) is True
        assert profile.allows_target(DeploymentTarget.AWS) is True

    def test_allows_target_when_not_allowed(self):
        """Test allows_target returns False for disallowed targets."""
        profile = DeploymentProfile(
            name="test",
            description="Test",
            allowed_targets=[DeploymentTarget.DOCKER],
        )

        assert profile.allows_target(DeploymentTarget.BINARY) is False
        assert profile.allows_target(DeploymentTarget.AWS) is False
        assert profile.allows_target(DeploymentTarget.AZURE) is False

    def test_allows_target_empty_list(self):
        """Test allows_target with empty allowed list."""
        profile = DeploymentProfile(
            name="test",
            description="Test",
            allowed_targets=[],
        )

        assert profile.allows_target(DeploymentTarget.DOCKER) is False

    def test_custom_resource_limits(self):
        """Test profile with custom resource limits."""
        profile = DeploymentProfile(
            name="custom",
            description="Custom profile",
            resource_limits={
                "memory": "16g",
                "cpus": "8",
                "disk": "100g",
            },
        )

        assert profile.resource_limits["memory"] == "16g"
        assert profile.resource_limits["cpus"] == "8"
        assert profile.resource_limits["disk"] == "100g"


@pytest.mark.unit
class TestPredefinedProfiles:
    """Tests for predefined PROFILES dictionary."""

    def test_all_profiles_exist(self):
        """Test that all expected profiles are defined."""
        assert "rapid" in PROFILES
        assert "standard" in PROFILES
        assert "enterprise" in PROFILES

    def test_profile_count(self):
        """Test total number of predefined profiles."""
        assert len(PROFILES) == 3

    def test_rapid_profile(self):
        """Test rapid profile configuration."""
        rapid = PROFILES["rapid"]

        assert rapid.name == "rapid"
        assert rapid.auto_destroy_hours == 72
        assert rapid.default_target == DeploymentTarget.DOCKER
        assert rapid.allowed_targets == [DeploymentTarget.DOCKER]
        assert rapid.max_clients == 500
        assert rapid.credential_expiry_hours == 72
        assert rapid.log_retention_days == 7
        assert rapid.resource_limits["memory"] == "4g"
        assert rapid.resource_limits["cpus"] == "2"

    def test_rapid_only_allows_docker(self):
        """Test rapid profile only allows Docker deployment."""
        rapid = PROFILES["rapid"]

        assert rapid.allows_target(DeploymentTarget.DOCKER) is True
        assert rapid.allows_target(DeploymentTarget.BINARY) is False
        assert rapid.allows_target(DeploymentTarget.AWS) is False
        assert rapid.allows_target(DeploymentTarget.AZURE) is False

    def test_standard_profile(self):
        """Test standard profile configuration."""
        standard = PROFILES["standard"]

        assert standard.name == "standard"
        assert standard.auto_destroy_hours is None
        assert standard.default_target == DeploymentTarget.DOCKER
        assert standard.max_clients == 2000
        assert standard.credential_expiry_hours is None
        assert standard.log_retention_days == 30
        assert standard.resource_limits["memory"] == "8g"
        assert standard.resource_limits["cpus"] == "4"

    def test_standard_allows_all_targets(self):
        """Test standard profile allows all deployment targets."""
        standard = PROFILES["standard"]

        assert standard.allows_target(DeploymentTarget.DOCKER) is True
        assert standard.allows_target(DeploymentTarget.BINARY) is True
        assert standard.allows_target(DeploymentTarget.AWS) is True
        assert standard.allows_target(DeploymentTarget.AZURE) is True

    def test_enterprise_profile(self):
        """Test enterprise profile configuration."""
        enterprise = PROFILES["enterprise"]

        assert enterprise.name == "enterprise"
        assert enterprise.auto_destroy_hours is None
        assert enterprise.default_target == DeploymentTarget.BINARY
        assert enterprise.max_clients is None  # Unlimited
        assert enterprise.credential_expiry_hours is None
        assert enterprise.log_retention_days == 90
        assert enterprise.resource_limits["memory"] == "16g"
        assert enterprise.resource_limits["cpus"] == "8"

    def test_enterprise_excludes_docker(self):
        """Test enterprise profile excludes Docker (production use)."""
        enterprise = PROFILES["enterprise"]

        assert enterprise.allows_target(DeploymentTarget.DOCKER) is False
        assert enterprise.allows_target(DeploymentTarget.BINARY) is True
        assert enterprise.allows_target(DeploymentTarget.AWS) is True
        assert enterprise.allows_target(DeploymentTarget.AZURE) is True

    def test_all_profiles_have_monitoring_enabled(self):
        """Test all profiles have monitoring enabled."""
        for profile in PROFILES.values():
            assert profile.enable_monitoring is True

    def test_all_profiles_have_ssl_pinning_enabled(self):
        """Test all profiles have SSL pinning enabled."""
        for profile in PROFILES.values():
            assert profile.enable_ssl_pinning is True


@pytest.mark.unit
class TestGetProfile:
    """Tests for get_profile function."""

    def test_get_valid_profiles(self):
        """Test getting valid profile names."""
        for name in ["rapid", "standard", "enterprise"]:
            profile = get_profile(name)
            assert profile.name == name

    def test_get_invalid_profile_raises(self):
        """Test getting invalid profile raises ValueError."""
        with pytest.raises(ValueError, match="Unknown profile 'invalid'"):
            get_profile("invalid")

    def test_error_message_includes_available_profiles(self):
        """Test error message includes list of available profiles."""
        with pytest.raises(ValueError) as exc_info:
            get_profile("nonexistent")

        error_msg = str(exc_info.value)
        assert "rapid" in error_msg
        assert "standard" in error_msg
        assert "enterprise" in error_msg

    def test_get_profile_returns_same_instance(self):
        """Test get_profile returns same instance (not a copy)."""
        profile1 = get_profile("standard")
        profile2 = get_profile("standard")

        assert profile1 is profile2
