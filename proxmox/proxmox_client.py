"""
Proxmox API client for VPS Deployer Discord Bot
"""
import asyncio
import aiohttp
import ssl
from typing import Dict, List, Optional, Any, Tuple
from proxmoxer import ProxmoxAPI
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class ProxmoxClient:
    """Advanced Proxmox API client with async support"""
    
    def __init__(self, host: str, user: str, password: str, realm: str = "pam", verify_ssl: bool = True):
        self.host = host
        self.user = user
        self.password = password
        self.realm = realm
        self.verify_ssl = verify_ssl
        self.api = None
        self.session = None
        self._auth_ticket = None
        self._auth_csrf = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
        
    async def connect(self):
        """Connect to Proxmox API"""
        try:
            # Create SSL context
            ssl_context = ssl.create_default_context()
            if not self.verify_ssl:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
            # Create aiohttp session
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)
            
            # Authenticate
            await self._authenticate()
            
            # Initialize ProxmoxAPI
            self.api = ProxmoxAPI(
                self.host,
                user=f"{self.user}@{self.realm}",
                password=self.password,
                verify_ssl=self.verify_ssl
            )
            
            logger.info(f"Connected to Proxmox at {self.host}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Proxmox: {e}")
            raise
            
    async def disconnect(self):
        """Disconnect from Proxmox API"""
        if self.session:
            await self.session.close()
            
    async def _authenticate(self):
        """Authenticate with Proxmox API"""
        try:
            auth_url = f"https://{self.host}:8006/api2/json/access/ticket"
            auth_data = {
                "username": f"{self.user}@{self.realm}",
                "password": self.password
            }
            
            async with self.session.post(auth_url, data=auth_data) as response:
                if response.status == 200:
                    auth_result = await response.json()
                    self._auth_ticket = auth_result["data"]["ticket"]
                    self._auth_csrf = auth_result["data"]["CSRFPreventionToken"]
                    logger.info("Successfully authenticated with Proxmox")
                else:
                    raise Exception(f"Authentication failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise
            
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Proxmox API"""
        if not self.session:
            raise Exception("Not connected to Proxmox")
            
        url = f"https://{self.host}:8006/api2/json/{endpoint}"
        headers = {
            "Authorization": f"PVEAPIToken={self._auth_ticket}",
            "CSRFPreventionToken": self._auth_csrf
        }
        
        try:
            async with self.session.request(method, url, headers=headers, json=data) as response:
                result = await response.json()
                
                if response.status == 200:
                    return result
                else:
                    error_msg = result.get("errors", {}).get("message", "Unknown error")
                    raise Exception(f"API request failed: {error_msg}")
                    
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise
            
    # Node Management
    async def get_nodes(self) -> List[Dict]:
        """Get all Proxmox nodes"""
        result = await self._make_request("GET", "nodes")
        return result.get("data", [])
        
    async def get_node_status(self, node: str) -> Dict:
        """Get node status and resources"""
        result = await self._make_request("GET", f"nodes/{node}/status")
        return result.get("data", {})
        
    async def get_node_resources(self, node: str) -> Dict:
        """Get node resource usage"""
        result = await self._make_request("GET", f"nodes/{node}/rrddata?timeframe=hour")
        return result.get("data", {})
        
    # VM Management
    async def get_vms(self, node: Optional[str] = None) -> List[Dict]:
        """Get all VMs or VMs from specific node"""
        if node:
            result = await self._make_request("GET", f"nodes/{node}/qemu")
        else:
            # Get VMs from all nodes
            nodes = await self.get_nodes()
            all_vms = []
            for node_info in nodes:
                node_name = node_info["node"]
                try:
                    vms = await self._make_request("GET", f"nodes/{node_name}/qemu")
                    for vm in vms.get("data", []):
                        vm["node"] = node_name
                        all_vms.append(vm)
                except Exception as e:
                    logger.warning(f"Failed to get VMs from node {node_name}: {e}")
            return all_vms
            
        return result.get("data", [])
        
    async def get_vm_config(self, node: str, vmid: int) -> Dict:
        """Get VM configuration"""
        result = await self._make_request("GET", f"nodes/{node}/qemu/{vmid}/config")
        return result.get("data", {})
        
    async def get_vm_status(self, node: str, vmid: int) -> Dict:
        """Get VM status"""
        result = await self._make_request("GET", f"nodes/{node}/qemu/{vmid}/status/current")
        return result.get("data", {})
        
    async def create_vm(self, node: str, vmid: int, config: Dict) -> Dict:
        """Create a new VM"""
        result = await self._make_request("POST", f"nodes/{node}/qemu", data=config)
        return result.get("data", {})
        
    async def clone_vm(self, node: str, vmid: int, newid: int, name: str, config: Dict) -> Dict:
        """Clone an existing VM"""
        clone_data = {
            "newid": newid,
            "name": name,
            **config
        }
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/clone", data=clone_data)
        return result.get("data", {})
        
    async def start_vm(self, node: str, vmid: int) -> Dict:
        """Start a VM"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/status/start")
        return result.get("data", {})
        
    async def stop_vm(self, node: str, vmid: int) -> Dict:
        """Stop a VM"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/status/stop")
        return result.get("data", {})
        
    async def shutdown_vm(self, node: str, vmid: int) -> Dict:
        """Shutdown a VM gracefully"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/status/shutdown")
        return result.get("data", {})
        
    async def reboot_vm(self, node: str, vmid: int) -> Dict:
        """Reboot a VM"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/status/reboot")
        return result.get("data", {})
        
    async def delete_vm(self, node: str, vmid: int) -> Dict:
        """Delete a VM"""
        result = await self._make_request("DELETE", f"nodes/{node}/qemu/{vmid}")
        return result.get("data", {})
        
    async def migrate_vm(self, node: str, vmid: int, target_node: str, config: Dict) -> Dict:
        """Migrate a VM to another node"""
        migrate_data = {
            "target": target_node,
            **config
        }
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/migrate", data=migrate_data)
        return result.get("data", {})
        
    # VM Configuration
    async def update_vm_config(self, node: str, vmid: int, config: Dict) -> Dict:
        """Update VM configuration"""
        result = await self._make_request("PUT", f"nodes/{node}/qemu/{vmid}/config", data=config)
        return result.get("data", {})
        
    async def resize_disk(self, node: str, vmid: int, disk: str, size: str) -> Dict:
        """Resize VM disk"""
        resize_data = {
            "disk": disk,
            "size": size
        }
        result = await self._make_request("PUT", f"nodes/{node}/qemu/{vmid}/resize", data=resize_data)
        return result.get("data", {})
        
    # Snapshots
    async def create_snapshot(self, node: str, vmid: int, snapname: str, description: str = "") -> Dict:
        """Create VM snapshot"""
        snapshot_data = {
            "snapname": snapname,
            "description": description
        }
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/snapshot", data=snapshot_data)
        return result.get("data", {})
        
    async def get_snapshots(self, node: str, vmid: int) -> List[Dict]:
        """Get VM snapshots"""
        result = await self._make_request("GET", f"nodes/{node}/qemu/{vmid}/snapshot")
        return result.get("data", [])
        
    async def restore_snapshot(self, node: str, vmid: int, snapname: str) -> Dict:
        """Restore VM from snapshot"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/snapshot/{snapname}/rollback")
        return result.get("data", {})
        
    async def delete_snapshot(self, node: str, vmid: int, snapname: str) -> Dict:
        """Delete VM snapshot"""
        result = await self._make_request("DELETE", f"nodes/{node}/qemu/{vmid}/snapshot/{snapname}")
        return result.get("data", {})
        
    # Backups
    async def create_backup(self, node: str, vmid: int, backup_config: Dict) -> Dict:
        """Create VM backup"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/vzdump", data=backup_config)
        return result.get("data", {})
        
    async def get_backups(self, node: str, vmid: int) -> List[Dict]:
        """Get VM backups"""
        result = await self._make_request("GET", f"nodes/{node}/qemu/{vmid}/vzdump")
        return result.get("data", [])
        
    # Storage Management
    async def get_storage(self, node: str) -> List[Dict]:
        """Get storage information"""
        result = await self._make_request("GET", f"nodes/{node}/storage")
        return result.get("data", [])
        
    async def get_storage_content(self, node: str, storage: str) -> List[Dict]:
        """Get storage content"""
        result = await self._make_request("GET", f"nodes/{node}/storage/{storage}/content")
        return result.get("data", [])
        
    # Network Management
    async def get_networks(self, node: str) -> List[Dict]:
        """Get network interfaces"""
        result = await self._make_request("GET", f"nodes/{node}/network")
        return result.get("data", [])
        
    # Template Management
    async def get_templates(self, node: str, storage: str) -> List[Dict]:
        """Get available templates"""
        result = await self._make_request("GET", f"nodes/{node}/storage/{storage}/content")
        templates = []
        for item in result.get("data", []):
            if item.get("content") == "vztmpl":
                templates.append(item)
        return templates
        
    async def download_template(self, node: str, storage: str, template: str) -> Dict:
        """Download template to storage"""
        download_data = {
            "content": "vztmpl",
            "filename": template
        }
        result = await self._make_request("POST", f"nodes/{node}/storage/{storage}/download-url", data=download_data)
        return result.get("data", {})
        
    # Monitoring and Statistics
    async def get_vm_stats(self, node: str, vmid: int) -> Dict:
        """Get VM statistics"""
        result = await self._make_request("GET", f"nodes/{node}/qemu/{vmid}/rrddata?timeframe=hour")
        return result.get("data", {})
        
    async def get_node_stats(self, node: str) -> Dict:
        """Get node statistics"""
        result = await self._make_request("GET", f"nodes/{node}/rrddata?timeframe=hour")
        return result.get("data", {})
        
    # Console Access
    async def get_vnc_info(self, node: str, vmid: int) -> Dict:
        """Get VNC console information"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/vncproxy")
        return result.get("data", {})
        
    async def get_spice_info(self, node: str, vmid: int) -> Dict:
        """Get SPICE console information"""
        result = await self._make_request("POST", f"nodes/{node}/qemu/{vmid}/spice_remote")
        return result.get("data", {})
        
    # Utility Methods
    async def get_next_vmid(self) -> int:
        """Get next available VM ID"""
        result = await self._make_request("GET", "cluster/nextid")
        return result.get("data", 100)
        
    async def check_vmid_exists(self, vmid: int) -> bool:
        """Check if VM ID exists"""
        try:
            nodes = await self.get_nodes()
            for node_info in nodes:
                node_name = node_info["node"]
                vms = await self.get_vms(node_name)
                for vm in vms:
                    if vm["vmid"] == vmid:
                        return True
            return False
        except:
            return False
            
    async def get_vm_by_name(self, name: str) -> Optional[Dict]:
        """Get VM by name"""
        try:
            vms = await self.get_vms()
            for vm in vms:
                if vm.get("name") == name:
                    return vm
            return None
        except:
            return None