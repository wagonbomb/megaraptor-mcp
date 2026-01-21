"""
Cloud-based Velociraptor server deployment.

Supports AWS CloudFormation and Azure ARM template deployments.
"""

import asyncio
import json
import os
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Any

from .base import BaseDeployer, DeploymentResult, DeploymentInfo
from ..profiles import DeploymentProfile, DeploymentState, DeploymentTarget

# Optional cloud SDK imports
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.resource.resources.models import DeploymentMode
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False


class CloudDeployer(BaseDeployer):
    """Base class for cloud deployments."""

    @abstractmethod
    async def deploy(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
    ) -> DeploymentResult:
        pass


class AWSDeployer(CloudDeployer):
    """Deploy Velociraptor servers on AWS using CloudFormation.

    Uses CloudFormation templates to provision EC2 instances,
    security groups, and other required infrastructure.
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        region: str = "us-east-1",
    ):
        """Initialize the AWS deployer.

        Args:
            storage_path: Path for storing deployment data
            region: AWS region for deployment

        Raises:
            ImportError: If boto3 is not installed
        """
        if not HAS_BOTO3:
            raise ImportError(
                "boto3 package required for AWS deployment. "
                "Install with: pip install boto3"
            )

        super().__init__(storage_path)
        self.region = region
        self._cf_client = None
        self._ec2_client = None

    @property
    def target_type(self) -> DeploymentTarget:
        """Return the deployment target type."""
        return DeploymentTarget.AWS

    @property
    def cf_client(self):
        """Get or create CloudFormation client."""
        if self._cf_client is None:
            self._cf_client = boto3.client("cloudformation", region_name=self.region)
        return self._cf_client

    @property
    def ec2_client(self):
        """Get or create EC2 client."""
        if self._ec2_client is None:
            self._ec2_client = boto3.client("ec2", region_name=self.region)
        return self._ec2_client

    def _stack_name(self, deployment_id: str) -> str:
        """Get the CloudFormation stack name."""
        return f"velociraptor-{deployment_id}"

    async def deploy(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
        instance_type: str = "t3.large",
        key_pair_name: Optional[str] = None,
        vpc_id: Optional[str] = None,
        subnet_id: Optional[str] = None,
    ) -> DeploymentResult:
        """Deploy Velociraptor server on AWS.

        Args:
            config: Deployment configuration
            profile: Deployment profile
            certificates: Certificate bundle
            instance_type: EC2 instance type
            key_pair_name: EC2 key pair for SSH access
            vpc_id: VPC ID (uses default if not specified)
            subnet_id: Subnet ID (uses default if not specified)

        Returns:
            DeploymentResult with deployment details
        """
        deployment_id = config.deployment_id
        stack_name = self._stack_name(deployment_id)

        try:
            # Generate CloudFormation template
            template = self._generate_cloudformation_template(
                config,
                profile,
                certificates,
                instance_type,
                key_pair_name,
            )

            # Create deployment directory
            deployment_dir = self.storage_path / deployment_id
            deployment_dir.mkdir(parents=True, exist_ok=True)

            # Save template
            template_file = deployment_dir / "cloudformation.yaml"
            template_file.write_text(template)

            # Create stack
            stack_params = []
            if vpc_id:
                stack_params.append({"ParameterKey": "VpcId", "ParameterValue": vpc_id})
            if subnet_id:
                stack_params.append({"ParameterKey": "SubnetId", "ParameterValue": subnet_id})

            await asyncio.to_thread(
                self.cf_client.create_stack,
                StackName=stack_name,
                TemplateBody=template,
                Parameters=stack_params,
                Capabilities=["CAPABILITY_IAM"],
                Tags=[
                    {"Key": "megaraptor:deployment_id", "Value": deployment_id},
                    {"Key": "megaraptor:profile", "Value": profile.name},
                ],
            )

            # Wait for stack creation
            waiter = self.cf_client.get_waiter("stack_create_complete")
            await asyncio.to_thread(
                waiter.wait,
                StackName=stack_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": 40},
            )

            # Get stack outputs
            response = await asyncio.to_thread(
                self.cf_client.describe_stacks,
                StackName=stack_name,
            )
            stack = response["Stacks"][0]
            outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}

            server_url = outputs.get("ServerURL", f"https://{config.server_hostname}:{config.gui_port}")
            api_url = outputs.get("APIURL", f"{server_url}/api/")
            instance_id = outputs.get("InstanceId", "")
            public_ip = outputs.get("PublicIP", "")

            # Calculate auto-destroy time
            auto_destroy_at = None
            if profile.auto_destroy_hours:
                destroy_time = datetime.now(timezone.utc) + timedelta(
                    hours=profile.auto_destroy_hours
                )
                auto_destroy_at = destroy_time.isoformat()

            # Create deployment info
            info = DeploymentInfo(
                deployment_id=deployment_id,
                profile=profile.name,
                target=self.target_type.value,
                state=DeploymentState.RUNNING,
                server_url=server_url,
                api_url=api_url,
                created_at=self._now_iso(),
                auto_destroy_at=auto_destroy_at,
                metadata={
                    "stack_name": stack_name,
                    "instance_id": instance_id,
                    "public_ip": public_ip,
                    "region": self.region,
                    "instance_type": instance_type,
                },
            )
            self.save_deployment_info(info)

            from ..security.credential_store import generate_password
            admin_password = generate_password(24)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="AWS deployment created successfully",
                server_url=server_url,
                api_url=api_url,
                admin_password=admin_password,
                details={
                    "stack_name": stack_name,
                    "instance_id": instance_id,
                    "public_ip": public_ip,
                    "region": self.region,
                    "auto_destroy_at": auto_destroy_at,
                    "ca_fingerprint": certificates.ca_fingerprint,
                },
            )

        except ClientError as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="AWS deployment failed",
                error=str(e),
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Deployment failed",
                error=str(e),
            )

    def _generate_cloudformation_template(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
        instance_type: str,
        key_pair_name: Optional[str],
    ) -> str:
        """Generate CloudFormation template."""
        import yaml

        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": f"Velociraptor Server Deployment - {config.deployment_id}",
            "Parameters": {
                "VpcId": {
                    "Type": "AWS::EC2::VPC::Id",
                    "Description": "VPC ID",
                    "Default": "",
                },
                "SubnetId": {
                    "Type": "AWS::EC2::Subnet::Id",
                    "Description": "Subnet ID",
                    "Default": "",
                },
            },
            "Resources": {
                "SecurityGroup": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "GroupDescription": f"Velociraptor Server - {config.deployment_id}",
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": config.gui_port,
                                "ToPort": config.gui_port,
                                "CidrIp": "0.0.0.0/0",
                            },
                            {
                                "IpProtocol": "tcp",
                                "FromPort": config.frontend_port,
                                "ToPort": config.frontend_port,
                                "CidrIp": "0.0.0.0/0",
                            },
                        ],
                        "Tags": [
                            {"Key": "Name", "Value": f"velociraptor-{config.deployment_id}"},
                        ],
                    },
                },
                "Instance": {
                    "Type": "AWS::EC2::Instance",
                    "Properties": {
                        "ImageId": "{{resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64}}",
                        "InstanceType": instance_type,
                        "SecurityGroupIds": [{"Ref": "SecurityGroup"}],
                        "Tags": [
                            {"Key": "Name", "Value": f"velociraptor-{config.deployment_id}"},
                        ],
                        "UserData": {
                            "Fn::Base64": self._generate_user_data(config, certificates),
                        },
                    },
                },
            },
            "Outputs": {
                "InstanceId": {
                    "Value": {"Ref": "Instance"},
                },
                "PublicIP": {
                    "Value": {"Fn::GetAtt": ["Instance", "PublicIp"]},
                },
                "ServerURL": {
                    "Value": {
                        "Fn::Sub": f"https://${{Instance.PublicIp}}:{config.gui_port}"
                    },
                },
                "APIURL": {
                    "Value": {
                        "Fn::Sub": f"https://${{Instance.PublicIp}}:{config.gui_port}/api/"
                    },
                },
            },
        }

        if key_pair_name:
            template["Resources"]["Instance"]["Properties"]["KeyName"] = key_pair_name

        return yaml.dump(template, default_flow_style=False)

    def _generate_user_data(self, config: Any, certificates: Any) -> str:
        """Generate EC2 user data script."""
        return f"""#!/bin/bash
