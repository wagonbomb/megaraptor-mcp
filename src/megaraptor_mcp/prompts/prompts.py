"""
MCP Prompts for DFIR workflows.

Provides pre-built prompts for common digital forensics and incident response workflows.
"""

from mcp.server import Server
from mcp.types import Prompt, PromptArgument, PromptMessage, TextContent


def register_prompts(server: Server) -> None:
    """Register DFIR workflow prompts with the MCP server."""

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """List available DFIR workflow prompts."""
        return [
            Prompt(
                name="investigate_endpoint",
                description="Start a comprehensive investigation on a specific endpoint. Guides through system interrogation, process analysis, network connections, and persistence mechanisms.",
                arguments=[
                    PromptArgument(
                        name="client_id",
                        description="The Velociraptor client ID (e.g., C.1234567890abcdef) or hostname to investigate",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="threat_hunt",
                description="Create and execute a threat hunting campaign across multiple endpoints. Helps build hunts for specific IOCs, TTPs, or suspicious behaviors.",
                arguments=[
                    PromptArgument(
                        name="indicators",
                        description="Indicators of compromise (IOCs) or behaviors to hunt for",
                        required=True,
                    ),
                    PromptArgument(
                        name="hunt_type",
                        description="Type of hunt: 'file', 'process', 'network', 'registry', 'persistence', or 'custom'",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="triage_incident",
                description="Rapid incident triage workflow. Quickly collects critical forensic artifacts for initial assessment and scoping.",
                arguments=[
                    PromptArgument(
                        name="client_id",
                        description="The Velociraptor client ID of the affected endpoint",
                        required=True,
                    ),
                    PromptArgument(
                        name="incident_type",
                        description="Type of incident: 'malware', 'intrusion', 'data_exfil', 'ransomware', or 'unknown'",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="malware_analysis",
                description="Analyze potentially malicious files or processes. Guides through file analysis, process inspection, and behavioral indicators.",
                arguments=[
                    PromptArgument(
                        name="client_id",
                        description="The Velociraptor client ID where the suspected malware exists",
                        required=True,
                    ),
                    PromptArgument(
                        name="target",
                        description="File path or process name to analyze",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="lateral_movement",
                description="Detect and investigate lateral movement indicators. Checks for RDP, SMB, WMI, PowerShell remoting, and other lateral movement techniques.",
                arguments=[
                    PromptArgument(
                        name="scope",
                        description="Investigation scope: specific client_id, 'label:xxx' for labeled clients, or 'all' for enterprise-wide",
                        required=True,
                    ),
                    PromptArgument(
                        name="timeframe",
                        description="Time range to investigate (e.g., '24h', '7d', '30d')",
                        required=False,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> list[PromptMessage]:
        """Get a specific DFIR workflow prompt."""
        arguments = arguments or {}

        if name == "investigate_endpoint":
            return _get_investigate_endpoint_prompt(arguments)
        elif name == "threat_hunt":
            return _get_threat_hunt_prompt(arguments)
        elif name == "triage_incident":
            return _get_triage_incident_prompt(arguments)
        elif name == "malware_analysis":
            return _get_malware_analysis_prompt(arguments)
        elif name == "lateral_movement":
            return _get_lateral_movement_prompt(arguments)
        else:
            raise ValueError(f"Unknown prompt: {name}")


def _get_investigate_endpoint_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate the investigate_endpoint prompt."""
    client_id = arguments.get("client_id", "<client_id>")

    return [PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=f"""I need to investigate the endpoint with identifier: {client_id}

Please help me conduct a comprehensive forensic investigation by:

1. **Initial Reconnaissance**
   - Get client information using get_client_info(client_id='{client_id}')
   - Verify the endpoint is online and get basic system details

2. **Process Analysis**
   - Collect running processes using the Windows.System.Pslist artifact
   - Look for suspicious processes (unusual names, locations, parent-child relationships)
   - Check for processes with high memory usage or CPU
   - Identify any processes running from temp directories or user profile locations

3. **Network Connections**
   - Collect network connections using Windows.Network.Netstat
   - Identify connections to external IPs
   - Look for listening ports that shouldn't be open
   - Check for connections to known malicious IPs/domains

4. **Persistence Mechanisms**
   - Check scheduled tasks (Windows.System.TaskScheduler)
   - Check startup items (Windows.Sys.StartupItems)
   - Check services (Windows.System.Services)
   - Check registry run keys (Windows.Registry.Run)

5. **User Activity**
   - Recent user logins
   - PowerShell history
   - Browser history if relevant

6. **File System Analysis**
   - Check for recently modified executables
   - Look for suspicious files in common malware locations
   - Check temp directories and downloads folder

Please start with step 1 and guide me through each phase, highlighting any findings that warrant further investigation. Use the appropriate Velociraptor tools to collect this information."""
        )
    )]


def _get_threat_hunt_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate the threat_hunt prompt."""
    indicators = arguments.get("indicators", "<indicators>")
    hunt_type = arguments.get("hunt_type", "custom")

    return [PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=f"""I need to conduct a threat hunt across my environment.

**Indicators/Behaviors to hunt for:**
{indicators}

**Hunt type:** {hunt_type}

Please help me create and execute this threat hunt by:

1. **Indicator Analysis**
   - Parse and categorize the provided indicators (file hashes, IP addresses, domains, file names, registry keys, process names, etc.)
   - Determine which Velociraptor artifacts are best suited for detecting each indicator type

2. **Hunt Strategy**
   - Recommend specific artifacts to use based on the indicators:
     - For file-based IOCs: Windows.Search.FileFinder, Windows.Search.YARA
     - For process-based: Windows.System.Pslist, Windows.Detection.ProcessHollowing
     - For network-based: Windows.Network.Netstat, Windows.Network.Connections
     - For registry-based: Windows.Registry.Persistence
     - For persistence: Windows.Persistence.PermanentWMIEvents

3. **Hunt Creation**
   - Use create_hunt() to create the hunt with appropriate:
     - Artifact selection
     - Parameters configured for our specific indicators
     - Scope (all clients or specific labels)
     - Resource limits to avoid impacting endpoints

4. **Results Analysis**
   - Once the hunt runs, use get_hunt_results() to analyze findings
   - Identify true positives vs false positives
   - Prioritize findings by severity
   - Recommend follow-up actions for confirmed detections

5. **Documentation**
   - Document hunt methodology
   - Record all findings with evidence
   - Provide recommendations for remediation

Let's start by analyzing the indicators and determining the best hunting strategy."""
        )
    )]


def _get_triage_incident_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate the triage_incident prompt."""
    client_id = arguments.get("client_id", "<client_id>")
    incident_type = arguments.get("incident_type", "unknown")

    artifact_recommendations = {
        "malware": ["Windows.System.Pslist", "Windows.Detection.Autoruns", "Windows.System.Services", "Windows.Network.Netstat"],
        "intrusion": ["Windows.EventLogs.Evtx", "Windows.System.Users", "Windows.Network.Connections", "Windows.Detection.Autoruns"],
        "data_exfil": ["Windows.Network.Netstat", "Windows.Forensics.Usn", "Windows.System.Pslist", "Windows.EventLogs.RDPAuth"],
        "ransomware": ["Windows.Detection.Ransomware", "Windows.System.Pslist", "Windows.Forensics.Usn", "Windows.Detection.Autoruns"],
        "unknown": ["Windows.KapeFiles.Targets", "Windows.System.Pslist", "Windows.Network.Netstat", "Windows.Detection.Autoruns"],
    }

    recommended_artifacts = artifact_recommendations.get(incident_type, artifact_recommendations["unknown"])

    return [PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=f"""URGENT: Incident triage needed for endpoint {client_id}

**Incident Type:** {incident_type}

Please help me rapidly triage this incident by collecting critical forensic data:

1. **Immediate Collection** (Time-sensitive volatile data)
   First, let's collect the most critical artifacts. Use collect_artifact() with:
   - Client ID: {client_id}
   - Artifacts: {recommended_artifacts}
   - Set urgent=True for priority collection

2. **Quick Assessment**
   While collection runs, get basic info:
   - Use get_client_info() to understand the system
   - Check if the client shows signs of compromise (unusual labels, recent activity)

3. **Volatile Data Analysis**
   Once collection completes, analyze:
   - Running processes - look for malicious/suspicious processes
   - Network connections - identify C2 or data exfiltration
   - Logged-in users - check for unauthorized access

4. **Persistence Check**
   Look for attacker persistence:
   - Scheduled tasks
   - Services
   - Startup items
   - Registry run keys

5. **Scoping Questions**
   Based on initial findings, determine:
   - Is this an isolated incident or are other endpoints affected?
   - What is the likely attack vector?
   - What data may have been accessed/exfiltrated?
   - Should we quarantine this endpoint?

6. **Immediate Recommendations**
   Provide actionable next steps:
   - Containment actions (quarantine, network isolation)
   - Evidence preservation priorities
   - Additional collection requirements
   - Escalation recommendations

Let's start immediately with the urgent collection. Time is critical."""
        )
    )]


def _get_malware_analysis_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate the malware_analysis prompt."""
    client_id = arguments.get("client_id", "<client_id>")
    target = arguments.get("target", "<file_path_or_process>")

    return [PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=f"""I need to analyze a potentially malicious file or process.

**Endpoint:** {client_id}
**Target:** {target}

Please help me analyze this potential malware by:

1. **Target Identification**
   - Determine if the target is a file path or process name
   - If process: Get process details using Windows.System.Pslist with name filter
   - If file: Get file metadata using Windows.Forensics.FileFinder

2. **File Analysis** (if file path provided)
   - Calculate file hashes (MD5, SHA1, SHA256) using Windows.Forensics.HashFiles
   - Get file metadata (timestamps, size, PE info if applicable)
   - Check digital signature status
   - Analyze PE headers if executable
   - Check for packed/obfuscated indicators

3. **Process Analysis** (if process is running)
   - Get full process details including:
     - Command line arguments
     - Parent process
     - Child processes
     - Loaded DLLs
     - Open handles
     - Network connections
   - Check process memory for suspicious patterns
   - Identify process injection indicators

4. **Behavioral Indicators**
   - Check what files the process/file has created or modified
   - Look for registry modifications
   - Check for network connections
   - Identify persistence mechanisms created

5. **Threat Intelligence**
   - Note the file hashes for external lookup (VirusTotal, etc.)
   - Check against known malware signatures
   - Identify malware family if possible

6. **Recommendations**
   - Assess severity and confidence level
   - Recommend containment actions
   - Provide remediation steps
   - Suggest additional investigation steps

Let's start by identifying and collecting information about the target."""
        )
    )]


def _get_lateral_movement_prompt(arguments: dict[str, str]) -> list[PromptMessage]:
    """Generate the lateral_movement prompt."""
    scope = arguments.get("scope", "all")
    timeframe = arguments.get("timeframe", "24h")

    return [PromptMessage(
        role="user",
        content=TextContent(
            type="text",
            text=f"""I need to detect and investigate potential lateral movement in my environment.

**Investigation Scope:** {scope}
**Timeframe:** {timeframe}

Please help me hunt for lateral movement indicators by checking:

1. **RDP Activity**
   - Collect Windows.EventLogs.RDPAuth artifact
   - Look for:
     - Failed RDP authentication attempts
     - Successful RDP logins from unusual sources
     - RDP sessions at unusual times
     - Pass-the-hash indicators in RDP

2. **SMB/Network Shares**
   - Check Windows.EventLogs.Evtx for SMB events
   - Look for:
     - Access to admin shares (C$, ADMIN$)
     - Unusual file share access patterns
     - PsExec-like activity

3. **WMI Activity**
   - Check for WMI-based lateral movement
   - Look for:
     - WMI process creation events
     - WMI persistence mechanisms
     - Unusual WMI providers

4. **PowerShell Remoting**
   - Analyze PowerShell logs
   - Look for:
     - Enter-PSSession usage
     - Invoke-Command to remote hosts
     - PowerShell script block logging for remote execution

5. **Service Creation**
   - Check for remote service installation
   - Look for:
     - New services created recently
     - Services running from unusual locations
     - Services with suspicious command lines

6. **Scheduled Task Abuse**
   - Check for remotely created scheduled tasks
   - Look for:
     - Tasks running as SYSTEM
     - Tasks created by unusual users
     - Tasks pointing to suspicious executables

7. **Credential Access**
   - Check for credential dumping indicators
   - Look for:
     - LSASS access
     - SAM database access
     - Mimikatz-like activity

8. **Analysis & Recommendations**
   - Correlate findings across multiple endpoints
   - Build attack timeline
   - Identify compromised accounts
   - Map lateral movement paths
   - Recommend containment and remediation

{'Create a hunt across all clients' if scope == 'all' else f'Focus investigation on {scope}'} for the past {timeframe}.

Let's start by setting up the appropriate hunts to detect these lateral movement techniques."""
        )
    )]
