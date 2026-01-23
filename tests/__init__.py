"""Tests for Megaraptor MCP.

Test Structure:
    tests/
    ├── conftest.py          # Shared pytest fixtures
    ├── unit/                # Unit tests (no external deps)
    │   ├── test_config.py
    │   ├── test_certificate_manager.py
    │   ├── test_credential_store.py
    │   └── test_profiles.py
    ├── integration/         # Integration tests (requires Docker)
    │   ├── test_dfir_tools.py
    │   └── test_docker_deployment.py
    ├── mocks/               # Mock implementations
    │   └── mock_velociraptor.py
    └── fixtures/            # Test configuration files

Usage:
    # Run all tests
    pytest

    # Run only unit tests
    pytest -m unit

    # Run only integration tests (requires Docker)
    pytest -m integration

    # Run with verbose output
    pytest -v

See scripts/test-lab.sh for managing the test infrastructure.
"""