set -ex

# Install dependencies
yum install -y curl

# Download Velociraptor
curl -L -o /usr/local/bin/velociraptor https://github.com/Velocidex/velociraptor/releases/latest/download/velociraptor-v0.7.1-linux-amd64
chmod +x /usr/local/bin/velociraptor

# Create directories
mkdir -p /opt/velociraptor/{{data,logs,config}}
mkdir -p /etc/velociraptor

# Write certificates
cat > /etc/velociraptor/ca.crt << 'CACERT'
{certificates.ca_cert}
CACERT

cat > /etc/velociraptor/server.crt << 'SERVERCERT'
{certificates.server_cert}
SERVERCERT

cat > /etc/velociraptor/server.key << 'SERVERKEY'
{certificates.server_key}
SERVERKEY

# Generate config
/usr/local/bin/velociraptor config generate --merge > /etc/velociraptor/server.config.yaml << EOF
{{
  "GUI": {{
    "bind_address": "{config.bind_address}:{config.gui_port}"
  }},
  "Frontend": {{
    "bind_address": "{config.bind_address}:{config.frontend_port}"
  }}
}}
EOF

# Create systemd service
cat > /etc/systemd/system/velociraptor.service << 'SERVICE'
[Unit]
Description=Velociraptor Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/velociraptor frontend -c /etc/velociraptor/server.config.yaml
Restart=always
RestartSec=10
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
SERVICE

