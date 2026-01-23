#!/bin/bash
# Test Lab Management Script for megaraptor-mcp
#
# This script manages the Docker test infrastructure for integration tests.
# It should be run from WSL2 or a Linux environment with Docker installed.
#
# Usage:
#   ./scripts/test-lab.sh [command]
#
# Commands:
#   up            - Start the test infrastructure
#   down          - Stop the test infrastructure (preserves data)
#   clean         - Stop and remove all test data
#   logs          - Follow container logs
#   status        - Show container status
#   generate-config - Generate Velociraptor configuration files
#   shell         - Open shell in Velociraptor server container
#   api-client    - Generate API client credentials
#   test          - Run the test suite
#   test-unit     - Run only unit tests
#   test-integration - Run only integration tests

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/tests/docker-compose.test.yml"
FIXTURES_DIR="$PROJECT_ROOT/tests/fixtures"
SERVER_CONFIG="$FIXTURES_DIR/server.config.yaml"
CLIENT_CONFIG="$FIXTURES_DIR/client.config.yaml"
API_CLIENT_CONFIG="$FIXTURES_DIR/api_client.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

check_configs() {
    if [[ ! -f "$SERVER_CONFIG" ]] || [[ ! -f "$CLIENT_CONFIG" ]]; then
        log_warn "Velociraptor configs not found. Run 'generate-config' first."
        return 1
    fi
    return 0
}

cmd_up() {
    check_docker

    if ! check_configs; then
        log_info "Generating configuration files..."
        cmd_generate_config
    fi

    log_info "Starting test infrastructure..."
    docker compose -f "$COMPOSE_FILE" up -d

    log_info "Waiting for Velociraptor server to be ready..."
    local retries=30
    local count=0

    while [[ $count -lt $retries ]]; do
        if docker compose -f "$COMPOSE_FILE" ps | grep -q "healthy"; then
            log_info "Velociraptor server is ready!"
            break
        fi
        sleep 2
        count=$((count + 1))
        echo -n "."
    done
    echo ""

    if [[ $count -eq $retries ]]; then
        log_warn "Server may not be fully ready. Check logs with: $0 logs"
    fi

    cmd_status
}

cmd_down() {
    check_docker
    log_info "Stopping test infrastructure..."
    docker compose -f "$COMPOSE_FILE" down
    log_info "Infrastructure stopped."
}

cmd_clean() {
    check_docker
    log_info "Stopping and cleaning test infrastructure..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans

    log_info "Removing generated configuration files..."
    rm -f "$SERVER_CONFIG" "$CLIENT_CONFIG" "$API_CLIENT_CONFIG"

    log_info "Cleanup complete."
}

cmd_logs() {
    check_docker
    docker compose -f "$COMPOSE_FILE" logs -f
}

cmd_status() {
    check_docker
    echo ""
    echo "Container Status:"
    echo "================="
    docker compose -f "$COMPOSE_FILE" ps
    echo ""

    # Check if server is accessible
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "vr-test-server.*Up"; then
        log_info "Server is running"
        log_info "GUI available at: https://localhost:8889"
        log_info "API available at: https://localhost:8001"
    else
        log_warn "Server is not running"
    fi
}

