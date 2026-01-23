"""Tests for configuration handling."""

import os
import tempfile
import pytest
import yaml

from megaraptor_mcp.config import VelociraptorConfig, load_config


@pytest.mark.unit
class TestVelociraptorConfig:
    """Tests for VelociraptorConfig class."""

    def test_from_config_file(self, tmp_path):
        """Test loading config from a YAML file."""
        config_data = {
            "api_url": "https://velociraptor.example.com:8001",
            "ca_certificate": "-----BEGIN CERTIFICATE-----\ntest-ca\n-----END CERTIFICATE-----",
            "client_cert": "-----BEGIN CERTIFICATE-----\ntest-cert\n-----END CERTIFICATE-----",
            "client_private_key": "-----BEGIN PRIVATE KEY-----\ntest-key\n-----END PRIVATE KEY-----",
        }

        config_file = tmp_path / "api_client.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = VelociraptorConfig.from_config_file(str(config_file))

        assert config.api_url == "https://velociraptor.example.com:8001"
        assert "test-ca" in config.ca_cert
        assert "test-cert" in config.client_cert
        assert "test-key" in config.client_key

    def test_from_config_file_not_found(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            VelociraptorConfig.from_config_file("/nonexistent/path.yaml")

    def test_from_env(self, monkeypatch):
        """Test loading config from environment variables."""
        monkeypatch.setenv("VELOCIRAPTOR_API_URL", "https://velociraptor.example.com:8001")
        monkeypatch.setenv("VELOCIRAPTOR_CLIENT_CERT", "test-cert-content")
        monkeypatch.setenv("VELOCIRAPTOR_CLIENT_KEY", "test-key-content")
        monkeypatch.setenv("VELOCIRAPTOR_CA_CERT", "test-ca-content")

        config = VelociraptorConfig.from_env()

        assert config.api_url == "https://velociraptor.example.com:8001"
        assert config.client_cert == "test-cert-content"
        assert config.client_key == "test-key-content"
        assert config.ca_cert == "test-ca-content"

    def test_validate_missing_url(self):
        """Test validation fails without API URL."""
        config = VelociraptorConfig(
            api_url="",
            client_cert="cert",
            client_key="key",
            ca_cert="ca",
        )

        with pytest.raises(ValueError, match="API URL is required"):
            config.validate()

    def test_validate_success(self):
        """Test validation passes with all required fields."""
        config = VelociraptorConfig(
            api_url="https://velociraptor.example.com:8001",
            client_cert="cert",
            client_key="key",
            ca_cert="ca",
        )

        # Should not raise
        config.validate()


@pytest.mark.unit
class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_env_config_path(self, tmp_path, monkeypatch):
        """Test loading config via VELOCIRAPTOR_CONFIG_PATH."""
        config_data = {
            "api_url": "https://velociraptor.example.com:8001",
            "ca_certificate": "ca-cert",
            "client_cert": "client-cert",
            "client_private_key": "client-key",
        }

        config_file = tmp_path / "api_client.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("VELOCIRAPTOR_CONFIG_PATH", str(config_file))

        config = load_config()

        assert config.api_url == "https://velociraptor.example.com:8001"

    def test_load_no_config_raises(self, monkeypatch):
        """Test error when no configuration is available."""
        # Clear any existing env vars
        monkeypatch.delenv("VELOCIRAPTOR_CONFIG_PATH", raising=False)
        monkeypatch.delenv("VELOCIRAPTOR_API_URL", raising=False)
        monkeypatch.delenv("VELOCIRAPTOR_CLIENT_CERT", raising=False)
        monkeypatch.delenv("VELOCIRAPTOR_CLIENT_KEY", raising=False)
        monkeypatch.delenv("VELOCIRAPTOR_CA_CERT", raising=False)

        with pytest.raises(ValueError, match="No Velociraptor configuration found"):
            load_config()