# Start service
systemctl daemon-reload
systemctl enable velociraptor
systemctl start velociraptor
"""

    async def destroy(self, deployment_id: str, force: bool = False) -> DeploymentResult:
        """Destroy an AWS deployment.

        Args:
            deployment_id: The deployment to destroy
            force: Force destruction

        Returns:
            DeploymentResult indicating success/failure
        """
        stack_name = self._stack_name(deployment_id)

        try:
            await asyncio.to_thread(
                self.cf_client.delete_stack,
                StackName=stack_name,
            )

            # Wait for deletion
            waiter = self.cf_client.get_waiter("stack_delete_complete")
            await asyncio.to_thread(
                waiter.wait,
                StackName=stack_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": 40},
            )

            # Update state
            info = self.load_deployment_info(deployment_id)
            if info:
                info.state = DeploymentState.DESTROYED
                self.save_deployment_info(info)

            if force:
                self.delete_deployment_info(deployment_id)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="AWS deployment destroyed successfully",
            )

        except ClientError as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Failed to destroy AWS deployment",
                error=str(e),
            )

    async def get_status(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get the status of an AWS deployment."""
        info = self.load_deployment_info(deployment_id)
        if not info:
            return None

        stack_name = self._stack_name(deployment_id)

        try:
            response = await asyncio.to_thread(
                self.cf_client.describe_stacks,
                StackName=stack_name,
            )
            stack = response["Stacks"][0]
            status = stack["StackStatus"]

            state_map = {
                "CREATE_COMPLETE": DeploymentState.RUNNING,
                "CREATE_IN_PROGRESS": DeploymentState.PROVISIONING,
                "DELETE_IN_PROGRESS": DeploymentState.STOPPING,
                "DELETE_COMPLETE": DeploymentState.DESTROYED,
                "ROLLBACK_COMPLETE": DeploymentState.FAILED,
                "ROLLBACK_IN_PROGRESS": DeploymentState.FAILED,
            }
            info.state = state_map.get(status, DeploymentState.RUNNING)

        except ClientError:
            info.state = DeploymentState.DESTROYED

        return info

    async def health_check(self, deployment_id: str) -> dict[str, Any]:
        """Perform a health check on an AWS deployment."""
        health = {
            "healthy": False,
            "stack_status": "unknown",
            "instance_status": "unknown",
            "api_responsive": False,
            "checks": [],
        }

        info = self.load_deployment_info(deployment_id)
        if not info:
            health["checks"].append({
                "name": "deployment_info",
                "status": "fail",
                "message": "Deployment info not found",
            })
            return health

        stack_name = self._stack_name(deployment_id)

        try:
            # Check stack status
            response = await asyncio.to_thread(
                self.cf_client.describe_stacks,
                StackName=stack_name,
            )
            stack = response["Stacks"][0]
            health["stack_status"] = stack["StackStatus"]
            health["checks"].append({
                "name": "stack_status",
                "status": "pass" if "COMPLETE" in stack["StackStatus"] else "fail",
                "message": f"Stack status: {stack['StackStatus']}",
            })

            # Check instance status
            instance_id = info.metadata.get("instance_id")
            if instance_id:
                response = await asyncio.to_thread(
                    self.ec2_client.describe_instance_status,
                    InstanceIds=[instance_id],
                )
                if response["InstanceStatuses"]:
                    status = response["InstanceStatuses"][0]
                    health["instance_status"] = status["InstanceState"]["Name"]
                    health["checks"].append({
                        "name": "instance_status",
                        "status": "pass" if health["instance_status"] == "running" else "fail",
                        "message": f"Instance status: {health['instance_status']}",
                    })

            health["healthy"] = (
                health["stack_status"] == "CREATE_COMPLETE"
                and health["instance_status"] == "running"
            )

        except ClientError as e:
            health["checks"].append({
                "name": "aws_api",
                "status": "fail",
                "message": str(e),
            })

        return health


