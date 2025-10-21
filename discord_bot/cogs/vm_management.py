"""
VM Management Cog for VPS Deployer Discord Bot
"""
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class VMManagementCog(commands.Cog):
    """VM Management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="vm_create", description="Create a new virtual machine")
    @app_commands.describe(
        name="Name for the VM",
        template="OS template to use",
        memory="Memory in MB (default: 2048)",
        cores="Number of CPU cores (default: 2)",
        disk="Disk size in GB (default: 32)",
        node="Proxmox node (optional)"
    )
    async def vm_create(
        self,
        interaction: discord.Interaction,
        name: str,
        template: str,
        memory: Optional[int] = 2048,
        cores: Optional[int] = 2,
        disk: Optional[int] = 32,
        node: Optional[str] = None
    ):
        """Create a new virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to create VMs.")
                return
                
            # Validate template
            if template not in self.bot.database.settings.available_templates:
                await interaction.followup.send(f"❌ Invalid template: {template}")
                return
                
            template_info = self.bot.database.settings.available_templates[template]
            
            # Validate resources
            if memory < template_info["min_memory"]:
                await interaction.followup.send(f"❌ Memory must be at least {template_info['min_memory']} MB")
                return
                
            if cores < template_info["min_cores"]:
                await interaction.followup.send(f"❌ Cores must be at least {template_info['min_cores']}")
                return
                
            if disk < template_info["min_disk"]:
                await interaction.followup.send(f"❌ Disk must be at least {template_info['min_disk']} GB")
                return
                
            # Get available nodes
            if not node:
                nodes = await self.bot.proxmox.get_nodes()
                if not nodes:
                    await interaction.followup.send("❌ No available nodes found")
                    return
                node = nodes[0]["node"]
                
            # Get next VM ID
            vmid = await self.bot.proxmox.get_next_vmid()
            
            # Create VM configuration
            vm_config = {
                "vmid": vmid,
                "name": name,
                "memory": memory,
                "cores": cores,
                "net0": f"virtio,bridge={self.bot.database.settings.default_network_bridge}",
                "scsi0": f"{self.bot.database.settings.default_storage}:{disk}",
                "ostype": "l26",
                "template": template_info["template_file"]
            }
            
            # Create VM
            result = await self.bot.proxmox.create_vm(node, vmid, vm_config)
            
            # Store in database
            vm_data = {
                "vm_id": vmid,
                "name": name,
                "template": template,
                "memory": memory,
                "cores": cores,
                "disk_size": disk,
                "node": node,
                "storage": self.bot.database.settings.default_storage,
                "network_bridge": self.bot.database.settings.default_network_bridge,
                "proxmox_config": vm_config
            }
            
            await self.bot.database.create_vm(interaction.user.id, vm_data)
            
            embed = discord.Embed(
                title="✅ VM Created Successfully",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Name", value=name, inline=True)
            embed.add_field(name="VM ID", value=str(vmid), inline=True)
            embed.add_field(name="Template", value=template_info["name"], inline=True)
            embed.add_field(name="Memory", value=f"{memory} MB", inline=True)
            embed.add_field(name="Cores", value=str(cores), inline=True)
            embed.add_field(name="Disk", value=f"{disk} GB", inline=True)
            embed.add_field(name="Node", value=node, inline=True)
            embed.add_field(name="Status", value="Stopped", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error creating VM: {e}")
            await interaction.followup.send(f"❌ Failed to create VM: {str(e)}")
            
    @app_commands.command(name="vm_list", description="List all your virtual machines")
    async def vm_list(self, interaction: discord.Interaction):
        """List all virtual machines"""
        await interaction.response.defer()
        
        try:
            vms = await self.bot.database.get_user_vms(interaction.user.id)
            
            if not vms:
                await interaction.followup.send("📝 You don't have any VMs yet.")
                return
                
            embed = discord.Embed(
                title="🖥️ Your Virtual Machines",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for vm in vms[:10]:  # Limit to 10 VMs
                status_emoji = "🟢" if vm["status"] == "running" else "🔴"
                embed.add_field(
                    name=f"{status_emoji} {vm['name']} (ID: {vm['vm_id']})",
                    value=f"**Template:** {vm['template']}\n"
                          f"**Resources:** {vm['memory']}MB RAM, {vm['cores']} cores, {vm['disk_size']}GB disk\n"
                          f"**Node:** {vm['node']}\n"
                          f"**IP:** {vm.get('ip_address', 'Not assigned')}",
                    inline=False
                )
                
            if len(vms) > 10:
                embed.set_footer(text=f"Showing 10 of {len(vms)} VMs")
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing VMs: {e}")
            await interaction.followup.send(f"❌ Failed to list VMs: {str(e)}")
            
    @app_commands.command(name="vm_start", description="Start a virtual machine")
    @app_commands.describe(vmid="VM ID to start")
    async def vm_start(self, interaction: discord.Interaction, vmid: int):
        """Start a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Start VM
            result = await self.bot.proxmox.start_vm(vm["node"], vmid)
            
            # Update status in database
            await self.bot.database.update_vm_status(vmid, "running")
            
            embed = discord.Embed(
                title="✅ VM Started",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=False)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            embed.add_field(name="Status", value="Starting...", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error starting VM: {e}")
            await interaction.followup.send(f"❌ Failed to start VM: {str(e)}")
            
    @app_commands.command(name="vm_stop", description="Stop a virtual machine")
    @app_commands.describe(vmid="VM ID to stop")
    async def vm_stop(self, interaction: discord.Interaction, vmid: int):
        """Stop a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Stop VM
            result = await self.bot.proxmox.stop_vm(vm["node"], vmid)
            
            # Update status in database
            await self.bot.database.update_vm_status(vmid, "stopped")
            
            embed = discord.Embed(
                title="✅ VM Stopped",
                color=0xff9900,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=False)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            embed.add_field(name="Status", value="Stopped", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error stopping VM: {e}")
            await interaction.followup.send(f"❌ Failed to stop VM: {str(e)}")
            
    @app_commands.command(name="vm_reboot", description="Reboot a virtual machine")
    @app_commands.describe(vmid="VM ID to reboot")
    async def vm_reboot(self, interaction: discord.Interaction, vmid: int):
        """Reboot a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Reboot VM
            result = await self.bot.proxmox.reboot_vm(vm["node"], vmid)
            
            embed = discord.Embed(
                title="✅ VM Rebooted",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=False)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            embed.add_field(name="Status", value="Rebooting...", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error rebooting VM: {e}")
            await interaction.followup.send(f"❌ Failed to reboot VM: {str(e)}")
            
    @app_commands.command(name="vm_delete", description="Delete a virtual machine")
    @app_commands.describe(vmid="VM ID to delete")
    async def vm_delete(self, interaction: discord.Interaction, vmid: int):
        """Delete a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Delete VM from Proxmox
            result = await self.bot.proxmox.delete_vm(vm["node"], vmid)
            
            # Delete from database
            await self.bot.database.delete_vm(vmid)
            
            embed = discord.Embed(
                title="✅ VM Deleted",
                color=0xff0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=False)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error deleting VM: {e}")
            await interaction.followup.send(f"❌ Failed to delete VM: {str(e)}")
            
    @app_commands.command(name="vm_info", description="Get detailed information about a VM")
    @app_commands.describe(vmid="VM ID to get info for")
    async def vm_info(self, interaction: discord.Interaction, vmid: int):
        """Get detailed VM information"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Get current status from Proxmox
            status = await self.bot.proxmox.get_vm_status(vm["node"], vmid)
            config = await self.bot.proxmox.get_vm_config(vm["node"], vmid)
            
            embed = discord.Embed(
                title=f"🖥️ {vm['name']} Information",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="VM ID", value=str(vmid), inline=True)
            embed.add_field(name="Status", value=status.get("status", "Unknown"), inline=True)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            embed.add_field(name="Template", value=vm["template"], inline=True)
            embed.add_field(name="Memory", value=f"{vm['memory']} MB", inline=True)
            embed.add_field(name="CPU Cores", value=str(vm["cores"]), inline=True)
            embed.add_field(name="Disk Size", value=f"{vm['disk_size']} GB", inline=True)
            embed.add_field(name="IP Address", value=vm.get("ip_address", "Not assigned"), inline=True)
            embed.add_field(name="MAC Address", value=vm.get("mac_address", "Not assigned"), inline=True)
            embed.add_field(name="Created", value=vm["created_at"].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            embed.add_field(name="Last Modified", value=vm["last_modified"].strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            
            if status.get("uptime"):
                uptime_seconds = status["uptime"]
                uptime_days = uptime_seconds // 86400
                uptime_hours = (uptime_seconds % 86400) // 3600
                uptime_minutes = (uptime_seconds % 3600) // 60
                embed.add_field(
                    name="Uptime",
                    value=f"{uptime_days}d {uptime_hours}h {uptime_minutes}m",
                    inline=True
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting VM info: {e}")
            await interaction.followup.send(f"❌ Failed to get VM info: {str(e)}")
            
    @app_commands.command(name="vm_clone", description="Clone an existing virtual machine")
    @app_commands.describe(
        vmid="VM ID to clone",
        new_name="Name for the cloned VM",
        new_vmid="VM ID for the clone (optional)"
    )
    async def vm_clone(
        self,
        interaction: discord.Interaction,
        vmid: int,
        new_name: str,
        new_vmid: Optional[int] = None
    ):
        """Clone a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Get next VM ID if not provided
            if not new_vmid:
                new_vmid = await self.bot.proxmox.get_next_vmid()
                
            # Clone VM
            clone_config = {
                "full": 1,  # Full clone
                "storage": vm["storage"]
            }
            
            result = await self.bot.proxmox.clone_vm(
                vm["node"], vmid, new_vmid, new_name, clone_config
            )
            
            # Store clone in database
            clone_data = {
                "vm_id": new_vmid,
                "name": new_name,
                "template": vm["template"],
                "memory": vm["memory"],
                "cores": vm["cores"],
                "disk_size": vm["disk_size"],
                "node": vm["node"],
                "storage": vm["storage"],
                "network_bridge": vm["network_bridge"],
                "proxmox_config": vm["proxmox_config"]
            }
            
            await self.bot.database.create_vm(interaction.user.id, clone_data)
            
            embed = discord.Embed(
                title="✅ VM Cloned Successfully",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Original VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Cloned VM", value=f"{new_name} (ID: {new_vmid})", inline=True)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            embed.add_field(name="Status", value="Stopped", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error cloning VM: {e}")
            await interaction.followup.send(f"❌ Failed to clone VM: {str(e)}")
            
    @app_commands.command(name="vm_resize", description="Resize VM disk")
    @app_commands.describe(
        vmid="VM ID to resize",
        new_size="New disk size in GB"
    )
    async def vm_resize(
        self,
        interaction: discord.Interaction,
        vmid: int,
        new_size: int
    ):
        """Resize VM disk"""
        await interaction.response.defer()
        
        try:
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            if new_size <= vm["disk_size"]:
                await interaction.followup.send("❌ New size must be larger than current size.")
                return
                
            # Resize disk
            disk = f"{vm['storage']}:vm-{vmid}-disk-0"
            result = await self.bot.proxmox.resize_disk(vm["node"], vmid, disk, f"{new_size}G")
            
            # Update database
            await self.bot.database.update_vm_disk_size(vmid, new_size)
            
            embed = discord.Embed(
                title="✅ VM Disk Resized",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Old Size", value=f"{vm['disk_size']} GB", inline=True)
            embed.add_field(name="New Size", value=f"{new_size} GB", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error resizing VM disk: {e}")
            await interaction.followup.send(f"❌ Failed to resize VM disk: {str(e)}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(VMManagementCog(bot))