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
            # Phase 1: TRIAGE - Quick process enumeration via VQL
            # ================================================================
            logger.info("=== PHASE 1: TRIAGE ===")
            logger.info(f"Target client: {enrolled_client_id}")

            # Execute triage VQL query - get process list
            # pslist() is a client-side artifact, needs collect_client first
            # For quick triage, we use server-side VQL that runs on the client
            triage_vql = f"""
            SELECT Pid, Name, Exe, Cmdline
            FROM pslist(client_id='{enrolled_client_id}')
            """

            triage_results = velociraptor_client.query(triage_vql)

            # Validate triage results
            assert triage_results is not None, "Triage query returned None"
            assert len(triage_results) > 0, "Triage query returned no processes"

            # Verify expected fields in process data
            first_process = triage_results[0]
            pid_found = any(k in first_process for k in ["Pid", "PID", "pid"])
            name_found = any(k in first_process for k in ["Name", "name", "Exe", "exe"])

            assert pid_found, f"Triage: Missing PID field. Available: {list(first_process.keys())}"
            assert name_found, f"Triage: Missing Name field. Available: {list(first_process.keys())}"

            logger.info(f"TRIAGE COMPLETE: Found {len(triage_results)} processes")
            logger.info(f"Sample process: {first_process}")

            # ================================================================
            # Phase 2: COLLECT - Schedule artifact collection
            # ================================================================
            logger.info("=== PHASE 2: COLLECT ===")

            # Use Generic.Client.Info - quick, always available
            collect_vql = f"""
            SELECT collect_client(
                client_id='{enrolled_client_id}',
                artifacts=['Generic.Client.Info'],
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

            # Get flow results - use specific source for Generic.Client.Info
            analyze_vql = f"""
            SELECT * FROM source(
                client_id='{enrolled_client_id}',
                flow_id='{flow_id}',
                artifact='Generic.Client.Info',
                source='BasicInformation'
            )
            """

            analyze_results = velociraptor_client.query(analyze_vql)

            # Validate analysis results
            assert analyze_results is not None, "Analysis query returned None"
            assert len(analyze_results) > 0, "Analysis query returned no results"

            # Validate expected client info fields
            client_info = analyze_results[0]

            # Check for critical fields (field names vary by version)
            hostname_found = any(k in client_info for k in ["Hostname", "hostname", "Fqdn", "fqdn"])
            os_found = any(k in client_info for k in ["OS", "os", "System", "Platform", "platform"])

            assert hostname_found, f"ANALYZE: Missing hostname field. Available: {list(client_info.keys())}"
            assert os_found, f"ANALYZE: Missing OS field. Available: {list(client_info.keys())}"

            # Log analysis summary
            logger.info(f"ANALYZE COMPLETE: Retrieved {len(analyze_results)} result(s)")
            logger.info(f"Client info fields: {list(client_info.keys())}")

            # Get hostname value for summary
            hostname_key = next((k for k in ["Hostname", "hostname", "Fqdn", "fqdn"] if k in client_info), None)
            if hostname_key:
                logger.info(f"Hostname: {client_info[hostname_key]}")

            # ================================================================
            # Investigation Summary
            # ================================================================
            logger.info("=== INVESTIGATION COMPLETE ===")
            logger.info(f"TRIAGE: {len(triage_results)} processes found")
            logger.info(f"COLLECT: flow_id={flow_id} completed")
            logger.info(f"ANALYZE: {len(analyze_results)} result(s) with {len(client_info.keys())} fields")

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
