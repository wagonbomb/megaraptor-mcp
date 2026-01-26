# Test Fixtures

This directory contains configuration files for the Velociraptor test infrastructure.

## Required Files

The following files are required for integration tests but are NOT committed to git
(they contain secrets and are environment-specific):

- `server.config.yaml` - Velociraptor server configuration
- `client.config.yaml` - Velociraptor client configuration
- `api_client.yaml` - API client credentials for test connections

## Generating Configuration Files

Use the test lab script to generate these files:

```bash
# From WSL or Linux
./scripts/test-lab.sh generate-config

# Or manually with Docker
docker run --rm -v "$(pwd)/tests/fixtures:/output" velocidex/velociraptor:latest \
    config generate --merge_output /output
```

This will generate:
1. `server.config.yaml` - Full server configuration with embedded certificates
2. `client.config.yaml` - Client configuration extracted from server config

## API Client Configuration

After generating configs and starting the server, create API credentials:

```bash
# Start the test lab
./scripts/test-lab.sh up

# Generate API client config
docker exec vr-test-server velociraptor \
    --config /config/server.config.yaml \
    config api_client --name megaraptor-test \
    > tests/fixtures/api_client.yaml
```

## File Structure After Generation

```
fixtures/
├── README.md           # This file
├── .gitignore          # Ignores generated configs
├── server.config.yaml  # Generated - DO NOT COMMIT
├── client.config.yaml  # Generated - DO NOT COMMIT
└── api_client.yaml     # Generated - DO NOT COMMIT
```

## Security Notes

- Generated configs contain cryptographic keys and certificates
- Never commit these files to version control
- Delete fixtures before sharing the repository
- Use `./scripts/test-lab.sh clean` to remove all test artifacts

## Known-Good Test Datasets

The `baselines/` directory contains known-good artifact collection results used for forensic validation testing. These baselines serve as reference data to verify that artifact collection produces consistent, correct output across different environments and Velociraptor versions.

### Purpose

Baseline fixtures enable:
- Hash validation (QUAL-01): Verify artifact collections produce expected output
- VQL correctness testing (QUAL-04): Validate VQL queries return correct data
- Regression detection: Catch unintended changes in artifact behavior
- Version compatibility testing: Ensure artifacts work across Velociraptor versions

### Available Baselines

#### linux_sys_users.json

**Artifact:** Linux.Sys.Users
**Purpose:** Validates user enumeration on Linux systems
**Critical fields:** User, Uid, Gid
**Expected users:** root (uid 0), nobody (uid 65534), and container-specific users
**Test conditions:**
- OS: Ubuntu 22.04 Docker container
- Velociraptor version: 0.75.x
- Collection method: collect_client with Linux.Sys.Users artifact

**Use case:** Verify Linux user enumeration returns expected system users with correct UIDs and GIDs. Essential for validating that basic OS artifact collection works correctly.

#### generic_client_info.json

**Artifact:** Generic.Client.Info
**Purpose:** Validates cross-platform client information collection
**Critical fields:** Hostname, OS
**Test conditions:**
- OS: Any (cross-platform artifact)
- Velociraptor version: 0.75.x
- Collection method: collect_client with Generic.Client.Info artifact

**Use case:** Verify client info collection works across operating systems. Generic.Client.Info is the most basic artifact and should always work regardless of platform.

### Baseline Update Procedure

When updating or adding baseline fixtures:

1. **Collect in controlled environment**: Run artifact collection in a known, stable environment (test lab container)

2. **Manually verify correctness**: Compare collected data against the source system to ensure accuracy
   - For Linux.Sys.Users: Verify against `/etc/passwd`
   - For Generic.Client.Info: Verify against `hostname`, `uname -a`

3. **Compute SHA-256 hash**: Use baseline_helpers.compute_forensic_hash() to generate hash
   ```python
   from tests.integration.helpers.baseline_helpers import compute_forensic_hash
   import json

   with open('tests/fixtures/baselines/linux_sys_users.json') as f:
       data = json.load(f)

   hash_value = compute_forensic_hash(data)
   print(f"SHA-256: {hash_value}")
   ```

4. **Document test conditions**: Update metadata.json with:
   - OS version and platform
   - Velociraptor version used
   - Collection method and parameters
   - Any special environment conditions

5. **Update baseline file**: Replace placeholder baseline with verified data

6. **Update metadata**: Add computed hash to metadata.json for the artifact

### Hash Verification

Baselines use deterministic SHA-256 hashing for validation:
- JSON is normalized (sorted keys, consistent separators) before hashing
- Same data produces same hash regardless of key order or formatting
- Hashes are stored in `metadata.json` for automated validation

### Current Status

Initial baselines are placeholders (empty arrays). They will be populated when tests run against the live test lab environment and manually verified before committing. This ensures baselines represent actual, verified artifact output rather than synthetic test data.
