"""End-to-end investigation workflow integration tests.

Validates DEPLOY-03: Full investigation workflow (triage to collection to analysis)
completes successfully against a live Velociraptor deployment.

This test validates the complete DFIR investigation workflow:
1. TRIAGE - Execute VQL query to get process list
2. COLLECT - Schedule and complete artifact collection
3. ANALYZE - Retrieve and validate results

Uses existing test infrastructure (docker-compose.test.yml), NOT a new deployment.
"""

import logging
import pytest

from tests.integration.helpers.wait_helpers import wait_for_flow_completion


logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.slow
class TestInvestigationWorkflowE2E:
    """End-to-end tests for complete DFIR investigation workflow.

    Validates that triage -> collect -> analyze workflow completes successfully
    against a deployed Velociraptor server (DEPLOY-03).
    """

    def test_full_investigation_workflow(
        self,
        docker_compose_up,
        velociraptor_client,
        enrolled_client_id,
    ):
        """DEPLOY-03: Full investigation workflow completes successfully.

        This test validates the complete DFIR investigation workflow:

        Phase 1 - TRIAGE:
            Execute VQL query to get initial process list for threat assessment.

        Phase 2 - COLLECT:
            Schedule artifact collection and wait for completion.

        Phase 3 - ANALYZE:
            Retrieve flow results and validate expected data structure.

        The workflow mirrors how a DFIR analyst would use Velociraptor:
        1. Quick triage via VQL to assess threat landscape
        2. Collect detailed artifacts for evidence preservation
        3. Analyze collected data for indicators

        Requires:
            - docker_compose_up: Ensures test infrastructure is running
            - velociraptor_client: Connected client for VQL queries
            - enrolled_client_id: Target client for investigation
        """
        flow_id = None

        try:
            # ================================================================
            # Phase 1: TRIAGE - Quick client assessment via VQL
            # ================================================================
            logger.info("=== PHASE 1: TRIAGE ===")
            logger.info(f"Target client: {enrolled_client_id}")

            # For triage, query the clients() table for quick assessment
            # This is server-side VQL that provides immediate client metadata
            # Note: pslist() is a client-side plugin that requires artifact collection
            # Real DFIR triage starts with client info before detailed collection
            triage_vql = f"""
            SELECT client_id, os_info, agent_information, last_seen_at
            FROM clients(client_id='{enrolled_client_id}')
            """

            triage_results = velociraptor_client.query(triage_vql)

            # Validate triage results
            assert triage_results is not None, "Triage query returned None"
            assert len(triage_results) > 0, "Triage query returned no client info"

            # Verify expected fields in triage data
            triage_data = triage_results[0]
            client_id_found = "client_id" in triage_data
            os_found = "os_info" in triage_data or any(
                k in triage_data for k in ["system", "platform", "OS"]
            )

            assert client_id_found, f"Triage: Missing client_id. Available: {list(triage_data.keys())}"
            assert os_found, f"Triage: Missing os_info field. Available: {list(triage_data.keys())}"

            # Extract OS info for logging
            os_info = triage_data.get("os_info", {})
            os_name = os_info.get("system", "Unknown") if isinstance(os_info, dict) else "Unknown"

            logger.info(f"TRIAGE COMPLETE: Client {enrolled_client_id}")
            logger.info(f"OS: {os_name}, Agent: {triage_data.get('agent_information', {})}")

            # ================================================================
            # Phase 2: COLLECT - Schedule artifact collection
            # ================================================================
            logger.info("=== PHASE 2: COLLECT ===")

            # Collect both client info AND process list for comprehensive investigation
            # - Generic.Client.Info: System metadata
            # - Linux.Sys.Pslist: Process list (satisfies DEPLOY-03 process list requirement)
            collect_vql = f"""
            SELECT collect_client(
                client_id='{enrolled_client_id}',
                artifacts=['Generic.Client.Info', 'Linux.Sys.Pslist'],
                timeout=60
            ) AS collection
            FROM scope()
            """

            collect_result = velociraptor_client.query(collect_vql)

            # Validate collection was scheduled
            assert len(collect_result) > 0, "collect_client returned no results"
            assert "collection" in collect_result[0], "Missing 'collection' field in response"

            collection = collect_result[0]["collection"]
            assert "flow_id" in collection, "Missing 'flow_id' in collection response"

            flow_id = collection["flow_id"]
            logger.info(f"Collection scheduled: flow_id={flow_id}")
            logger.info("Artifacts: Generic.Client.Info, Linux.Sys.Pslist")

            # Wait for flow completion
            logger.info("Waiting for artifact collection to complete...")
            try:
                wait_for_flow_completion(
                    velociraptor_client,
                    enrolled_client_id,
                    flow_id,
                    timeout=60,
                    poll_interval=2,
                )
                logger.info("Collection completed successfully")
            except TimeoutError as e:
                pytest.fail(f"COLLECT phase failed: Artifact collection timed out after 60s - {e}")
            except RuntimeError as e:
                pytest.fail(f"COLLECT phase failed: Flow error - {e}")

            # ================================================================
            # Phase 3: ANALYZE - Retrieve and validate results
            # ================================================================
            logger.info("=== PHASE 3: ANALYZE ===")

            # 3a. Analyze client info results
            logger.info("Analyzing Generic.Client.Info results...")
            client_info_vql = f"""
            SELECT * FROM source(
                client_id='{enrolled_client_id}',
                flow_id='{flow_id}',
                artifact='Generic.Client.Info',
                source='BasicInformation'
            )
            """

            client_info_results = velociraptor_client.query(client_info_vql)

            # Validate client info results
            assert client_info_results is not None, "Client info query returned None"
            assert len(client_info_results) > 0, "Client info query returned no results"

            # Validate expected client info fields
            client_info = client_info_results[0]

            # Check for critical fields (field names vary by version)
            hostname_found = any(k in client_info for k in ["Hostname", "hostname", "Fqdn", "fqdn"])
            os_found = any(k in client_info for k in ["OS", "os", "System", "Platform", "platform"])

            assert hostname_found, f"ANALYZE: Missing hostname field. Available: {list(client_info.keys())}"
            assert os_found, f"ANALYZE: Missing OS field. Available: {list(client_info.keys())}"

            hostname_key = next((k for k in ["Hostname", "hostname", "Fqdn", "fqdn"] if k in client_info), None)
            logger.info(f"Client hostname: {client_info.get(hostname_key, 'N/A')}")

            # 3b. Analyze process list results (DEPLOY-03: process list requirement)
            logger.info("Analyzing Linux.Sys.Pslist results...")
            pslist_vql = f"""
            SELECT * FROM source(
                client_id='{enrolled_client_id}',
                flow_id='{flow_id}',
                artifact='Linux.Sys.Pslist'
            )
            """

            pslist_results = velociraptor_client.query(pslist_vql)

            # Validate process list results
            assert pslist_results is not None, "Process list query returned None"
            assert len(pslist_results) > 0, "Process list query returned no processes"

            # Validate expected process fields (Pid, Name, CommandLine)
            first_process = pslist_results[0]
            pid_found = any(k in first_process for k in ["Pid", "PID", "pid"])
            name_found = any(k in first_process for k in ["Name", "name", "Exe", "exe"])
            cmdline_found = any(k in first_process for k in [
                "CommandLine", "command_line", "Cmdline", "cmdline", "Commandline"
            ])

            assert pid_found, f"ANALYZE: Missing PID field. Available: {list(first_process.keys())}"
            assert name_found, f"ANALYZE: Missing Name field. Available: {list(first_process.keys())}"
            # CommandLine may be empty for some processes, but field should exist
            assert cmdline_found, f"ANALYZE: Missing CommandLine field. Available: {list(first_process.keys())}"

            logger.info(f"Process list: {len(pslist_results)} processes found")
            logger.info(f"Sample process: {first_process}")

            # ================================================================
            # Investigation Summary
            # ================================================================
            logger.info("=== INVESTIGATION COMPLETE ===")
            logger.info(f"TRIAGE: Client {enrolled_client_id} identified (OS: {os_name})")
            logger.info(f"COLLECT: flow_id={flow_id} completed (2 artifacts)")
            logger.info(f"ANALYZE: Client info ({len(client_info.keys())} fields) + Process list ({len(pslist_results)} processes)")

        finally:
            # Cleanup: Cancel any running flows
            if flow_id:
                try:
                    cancel_vql = f"""
                    SELECT cancel_flow(
                        client_id='{enrolled_client_id}',
                        flow_id='{flow_id}'
                    ) FROM scope()
                    """
                    velociraptor_client.query(cancel_vql)
                    logger.debug(f"Cleanup: Cancelled flow {flow_id}")
                except Exception as e:
                    # Ignore cleanup errors - flow may already be complete
                    logger.debug(f"Cleanup: Could not cancel flow {flow_id}: {e}")
