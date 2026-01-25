"""Wait helpers for async Velociraptor operations.

These helpers poll Velociraptor for operation completion to avoid
race conditions in integration tests.
"""

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from megaraptor_mcp.client import VelociraptorClient


def wait_for_flow_completion(
    client: "VelociraptorClient",
    client_id: str,
    flow_id: str,
    timeout: int = 60,
    poll_interval: int = 2
) -> bool:
    """Wait for a Velociraptor flow to complete.

    Polls the flow status using VQL until it reaches FINISHED state,
    times out, or fails with ERROR state.

    Args:
        client: VelociraptorClient instance
        client_id: Client ID (e.g., "C.123...")
        flow_id: Flow ID (e.g., "F.456...")
        timeout: Maximum wait time in seconds (default 60)
        poll_interval: Time between status checks in seconds (default 2)

    Returns:
        True if flow completed successfully

    Raises:
        TimeoutError: If flow doesn't complete within timeout
        RuntimeError: If flow reaches ERROR state
    """
    start = time.time()

    while time.time() - start < timeout:
        # Query flow status using VQL
        status = client.query(
            f"SELECT state FROM flows(client_id='{client_id}', flow_id='{flow_id}')"
        )

        if status and len(status) > 0:
            state = status[0].get("state", "")
            if state == "FINISHED":
                return True
            elif state == "ERROR":
                raise RuntimeError(f"Flow {flow_id} failed with ERROR state")

        time.sleep(poll_interval)

    raise TimeoutError(f"Flow {flow_id} did not complete within {timeout}s")


def wait_for_client_enrollment(
    client: "VelociraptorClient",
    timeout: int = 60,
    poll_interval: int = 5,
    min_clients: int = 1
) -> str:
    """Wait for at least one Velociraptor client to enroll.

    Polls the clients table until at least min_clients are enrolled.

    Args:
        client: VelociraptorClient instance
        timeout: Maximum wait time in seconds (default 60)
        poll_interval: Time between checks in seconds (default 5)
        min_clients: Minimum number of clients required (default 1)

    Returns:
        Client ID of the first enrolled client

    Raises:
        TimeoutError: If no clients enroll within timeout
    """
    start = time.time()

    while time.time() - start < timeout:
        clients = client.query("SELECT client_id FROM clients() LIMIT 10")

        if len(clients) >= min_clients:
            return clients[0]["client_id"]

        time.sleep(poll_interval)

    raise TimeoutError(f"No clients enrolled within {timeout}s timeout")


def wait_for_hunt_completion(
    client: "VelociraptorClient",
    hunt_id: str,
    timeout: int = 120,
    poll_interval: int = 5
) -> bool:
    """Wait for a hunt to complete (all scheduled clients finished).

    Args:
        client: VelociraptorClient instance
        hunt_id: Hunt ID (e.g., "H.123...")
        timeout: Maximum wait time in seconds (default 120)
        poll_interval: Time between checks in seconds (default 5)

    Returns:
        True if hunt completed

    Raises:
        TimeoutError: If hunt doesn't complete within timeout
    """
    start = time.time()

    while time.time() - start < timeout:
        status = client.query(
            f"SELECT stats FROM hunts(hunt_id='{hunt_id}')"
        )

        if status and len(status) > 0:
            stats = status[0].get("stats", {})
            # Hunt complete when all scheduled clients have finished
            total = stats.get("total_clients_scheduled", 0)
            completed = stats.get("total_clients_with_results", 0)
            if total > 0 and completed >= total:
                return True

        time.sleep(poll_interval)

    raise TimeoutError(f"Hunt {hunt_id} did not complete within {timeout}s")
