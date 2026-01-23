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
