"""
Ansible playbook generator for agent deployment.

Generates Ansible playbooks and roles for deploying Velociraptor agents
across infrastructure-as-code environments.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import yaml


@dataclass
class AnsibleConfig:
    """Configuration for Ansible playbook generation.

    Attributes:
        server_url: Velociraptor server URL
        ca_cert: CA certificate content
        ca_fingerprint: CA certificate fingerprint
        client_labels: Labels to apply to clients
        deployment_id: Associated deployment ID
        binary_version: Velociraptor version to deploy
        service_user: User to run the service as
        config_path: Path for client configuration
    """
    server_url: str
    ca_cert: str
    ca_fingerprint: str
    client_labels: list[str] = field(default_factory=list)
    deployment_id: Optional[str] = None
    binary_version: str = "latest"
    service_user: str = "root"
    config_path: str = "/etc/velociraptor"


@dataclass
class GeneratedPlaybook:
    """Result of playbook generation.

    Attributes:
        output_dir: Directory containing generated files
        playbook_path: Path to main playbook
        role_path: Path to role directory
        inventory_example: Path to example inventory
        readme_path: Path to README
        files: List of all generated file paths
    """
    output_dir: Path
    playbook_path: Path
    role_path: Path
    inventory_example: Path
    readme_path: Path
    files: list[Path]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "output_dir": str(self.output_dir),
            "playbook_path": str(self.playbook_path),
            "role_path": str(self.role_path),
            "inventory_example": str(self.inventory_example),
            "readme_path": str(self.readme_path),
            "files": [str(f) for f in self.files],
        }


class AnsiblePlaybookGenerator:
    """Generates Ansible playbooks for Velociraptor agent deployment.

    Creates complete Ansible roles with:
    - Tasks for installing and configuring agents
    - Handlers for service management
    - Variables for customization
    - Templates for configuration files
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the playbook generator.

        Args:
            output_dir: Directory for generated playbooks
        """
        self.output_dir = output_dir or self._default_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default_output_dir() -> Path:
        """Get the default output directory."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", "~"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return base.expanduser() / "megaraptor-mcp" / "ansible"

    def generate(
        self,
        config: AnsibleConfig,
        include_windows: bool = True,
        include_linux: bool = True,
        include_macos: bool = True,
    ) -> GeneratedPlaybook:
        """Generate complete Ansible playbook and role.

        Args:
            config: Ansible configuration
            include_windows: Include Windows tasks
            include_linux: Include Linux tasks
            include_macos: Include macOS tasks

        Returns:
            Generated playbook details
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        playbook_name = f"velociraptor-deploy-{config.deployment_id or timestamp}"
        playbook_dir = self.output_dir / playbook_name

        # Create directory structure
        role_dir = playbook_dir / "roles" / "velociraptor_agent"
        for subdir in ["tasks", "handlers", "templates", "defaults", "vars", "files"]:
            (role_dir / subdir).mkdir(parents=True, exist_ok=True)

        files = []

        # Generate main playbook
        playbook_path = playbook_dir / "deploy_agents.yml"
        playbook_path.write_text(self._generate_main_playbook(config))
        files.append(playbook_path)

        # Generate role defaults
        defaults_path = role_dir / "defaults" / "main.yml"
        defaults_path.write_text(self._generate_defaults(config))
        files.append(defaults_path)

        # Generate role vars
        vars_path = role_dir / "vars" / "main.yml"
        vars_path.write_text(self._generate_vars(config))
        files.append(vars_path)

        # Generate tasks
        tasks_main = role_dir / "tasks" / "main.yml"
        tasks_main.write_text(self._generate_main_tasks(include_windows, include_linux, include_macos))
        files.append(tasks_main)

        if include_linux:
            linux_tasks = role_dir / "tasks" / "linux.yml"
            linux_tasks.write_text(self._generate_linux_tasks())
            files.append(linux_tasks)

        if include_windows:
            windows_tasks = role_dir / "tasks" / "windows.yml"
            windows_tasks.write_text(self._generate_windows_tasks())
            files.append(windows_tasks)

        if include_macos:
            macos_tasks = role_dir / "tasks" / "macos.yml"
            macos_tasks.write_text(self._generate_macos_tasks())
            files.append(macos_tasks)

        # Generate handlers
        handlers_path = role_dir / "handlers" / "main.yml"
        handlers_path.write_text(self._generate_handlers())
        files.append(handlers_path)

        # Generate templates
        client_config_template = role_dir / "templates" / "client.config.yaml.j2"
        client_config_template.write_text(self._generate_client_config_template(config))
        files.append(client_config_template)

        systemd_template = role_dir / "templates" / "velociraptor.service.j2"
        systemd_template.write_text(self._generate_systemd_template())
        files.append(systemd_template)

        launchd_template = role_dir / "templates" / "com.velocidex.velociraptor.plist.j2"
        launchd_template.write_text(self._generate_launchd_template())
        files.append(launchd_template)

        # Generate CA certificate file
        ca_cert_file = role_dir / "files" / "ca.crt"
        ca_cert_file.write_text(config.ca_cert)
        files.append(ca_cert_file)

        # Generate inventory example
        inventory_path = playbook_dir / "inventory.yml.example"
        inventory_path.write_text(self._generate_inventory_example())
        files.append(inventory_path)

        # Generate README
        readme_path = playbook_dir / "README.md"
        readme_path.write_text(self._generate_readme(config))
        files.append(readme_path)

        # Generate ansible.cfg
        ansible_cfg = playbook_dir / "ansible.cfg"
        ansible_cfg.write_text(self._generate_ansible_cfg())
        files.append(ansible_cfg)

        return GeneratedPlaybook(
            output_dir=playbook_dir,
            playbook_path=playbook_path,
            role_path=role_dir,
            inventory_example=inventory_path,
            readme_path=readme_path,
            files=files,
        )

    def _generate_main_playbook(self, config: AnsibleConfig) -> str:
        """Generate main playbook YAML."""
        playbook = [
            {
                "name": "Deploy Velociraptor Agent",
                "hosts": "all",
                "become": True,
                "roles": [
                    "velociraptor_agent"
                ],
                "vars": {
                    "velociraptor_server_url": config.server_url,
                    "velociraptor_ca_fingerprint": config.ca_fingerprint,
                    "velociraptor_client_labels": config.client_labels,
                },
            }
        ]
        return yaml.dump(playbook, default_flow_style=False)

    def _generate_defaults(self, config: AnsibleConfig) -> str:
        """Generate role defaults."""
        defaults = {
            "velociraptor_version": config.binary_version,
            "velociraptor_server_url": config.server_url,
            "velociraptor_config_path": config.config_path,
            "velociraptor_service_user": config.service_user,
            "velociraptor_client_labels": config.client_labels,
            "velociraptor_ca_fingerprint": config.ca_fingerprint,
            "velociraptor_binary_base_url": "https://github.com/Velocidex/velociraptor/releases/latest/download",
            "velociraptor_install_path_linux": "/usr/local/bin/velociraptor",
            "velociraptor_install_path_macos": "/usr/local/bin/velociraptor",
            "velociraptor_install_path_windows": "C:\\Program Files\\Velociraptor\\velociraptor.exe",
        }
        return yaml.dump(defaults, default_flow_style=False)

    def _generate_vars(self, config: AnsibleConfig) -> str:
        """Generate role variables."""
        vars_content = {
            "velociraptor_binaries": {
                "linux_amd64": "velociraptor-v{{ velociraptor_version }}-linux-amd64",
                "linux_arm64": "velociraptor-v{{ velociraptor_version }}-linux-arm64",
                "darwin_amd64": "velociraptor-v{{ velociraptor_version }}-darwin-amd64",
                "darwin_arm64": "velociraptor-v{{ velociraptor_version }}-darwin-arm64",
                "windows_amd64": "velociraptor-v{{ velociraptor_version }}-windows-amd64.msi",
            }
        }
        return yaml.dump(vars_content, default_flow_style=False)

    def _generate_main_tasks(
        self,
        include_windows: bool,
        include_linux: bool,
        include_macos: bool,
    ) -> str:
        """Generate main tasks file."""
        tasks = []

        if include_linux:
            tasks.append({
                "name": "Include Linux tasks",
                "include_tasks": "linux.yml",
                "when": "ansible_os_family != 'Windows' and ansible_os_family != 'Darwin'",
            })

        if include_windows:
            tasks.append({
                "name": "Include Windows tasks",
                "include_tasks": "windows.yml",
                "when": "ansible_os_family == 'Windows'",
            })

        if include_macos:
            tasks.append({
                "name": "Include macOS tasks",
                "include_tasks": "macos.yml",
                "when": "ansible_os_family == 'Darwin'",
            })

        return yaml.dump(tasks, default_flow_style=False)

    def _generate_linux_tasks(self) -> str:
        """Generate Linux tasks."""
        tasks = [
            {
                "name": "Create Velociraptor directories",
                "file": {
                    "path": "{{ item }}",
                    "state": "directory",
                    "mode": "0755",
                },
                "loop": [
                    "{{ velociraptor_config_path }}",
                    "/opt/velociraptor",
                ],
            },
            {
                "name": "Detect architecture",
                "set_fact": {
                    "velociraptor_arch": "{{ 'arm64' if ansible_architecture == 'aarch64' else 'amd64' }}",
                },
            },
            {
                "name": "Download Velociraptor binary",
                "get_url": {
                    "url": "{{ velociraptor_binary_base_url }}/{{ velociraptor_binaries['linux_' + velociraptor_arch] }}",
                    "dest": "{{ velociraptor_install_path_linux }}",
                    "mode": "0755",
                },
            },
            {
                "name": "Copy CA certificate",
                "copy": {
                    "src": "ca.crt",
                    "dest": "{{ velociraptor_config_path }}/ca.crt",
                    "mode": "0644",
                },
            },
            {
                "name": "Deploy client configuration",
                "template": {
                    "src": "client.config.yaml.j2",
                    "dest": "{{ velociraptor_config_path }}/client.config.yaml",
                    "mode": "0600",
                },
                "notify": "restart velociraptor",
            },
            {
                "name": "Deploy systemd service",
                "template": {
                    "src": "velociraptor.service.j2",
                    "dest": "/etc/systemd/system/velociraptor.service",
                    "mode": "0644",
                },
                "notify": [
                    "reload systemd",
                    "restart velociraptor",
                ],
            },
            {
                "name": "Enable and start Velociraptor service",
                "systemd": {
                    "name": "velociraptor",
                    "state": "started",
                    "enabled": True,
                    "daemon_reload": True,
                },
            },
        ]
        return yaml.dump(tasks, default_flow_style=False)

    def _generate_windows_tasks(self) -> str:
        """Generate Windows tasks."""
        tasks = [
            {
                "name": "Create Velociraptor directory",
                "win_file": {
                    "path": "C:\\Program Files\\Velociraptor",
                    "state": "directory",
                },
            },
            {
                "name": "Download Velociraptor MSI",
                "win_get_url": {
                    "url": "{{ velociraptor_binary_base_url }}/{{ velociraptor_binaries['windows_amd64'] }}",
                    "dest": "C:\\Program Files\\Velociraptor\\velociraptor.msi",
                },
            },
            {
                "name": "Install Velociraptor",
                "win_package": {
                    "path": "C:\\Program Files\\Velociraptor\\velociraptor.msi",
                    "state": "present",
                },
            },
            {
                "name": "Copy CA certificate",
                "win_copy": {
                    "src": "ca.crt",
                    "dest": "C:\\Program Files\\Velociraptor\\ca.crt",
                },
            },
            {
                "name": "Deploy client configuration",
                "win_template": {
                    "src": "client.config.yaml.j2",
                    "dest": "C:\\Program Files\\Velociraptor\\Velociraptor.config.yaml",
                },
                "notify": "restart velociraptor windows",
            },
            {
                "name": "Ensure Velociraptor service is running",
                "win_service": {
                    "name": "Velociraptor",
                    "state": "started",
                    "start_mode": "auto",
                },
            },
        ]
        return yaml.dump(tasks, default_flow_style=False)

    def _generate_macos_tasks(self) -> str:
        """Generate macOS tasks."""
        tasks = [
            {
                "name": "Create Velociraptor directories",
                "file": {
                    "path": "{{ item }}",
                    "state": "directory",
                    "mode": "0755",
                },
                "loop": [
                    "{{ velociraptor_config_path }}",
                    "/opt/velociraptor",
                ],
            },
            {
                "name": "Detect architecture",
                "set_fact": {
                    "velociraptor_arch": "{{ 'arm64' if ansible_architecture == 'arm64' else 'amd64' }}",
                },
            },
            {
                "name": "Download Velociraptor binary",
                "get_url": {
                    "url": "{{ velociraptor_binary_base_url }}/{{ velociraptor_binaries['darwin_' + velociraptor_arch] }}",
                    "dest": "{{ velociraptor_install_path_macos }}",
                    "mode": "0755",
                },
            },
            {
                "name": "Copy CA certificate",
                "copy": {
                    "src": "ca.crt",
                    "dest": "{{ velociraptor_config_path }}/ca.crt",
                    "mode": "0644",
                },
            },
            {
                "name": "Deploy client configuration",
                "template": {
                    "src": "client.config.yaml.j2",
                    "dest": "{{ velociraptor_config_path }}/client.config.yaml",
                    "mode": "0600",
                },
                "notify": "restart velociraptor macos",
            },
            {
                "name": "Deploy launchd plist",
                "template": {
                    "src": "com.velocidex.velociraptor.plist.j2",
                    "dest": "/Library/LaunchDaemons/com.velocidex.velociraptor.plist",
                    "mode": "0644",
                },
                "notify": "restart velociraptor macos",
            },
            {
                "name": "Load Velociraptor service",
                "command": "launchctl load /Library/LaunchDaemons/com.velocidex.velociraptor.plist",
                "register": "launchctl_result",
                "failed_when": False,
                "changed_when": "launchctl_result.rc == 0",
            },
        ]
        return yaml.dump(tasks, default_flow_style=False)

    def _generate_handlers(self) -> str:
        """Generate handlers."""
        handlers = [
            {
                "name": "reload systemd",
                "systemd": {
                    "daemon_reload": True,
                },
            },
            {
                "name": "restart velociraptor",
                "systemd": {
                    "name": "velociraptor",
                    "state": "restarted",
                },
            },
            {
                "name": "restart velociraptor windows",
                "win_service": {
                    "name": "Velociraptor",
                    "state": "restarted",
                },
            },
            {
                "name": "restart velociraptor macos",
                "command": "launchctl kickstart -k system/com.velocidex.velociraptor",
            },
        ]
        return yaml.dump(handlers, default_flow_style=False)

    def _generate_client_config_template(self, config: AnsibleConfig) -> str:
        """Generate client configuration Jinja2 template."""
        return """# Velociraptor Client Configuration