cmd_generate_config() {
    check_docker

    log_info "Generating Velociraptor configuration..."
    mkdir -p "$FIXTURES_DIR"

    # Generate server config
    docker run --rm velocidex/velociraptor:latest \
        config generate \
        --merge '{"Frontend": {"hostname": "localhost", "bind_address": "0.0.0.0"}, "GUI": {"bind_address": "0.0.0.0"}, "API": {"bind_address": "0.0.0.0"}}' \
        > "$SERVER_CONFIG"

    if [[ ! -s "$SERVER_CONFIG" ]]; then
        log_error "Failed to generate server config"
        exit 1
    fi

    log_info "Server config generated: $SERVER_CONFIG"

    # Extract client config from server config
    docker run --rm -v "$FIXTURES_DIR:/config" velocidex/velociraptor:latest \
        config client --config /config/server.config.yaml \
        > "$CLIENT_CONFIG"

    if [[ ! -s "$CLIENT_CONFIG" ]]; then
        log_error "Failed to generate client config"
        exit 1
    fi

    log_info "Client config generated: $CLIENT_CONFIG"

    # Update client config to point to Docker hostname
    if command -v sed &> /dev/null; then
        # Replace localhost with velociraptor-server (Docker network hostname)
        sed -i 's/localhost:8000/velociraptor-server:8000/g' "$CLIENT_CONFIG" 2>/dev/null || true
    fi

    log_info "Configuration files generated successfully!"
}

cmd_shell() {
    check_docker
    log_info "Opening shell in Velociraptor server container..."
    docker exec -it vr-test-server /bin/sh
}

cmd_api_client() {
    check_docker

    if ! docker compose -f "$COMPOSE_FILE" ps | grep -q "vr-test-server.*Up"; then
        log_error "Server is not running. Start with: $0 up"
        exit 1
    fi

    log_info "Generating API client credentials..."

    docker exec vr-test-server velociraptor \
        --config /config/server.config.yaml \
        config api_client \
        --name "megaraptor-test-$(date +%s)" \
        --role administrator \
        > "$API_CLIENT_CONFIG"

    if [[ ! -s "$API_CLIENT_CONFIG" ]]; then
        log_error "Failed to generate API client config"
        exit 1
    fi

    log_info "API client config generated: $API_CLIENT_CONFIG"
}

cmd_test() {
    log_info "Running full test suite..."

    # Ensure infrastructure is up
    if ! docker compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -q "Up"; then
        log_info "Starting test infrastructure..."
        cmd_up
    fi

    cd "$PROJECT_ROOT"
    python -m pytest tests/ -v "$@"
}

cmd_test_unit() {
    log_info "Running unit tests..."
    cd "$PROJECT_ROOT"
    python -m pytest tests/unit -v -m "unit" "$@"
}

cmd_test_integration() {
    log_info "Running integration tests..."

    # Ensure infrastructure is up
    if ! docker compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -q "Up"; then
        log_info "Starting test infrastructure..."
        cmd_up
    fi

    cd "$PROJECT_ROOT"
    python -m pytest tests/integration -v -m "integration" "$@"
}

show_help() {
    echo "Megaraptor MCP Test Lab"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  up              Start the test infrastructure"
    echo "  down            Stop the test infrastructure"
    echo "  clean           Stop and remove all test data"
    echo "  logs            Follow container logs"
    echo "  status          Show container status"
    echo "  generate-config Generate Velociraptor configs"
    echo "  shell           Open shell in server container"
    echo "  api-client      Generate API client credentials"
    echo "  test            Run full test suite"
    echo "  test-unit       Run unit tests only"
    echo "  test-integration Run integration tests only"
    echo "  help            Show this help message"
    echo ""
    echo "Example workflow:"
    echo "  $0 generate-config  # Generate Velociraptor configs"
    echo "  $0 up               # Start containers"
    echo "  $0 api-client       # Generate API credentials"
    echo "  $0 test             # Run tests"
    echo "  $0 clean            # Cleanup when done"
}

# Main command dispatch
case "${1:-}" in
    up)
        cmd_up
        ;;
    down)
        cmd_down
        ;;
    clean)
        cmd_clean
        ;;
    logs)
        cmd_logs
        ;;
    status)
        cmd_status
        ;;
    generate-config)
        cmd_generate_config
        ;;
    shell)
        cmd_shell
        ;;
    api-client)
        cmd_api_client
        ;;
    test)
        shift
        cmd_test "$@"
        ;;
    test-unit)
        shift
        cmd_test_unit "$@"
        ;;
    test-integration)
        shift
        cmd_test_integration "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
