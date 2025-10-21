"""
Node Management Cog for VPS Deployer Discord Bot
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

class NodeManagementCog(commands.Cog):
    """Node Management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="node_list", description="List all Proxmox nodes and their status")
    async def node_list(self, interaction: discord.Interaction):
        """List all Proxmox nodes"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view nodes.")
                return
                
            nodes = await self.bot.proxmox.get_nodes()
            
            if not nodes:
                await interaction.followup.send("❌ No nodes found.")
                return
                
            embed = discord.Embed(
                title="🖥️ Proxmox Nodes",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for node in nodes:
                try:
                    # Get node status
                    status = await self.bot.proxmox.get_node_status(node["node"])
                    
                    # Get node resources
                    resources = await self.bot.proxmox.get_node_resources(node["node"])
                    
                    # Calculate resource usage
                    cpu_usage = 0
                    memory_usage = 0
                    memory_total = 0
                    
                    if resources:
                        cpu_usage = resources.get("cpu", 0) * 100
                        memory_usage = resources.get("mem", 0) / 1024 / 1024 / 1024  # Convert to GB
                        memory_total = resources.get("maxmem", 0) / 1024 / 1024 / 1024  # Convert to GB
                    
                    status_emoji = "🟢" if status.get("status") == "online" else "🔴"
                    
                    embed.add_field(
                        name=f"{status_emoji} {node['node']}",
                        value=f"**Status:** {status.get('status', 'Unknown')}\n"
                              f"**CPU Usage:** {cpu_usage:.1f}%\n"
                              f"**Memory:** {memory_usage:.1f}GB / {memory_total:.1f}GB\n"
                              f"**Uptime:** {status.get('uptime', 0) // 86400} days",
                        inline=True
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to get status for node {node['node']}: {e}")
                    embed.add_field(
                        name=f"🔴 {node['node']}",
                        value="**Status:** Error\n**Details:** Unable to fetch status",
                        inline=True
                    )
                    
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing nodes: {e}")
            await interaction.followup.send(f"❌ Failed to list nodes: {str(e)}")
            
    @app_commands.command(name="node_info", description="Get detailed information about a specific node")
    @app_commands.describe(node="Node name to get info for")
    async def node_info(self, interaction: discord.Interaction, node: str):
        """Get detailed node information"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view node info.")
                return
                
            # Get node status
            status = await self.bot.proxmox.get_node_status(node)
            
            # Get node resources
            resources = await self.bot.proxmox.get_node_resources(node)
            
            # Get VMs on this node
            vms = await self.bot.proxmox.get_vms(node)
            
            embed = discord.Embed(
                title=f"🖥️ Node: {node}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            # Basic info
            embed.add_field(name="Status", value=status.get("status", "Unknown"), inline=True)
            embed.add_field(name="Uptime", value=f"{status.get('uptime', 0) // 86400} days", inline=True)
            embed.add_field(name="Load Average", value=status.get("loadavg", "N/A"), inline=True)
            
            # CPU info
            if resources:
                cpu_usage = resources.get("cpu", 0) * 100
                embed.add_field(name="CPU Usage", value=f"{cpu_usage:.1f}%", inline=True)
                
                # Memory info
                memory_used = resources.get("mem", 0) / 1024 / 1024 / 1024  # GB
                memory_total = resources.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                memory_percent = (memory_used / memory_total * 100) if memory_total > 0 else 0
                
                embed.add_field(
                    name="Memory",
                    value=f"{memory_used:.1f}GB / {memory_total:.1f}GB ({memory_percent:.1f}%)",
                    inline=True
                )
                
                # Disk info
                disk_used = resources.get("disk", 0) / 1024 / 1024 / 1024  # GB
                disk_total = resources.get("maxdisk", 0) / 1024 / 1024 / 1024  # GB
                disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
                
                embed.add_field(
                    name="Disk",
                    value=f"{disk_used:.1f}GB / {disk_total:.1f}GB ({disk_percent:.1f}%)",
                    inline=True
                )
            
            # VM count
            running_vms = len([vm for vm in vms if vm.get("status") == "running"])
            total_vms = len(vms)
            
            embed.add_field(name="VMs", value=f"{running_vms} running / {total_vms} total", inline=True)
            
            # Storage info
            try:
                storage = await self.bot.proxmox.get_storage(node)
                storage_info = []
                for store in storage[:5]:  # Limit to 5 storage devices
                    store_name = store.get("storage", "Unknown")
                    store_type = store.get("type", "Unknown")
                    storage_info.append(f"**{store_name}** ({store_type})")
                
                if storage_info:
                    embed.add_field(
                        name="Storage",
                        value="\n".join(storage_info),
                        inline=False
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to get storage info for node {node}: {e}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting node info: {e}")
            await interaction.followup.send(f"❌ Failed to get node info: {str(e)}")
            
    @app_commands.command(name="node_storage", description="Get storage information for a node")
    @app_commands.describe(node="Node name to get storage info for")
    async def node_storage(self, interaction: discord.Interaction, node: str):
        """Get storage information for a node"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view storage info.")
                return
                
            storage = await self.bot.proxmox.get_storage(node)
            
            if not storage:
                await interaction.followup.send("❌ No storage found on this node.")
                return
                
            embed = discord.Embed(
                title=f"💾 Storage: {node}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for store in storage:
                store_name = store.get("storage", "Unknown")
                store_type = store.get("type", "Unknown")
                store_status = store.get("status", "Unknown")
                
                # Calculate usage
                total_space = store.get("total", 0) / 1024 / 1024 / 1024  # GB
                used_space = store.get("used", 0) / 1024 / 1024 / 1024  # GB
                free_space = total_space - used_space
                usage_percent = (used_space / total_space * 100) if total_space > 0 else 0
                
                status_emoji = "🟢" if store_status == "available" else "🔴"
                
                embed.add_field(
                    name=f"{status_emoji} {store_name}",
                    value=f"**Type:** {store_type}\n"
                          f"**Status:** {store_status}\n"
                          f"**Used:** {used_space:.1f}GB / {total_space:.1f}GB ({usage_percent:.1f}%)\n"
                          f"**Free:** {free_space:.1f}GB",
                    inline=True
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting storage info: {e}")
            await interaction.followup.send(f"❌ Failed to get storage info: {str(e)}")
            
    @app_commands.command(name="node_network", description="Get network information for a node")
    @app_commands.describe(node="Node name to get network info for")
    async def node_network(self, interaction: discord.Interaction, node: str):
        """Get network information for a node"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view network info.")
                return
                
            networks = await self.bot.proxmox.get_networks(node)
            
            if not networks:
                await interaction.followup.send("❌ No network interfaces found on this node.")
                return
                
            embed = discord.Embed(
                title=f"🌐 Network: {node}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for network in networks:
                if_name = network.get("iface", "Unknown")
                if_type = network.get("type", "Unknown")
                if_status = network.get("status", "Unknown")
                
                # Get additional info
                method = network.get("method", "N/A")
                address = network.get("address", "N/A")
                netmask = network.get("netmask", "N/A")
                
                status_emoji = "🟢" if if_status == "up" else "🔴"
                
                embed.add_field(
                    name=f"{status_emoji} {if_name}",
                    value=f"**Type:** {if_type}\n"
                          f"**Status:** {if_status}\n"
                          f"**Method:** {method}\n"
                          f"**Address:** {address}\n"
                          f"**Netmask:** {netmask}",
                    inline=True
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            await interaction.followup.send(f"❌ Failed to get network info: {str(e)}")
            
    @app_commands.command(name="node_templates", description="Get available templates on a node")
    @app_commands.describe(
        node="Node name to get templates from",
        storage="Storage name (optional)"
    )
    async def node_templates(
        self,
        interaction: discord.Interaction,
        node: str,
        storage: Optional[str] = None
    ):
        """Get available templates on a node"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view templates.")
                return
                
            if not storage:
                # Get default storage
                storage = self.bot.database.settings.default_storage
                
            templates = await self.bot.proxmox.get_templates(node, storage)
            
            if not templates:
                await interaction.followup.send("❌ No templates found on this node.")
                return
                
            embed = discord.Embed(
                title=f"📦 Templates: {node}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for template in templates[:10]:  # Limit to 10 templates
                template_name = template.get("volid", "Unknown")
                template_size = template.get("size", 0) / 1024 / 1024 / 1024  # GB
                template_format = template.get("format", "Unknown")
                
                embed.add_field(
                    name=template_name,
                    value=f"**Size:** {template_size:.1f}GB\n"
                          f"**Format:** {template_format}",
                    inline=True
                )
                
            if len(templates) > 10:
                embed.set_footer(text=f"Showing 10 of {len(templates)} templates")
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting templates: {e}")
            await interaction.followup.send(f"❌ Failed to get templates: {str(e)}")
            
    @app_commands.command(name="node_migrate", description="Migrate a VM to another node")
    @app_commands.describe(
        vmid="VM ID to migrate",
        target_node="Target node name"
    )
    async def node_migrate(
        self,
        interaction: discord.Interaction,
        vmid: int,
        target_node: str
    ):
        """Migrate a VM to another node"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to migrate VMs.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Check if target node exists
            nodes = await self.bot.proxmox.get_nodes()
            target_node_exists = any(node["node"] == target_node for node in nodes)
            
            if not target_node_exists:
                await interaction.followup.send(f"❌ Target node '{target_node}' not found.")
                return
                
            # Migrate VM
            migrate_config = {
                "online": 1,  # Online migration
                "with-local-disks": 1
            }
            
            result = await self.bot.proxmox.migrate_vm(
                vm["node"], vmid, target_node, migrate_config
            )
            
            # Update VM node in database
            await self.bot.database.update_vm_node(vmid, target_node)
            
            embed = discord.Embed(
                title="✅ VM Migration Started",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Source Node", value=vm["node"], inline=True)
            embed.add_field(name="Target Node", value=target_node, inline=True)
            embed.add_field(name="Status", value="Migrating...", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error migrating VM: {e}")
            await interaction.followup.send(f"❌ Failed to migrate VM: {str(e)}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(NodeManagementCog(bot))