# Generated by Megaraptor MCP Ansible Playbook Generator

Client:
  server_urls:
    - {{ velociraptor_server_url }}
  ca_certificate: |
{{ lookup('file', velociraptor_config_path + '/ca.crt') | indent(4, True) }}
  nonce: {{ ansible_machine_id | default(ansible_hostname) | hash('sha256') | truncate(16, True, '') }}
{% if velociraptor_client_labels %}
  labels:
{% for label in velociraptor_client_labels %}
    - {{ label }}
{% endfor %}
{% endif %}
  writeback_darwin: /etc/velociraptor.writeback.yaml
  writeback_linux: /etc/velociraptor.writeback.yaml
  writeback_windows: C:\\Program Files\\Velociraptor\\velociraptor.writeback.yaml

version:
  name: megaraptor-ansible-deploy
"""

    def _generate_systemd_template(self) -> str:
        """Generate systemd service template."""
        return """[Unit]
Description=Velociraptor Agent
After=network.target

[Service]
Type=simple
ExecStart={{ velociraptor_install_path_linux }} client -c {{ velociraptor_config_path }}/client.config.yaml
Restart=always
RestartSec=10
User={{ velociraptor_service_user }}
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""

    def _generate_launchd_template(self) -> str:
        """Generate launchd plist template."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.velocidex.velociraptor</string>
    <key>ProgramArguments</key>
    <array>
        <string>{{ velociraptor_install_path_macos }}</string>
        <string>client</string>
        <string>-c</string>
        <string>{{ velociraptor_config_path }}/client.config.yaml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/var/log/velociraptor.err</string>
    <key>StandardOutPath</key>
    <string>/var/log/velociraptor.out</string>
</dict>
</plist>
"""

    def _generate_inventory_example(self) -> str:
        """Generate example inventory file."""
        return """# Velociraptor Agent Deployment Inventory
# Copy this file to inventory.yml and customize for your environment

all:
  children:
    linux_servers:
      hosts:
        server1.example.com:
        server2.example.com:
      vars:
        ansible_user: admin
        ansible_become: true

    windows_servers:
      hosts:
        winserver1.example.com:
        winserver2.example.com:
      vars:
        ansible_user: Administrator
        ansible_connection: winrm
        ansible_winrm_transport: ntlm
        ansible_winrm_server_cert_validation: ignore

    macos_endpoints:
      hosts:
        mac1.example.com:
      vars:
        ansible_user: admin
        ansible_become: true
        ansible_become_method: sudo

  vars:
    # Override these in your inventory or via command line
    velociraptor_client_labels:
      - deployed_by_ansible
"""

    def _generate_readme(self, config: AnsibleConfig) -> str:
        """Generate README documentation."""
        return f"""# Velociraptor Agent Deployment Playbook

Ansible playbook for deploying Velociraptor agents to Linux, Windows, and macOS systems.

## Generated Configuration

- **Server URL**: {config.server_url}
- **CA Fingerprint**: {config.ca_fingerprint}
- **Deployment ID**: {config.deployment_id or 'N/A'}
- **Generated**: {datetime.now(timezone.utc).isoformat()}

## Prerequisites

- Ansible 2.9+
- For Windows: `pywinrm` installed (`pip install pywinrm`)
- SSH access to Linux/macOS hosts
- WinRM enabled on Windows hosts

## Quick Start

1. Copy `inventory.yml.example` to `inventory.yml`
2. Update inventory with your hosts
3. Run the playbook:

```bash
ansible-playbook -i inventory.yml deploy_agents.yml
```

## Directory Structure

```
.
├── ansible.cfg              # Ansible configuration
├── deploy_agents.yml        # Main playbook
├── inventory.yml.example    # Example inventory
├── README.md               # This file
└── roles/
    └── velociraptor_agent/
        ├── defaults/        # Default variables
        ├── files/          # CA certificate
        ├── handlers/       # Service handlers
        ├── tasks/          # Installation tasks
        ├── templates/      # Config templates
        └── vars/           # Role variables
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `velociraptor_version` | `{config.binary_version}` | Version to deploy |
| `velociraptor_server_url` | `{config.server_url}` | Server URL |
| `velociraptor_config_path` | `{config.config_path}` | Config directory |
| `velociraptor_client_labels` | `[]` | Labels for clients |

## Usage Examples

### Deploy to all hosts
```bash
ansible-playbook -i inventory.yml deploy_agents.yml
```

### Deploy to specific group
```bash
ansible-playbook -i inventory.yml deploy_agents.yml -l linux_servers
```

### Deploy with custom labels
```bash
ansible-playbook -i inventory.yml deploy_agents.yml -e "velociraptor_client_labels=['production','web']"
```

### Check mode (dry run)
```bash
ansible-playbook -i inventory.yml deploy_agents.yml --check
```

## Security Notes

- Client configuration contains sensitive certificates
- CA certificate is pinned via fingerprint: `{config.ca_fingerprint}`
- Ensure inventory files with credentials are not committed to version control

## Troubleshooting

### Linux
```bash
# Check service status
sudo systemctl status velociraptor

# View logs
sudo journalctl -u velociraptor -f
```

### Windows
```powershell
# Check service status
Get-Service Velociraptor

# View logs
Get-EventLog -LogName Application -Source Velociraptor
```

### macOS
```bash
# Check service status
sudo launchctl list | grep velociraptor

# View logs
cat /var/log/velociraptor.out
cat /var/log/velociraptor.err
```
"""

    def _generate_ansible_cfg(self) -> str:
        """Generate ansible.cfg."""
        return """[defaults]
inventory = inventory.yml
roles_path = roles
host_key_checking = False
retry_files_enabled = False

[privilege_escalation]
become = True
become_method = sudo
become_ask_pass = False
"""
