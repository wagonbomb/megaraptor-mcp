"""Cleanup helpers for Velociraptor test entities.

These helpers remove test-created entities (hunts, labels) to prevent
state pollution between tests.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from megaraptor_mcp.client import VelociraptorClient


def cleanup_test_hunts(
    client: "VelociraptorClient",
    test_prefix: str = "TEST-"
) -> List[str]:
    """Archive hunts with test prefix in description.

    Velociraptor doesn't support hunt deletion, so we archive them instead.

    Args:
        client: VelociraptorClient instance
        test_prefix: Prefix to match in hunt_description (default "TEST-")

    Returns:
        List of hunt IDs that were archived
    """
    archived = []

    try:
        # Find hunts with TEST- prefix in description
        test_hunts = client.query(
            f"SELECT hunt_id, hunt_description FROM hunts() "
            f"WHERE hunt_description =~ '{test_prefix}'"
        )

        for hunt in test_hunts:
            hunt_id = hunt.get("hunt_id")
            if hunt_id:
                # Archive the hunt
                client.query(
                    f"SELECT modify_hunt(hunt_id='{hunt_id}', state='ARCHIVED') "
                    f"FROM scope()"
                )
                archived.append(hunt_id)

    except Exception as e:
        # Log but don't fail - cleanup is best-effort
        print(f"Hunt cleanup warning: {e}")

    return archived


def cleanup_test_labels(
    client: "VelociraptorClient",
    label_prefix: str = "TEST-"
) -> List[str]:
    """Remove labels with test prefix from all clients.

    Args:
        client: VelociraptorClient instance
        label_prefix: Prefix to match in labels (default "TEST-")

    Returns:
        List of client IDs that had labels removed
    """
    cleaned = []

    try:
        # Find clients with TEST- prefixed labels
        # Note: VQL array membership check syntax
        labeled_clients = client.query(
            "SELECT client_id, labels FROM clients()"
        )

        for client_data in labeled_clients:
            client_id = client_data.get("client_id")
            labels = client_data.get("labels", [])

            if not client_id or not labels:
                continue

            # Find and remove TEST- prefixed labels
            test_labels = [
                label for label in labels
                if isinstance(label, str) and label.startswith(label_prefix)
            ]

            for label in test_labels:
                client.query(
                    f"SELECT label(client_id='{client_id}', "
                    f"op='remove', labels='{label}') FROM scope()"
                )

            if test_labels:
                cleaned.append(client_id)

    except Exception as e:
        # Log but don't fail - cleanup is best-effort
        print(f"Label cleanup warning: {e}")

    return cleaned


def cleanup_test_flows(
    client: "VelociraptorClient",
    client_id: str,
    flow_prefix: str = "TEST-"
) -> List[str]:
    """Cancel or mark test flows as archived.

    Args:
        client: VelociraptorClient instance
        client_id: Client ID to cleanup flows for
        flow_prefix: Prefix in flow name/artifact (default "TEST-")

    Returns:
        List of flow IDs that were cleaned up

    Note: Flow cleanup is limited - Velociraptor doesn't support flow deletion.
    This function is provided for documentation/future use.
    """
    # Flows cannot be deleted in Velociraptor, only cancelled if running
    # This is a placeholder for future cleanup patterns
    cleaned = []

    try:
        # Query flows for the client
        flows = client.query(
            f"SELECT flow_id, state FROM flows(client_id='{client_id}') "
            f"WHERE state = 'RUNNING'"
        )

        for flow in flows:
            flow_id = flow.get("flow_id")
            if flow_id:
                # Cancel running flows
                client.query(
                    f"SELECT cancel_flow(client_id='{client_id}', "
                    f"flow_id='{flow_id}') FROM scope()"
                )
                cleaned.append(flow_id)

    except Exception as e:
        print(f"Flow cleanup warning: {e}")

    return cleaned