class AzureDeployer(CloudDeployer):
    """Deploy Velociraptor servers on Azure using ARM templates.

    Uses Azure Resource Manager templates to provision VMs,
    network security groups, and other required infrastructure.
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        subscription_id: Optional[str] = None,
    ):
        """Initialize the Azure deployer.

        Args:
            storage_path: Path for storing deployment data
            subscription_id: Azure subscription ID

        Raises:
            ImportError: If Azure SDK is not installed
        """
        if not HAS_AZURE:
            raise ImportError(
                "Azure SDK required for Azure deployment. "
                "Install with: pip install azure-identity azure-mgmt-resource"
            )

        super().__init__(storage_path)
        self.subscription_id = subscription_id or os.environ.get("AZURE_SUBSCRIPTION_ID")
        self._resource_client = None

    @property
    def target_type(self) -> DeploymentTarget:
        """Return the deployment target type."""
        return DeploymentTarget.AZURE

    @property
    def resource_client(self):
        """Get or create Azure Resource Management client."""
        if self._resource_client is None:
            credential = DefaultAzureCredential()
            self._resource_client = ResourceManagementClient(
                credential, self.subscription_id
            )
        return self._resource_client

    def _resource_group_name(self, deployment_id: str) -> str:
        """Get the resource group name."""
        return f"rg-velociraptor-{deployment_id}"

    async def deploy(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
        resource_group: Optional[str] = None,
        location: str = "eastus",
        vm_size: str = "Standard_D2s_v3",
    ) -> DeploymentResult:
        """Deploy Velociraptor server on Azure.

        Args:
            config: Deployment configuration
            profile: Deployment profile
            certificates: Certificate bundle
            resource_group: Azure resource group (created if not exists)
            location: Azure region
            vm_size: VM size

        Returns:
            DeploymentResult with deployment details
        """
        deployment_id = config.deployment_id
        rg_name = resource_group or self._resource_group_name(deployment_id)

        try:
            # Create resource group
            await asyncio.to_thread(
                self.resource_client.resource_groups.create_or_update,
                rg_name,
                {"location": location},
            )

            # Generate ARM template
            template = self._generate_arm_template(config, profile, certificates, vm_size)

            # Create deployment directory
            deployment_dir = self.storage_path / deployment_id
            deployment_dir.mkdir(parents=True, exist_ok=True)

            # Save template
            template_file = deployment_dir / "arm_template.json"
            template_file.write_text(json.dumps(template, indent=2))

            # Deploy template
            deployment_name = f"velociraptor-{deployment_id}"
            deployment_properties = {
                "mode": "Incremental",
                "template": template,
            }

            deployment_async = await asyncio.to_thread(
                self.resource_client.deployments.begin_create_or_update,
                rg_name,
                deployment_name,
                {"properties": deployment_properties},
            )

            # Wait for deployment
            result = await asyncio.to_thread(deployment_async.result)

            # Get outputs
            outputs = result.properties.outputs or {}
            public_ip = outputs.get("publicIP", {}).get("value", "")
            server_url = f"https://{public_ip}:{config.gui_port}"
            api_url = f"{server_url}/api/"

            # Calculate auto-destroy time
            auto_destroy_at = None
            if profile.auto_destroy_hours:
                destroy_time = datetime.now(timezone.utc) + timedelta(
                    hours=profile.auto_destroy_hours
                )
                auto_destroy_at = destroy_time.isoformat()

            # Create deployment info
            info = DeploymentInfo(
                deployment_id=deployment_id,
                profile=profile.name,
                target=self.target_type.value,
                state=DeploymentState.RUNNING,
                server_url=server_url,
                api_url=api_url,
                created_at=self._now_iso(),
                auto_destroy_at=auto_destroy_at,
                metadata={
                    "resource_group": rg_name,
                    "deployment_name": deployment_name,
                    "location": location,
                    "public_ip": public_ip,
                    "vm_size": vm_size,
                },
            )
            self.save_deployment_info(info)

            from ..security.credential_store import generate_password
            admin_password = generate_password(24)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="Azure deployment created successfully",
                server_url=server_url,
                api_url=api_url,
                admin_password=admin_password,
                details={
                    "resource_group": rg_name,
                    "deployment_name": deployment_name,
                    "location": location,
                    "public_ip": public_ip,
                    "auto_destroy_at": auto_destroy_at,
                    "ca_fingerprint": certificates.ca_fingerprint,
                },
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Azure deployment failed",
                error=str(e),
            )

    def _generate_arm_template(
        self,
        config: Any,
        profile: DeploymentProfile,
        certificates: Any,
        vm_size: str,
    ) -> dict:
        """Generate Azure ARM template."""
        return {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [
                {
                    "type": "Microsoft.Network/publicIPAddresses",
                    "apiVersion": "2021-02-01",
                    "name": f"pip-velociraptor-{config.deployment_id}",
                    "location": "[resourceGroup().location]",
                    "properties": {
                        "publicIPAllocationMethod": "Static",
                    },
                },
                {
                    "type": "Microsoft.Network/networkSecurityGroups",
                    "apiVersion": "2021-02-01",
                    "name": f"nsg-velociraptor-{config.deployment_id}",
                    "location": "[resourceGroup().location]",
                    "properties": {
                        "securityRules": [
                            {
                                "name": "AllowGUI",
                                "properties": {
                                    "priority": 100,
                                    "protocol": "Tcp",
                                    "access": "Allow",
                                    "direction": "Inbound",
                                    "sourceAddressPrefix": "*",
                                    "sourcePortRange": "*",
                                    "destinationAddressPrefix": "*",
                                    "destinationPortRange": str(config.gui_port),
                                },
                            },
                            {
                                "name": "AllowFrontend",
                                "properties": {
                                    "priority": 101,
                                    "protocol": "Tcp",
                                    "access": "Allow",
                                    "direction": "Inbound",
                                    "sourceAddressPrefix": "*",
                                    "sourcePortRange": "*",
                                    "destinationAddressPrefix": "*",
                                    "destinationPortRange": str(config.frontend_port),
                                },
                            },
                        ],
                    },
                },
            ],
            "outputs": {
                "publicIP": {
                    "type": "string",
                    "value": "[reference(resourceId('Microsoft.Network/publicIPAddresses', concat('pip-velociraptor-', parameters('deploymentId')))).ipAddress]",
                },
            },
        }

    async def destroy(self, deployment_id: str, force: bool = False) -> DeploymentResult:
        """Destroy an Azure deployment."""
        info = self.load_deployment_info(deployment_id)
        if not info:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Deployment not found",
            )

        rg_name = info.metadata.get("resource_group")
        if not rg_name:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Resource group not found in metadata",
            )

        try:
            delete_async = await asyncio.to_thread(
                self.resource_client.resource_groups.begin_delete,
                rg_name,
            )
            await asyncio.to_thread(delete_async.result)

            info.state = DeploymentState.DESTROYED
            self.save_deployment_info(info)

            if force:
                self.delete_deployment_info(deployment_id)

            return DeploymentResult(
                success=True,
                deployment_id=deployment_id,
                message="Azure deployment destroyed successfully",
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                deployment_id=deployment_id,
                message="Failed to destroy Azure deployment",
                error=str(e),
            )

    async def get_status(self, deployment_id: str) -> Optional[DeploymentInfo]:
        """Get the status of an Azure deployment."""
        return self.load_deployment_info(deployment_id)

    async def health_check(self, deployment_id: str) -> dict[str, Any]:
        """Perform a health check on an Azure deployment."""
        health = {
            "healthy": False,
            "deployment_status": "unknown",
            "api_responsive": False,
            "checks": [],
        }

        info = self.load_deployment_info(deployment_id)
        if not info:
            health["checks"].append({
                "name": "deployment_info",
                "status": "fail",
                "message": "Deployment info not found",
            })
            return health

        # Check API responsiveness
        try:
            import httpx

            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.get(info.api_url)
                health["api_responsive"] = response.status_code < 500
                health["healthy"] = health["api_responsive"]
                health["checks"].append({
                    "name": "api_health",
                    "status": "pass" if health["api_responsive"] else "fail",
                    "message": f"API responded with status {response.status_code}",
                })
        except Exception as e:
            health["checks"].append({
                "name": "api_health",
                "status": "fail",
                "message": f"API check failed: {str(e)}",
            })

        return health
