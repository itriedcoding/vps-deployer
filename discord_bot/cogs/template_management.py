"""
Template Management Cog for VPS Deployer Discord Bot
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

class TemplateManagementCog(commands.Cog):
    """Template Management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="template_list", description="List all available OS templates")
    async def template_list(self, interaction: discord.Interaction):
        """List all available OS templates"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view templates.")
                return
                
            templates = self.bot.database.settings.available_templates
            
            if not templates:
                await interaction.followup.send("❌ No templates available.")
                return
                
            embed = discord.Embed(
                title="📦 Available OS Templates",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for template_id, template_info in templates.items():
                embed.add_field(
                    name=f"🐧 {template_info['name']}",
                    value=f"**ID:** `{template_id}`\n"
                          f"**Min Memory:** {template_info['min_memory']} MB\n"
                          f"**Min Cores:** {template_info['min_cores']}\n"
                          f"**Min Disk:** {template_info['min_disk']} GB\n"
                          f"**Default User:** {template_info['default_user']}\n"
                          f"**SSH Port:** {template_info['ssh_port']}",
                    inline=True
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            await interaction.followup.send(f"❌ Failed to list templates: {str(e)}")
            
    @app_commands.command(name="template_info", description="Get detailed information about a specific template")
    @app_commands.describe(template_id="Template ID to get info for")
    async def template_info(self, interaction: discord.Interaction, template_id: str):
        """Get detailed information about a specific template"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view template info.")
                return
                
            templates = self.bot.database.settings.available_templates
            
            if template_id not in templates:
                await interaction.followup.send(f"❌ Template '{template_id}' not found.")
                return
                
            template_info = templates[template_id]
            
            embed = discord.Embed(
                title=f"📦 Template: {template_info['name']}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="Template ID", value=template_id, inline=True)
            embed.add_field(name="Display Name", value=template_info['name'], inline=True)
            embed.add_field(name="Template File", value=template_info['template_file'], inline=True)
            embed.add_field(name="Minimum Memory", value=f"{template_info['min_memory']} MB", inline=True)
            embed.add_field(name="Minimum Cores", value=str(template_info['min_cores']), inline=True)
            embed.add_field(name="Minimum Disk", value=f"{template_info['min_disk']} GB", inline=True)
            embed.add_field(name="Default User", value=template_info['default_user'], inline=True)
            embed.add_field(name="SSH Port", value=str(template_info['ssh_port']), inline=True)
            
            # Check if template is available on nodes
            nodes = await self.bot.proxmox.get_nodes()
            available_nodes = []
            
            for node in nodes:
                try:
                    storage = self.bot.database.settings.default_storage
                    node_templates = await self.bot.proxmox.get_templates(node["node"], storage)
                    
                    template_available = any(
                        template.get("volid") == template_info['template_file']
                        for template in node_templates
                    )
                    
                    if template_available:
                        available_nodes.append(node["node"])
                        
                except Exception as e:
                    logger.warning(f"Failed to check template availability on node {node['node']}: {e}")
            
            if available_nodes:
                embed.add_field(
                    name="Available On Nodes",
                    value=", ".join(available_nodes),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Available On Nodes",
                    value="Not available on any node",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting template info: {e}")
            await interaction.followup.send(f"❌ Failed to get template info: {str(e)}")
            
    @app_commands.command(name="template_download", description="Download a template to a specific node")
    @app_commands.describe(
        template_id="Template ID to download",
        node="Node to download template to",
        storage="Storage to download template to (optional)"
    )
    async def template_download(
        self,
        interaction: discord.Interaction,
        template_id: str,
        node: str,
        storage: Optional[str] = None
    ):
        """Download a template to a specific node"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to download templates.")
                return
                
            templates = self.bot.database.settings.available_templates
            
            if template_id not in templates:
                await interaction.followup.send(f"❌ Template '{template_id}' not found.")
                return
                
            template_info = templates[template_id]
            
            if not storage:
                storage = self.bot.database.settings.default_storage
                
            # Download template
            result = await self.bot.proxmox.download_template(node, storage, template_info['template_file'])
            
            embed = discord.Embed(
                title="✅ Template Download Started",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Template", value=template_info['name'], inline=True)
            embed.add_field(name="Node", value=node, inline=True)
            embed.add_field(name="Storage", value=storage, inline=True)
            embed.add_field(name="Status", value="Downloading...", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error downloading template: {e}")
            await interaction.followup.send(f"❌ Failed to download template: {str(e)}")
            
    @app_commands.command(name="template_check", description="Check template availability on all nodes")
    @app_commands.describe(template_id="Template ID to check")
    async def template_check(self, interaction: discord.Interaction, template_id: str):
        """Check template availability on all nodes"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to check templates.")
                return
                
            templates = self.bot.database.settings.available_templates
            
            if template_id not in templates:
                await interaction.followup.send(f"❌ Template '{template_id}' not found.")
                return
                
            template_info = templates[template_id]
            
            # Check all nodes
            nodes = await self.bot.proxmox.get_nodes()
            available_nodes = []
            unavailable_nodes = []
            
            for node in nodes:
                try:
                    storage = self.bot.database.settings.default_storage
                    node_templates = await self.bot.proxmox.get_templates(node["node"], storage)
                    
                    template_available = any(
                        template.get("volid") == template_info['template_file']
                        for template in node_templates
                    )
                    
                    if template_available:
                        available_nodes.append(node["node"])
                    else:
                        unavailable_nodes.append(node["node"])
                        
                except Exception as e:
                    logger.warning(f"Failed to check template on node {node['node']}: {e}")
                    unavailable_nodes.append(f"{node['node']} (Error)")
            
            embed = discord.Embed(
                title=f"📦 Template Check: {template_info['name']}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            if available_nodes:
                embed.add_field(
                    name="✅ Available On",
                    value="\n".join(available_nodes),
                    inline=True
                )
            
            if unavailable_nodes:
                embed.add_field(
                    name="❌ Not Available On",
                    value="\n".join(unavailable_nodes),
                    inline=True
                )
            
            if not available_nodes and not unavailable_nodes:
                embed.add_field(
                    name="Status",
                    value="No nodes checked",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking template: {e}")
            await interaction.followup.send(f"❌ Failed to check template: {str(e)}")
            
    @app_commands.command(name="template_create", description="Create a new template from an existing VM")
    @app_commands.describe(
        vmid="VM ID to create template from",
        template_name="Name for the new template",
        description="Description for the template"
    )
    async def template_create(
        self,
        interaction: discord.Interaction,
        vmid: int,
        template_name: str,
        description: Optional[str] = ""
    ):
        """Create a new template from an existing VM"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to create templates.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Stop VM if running
            status = await self.bot.proxmox.get_vm_status(vm["node"], vmid)
            if status.get("status") == "running":
                await self.bot.proxmox.stop_vm(vm["node"], vmid)
                await asyncio.sleep(5)  # Wait for VM to stop
                
            # Convert VM to template
            template_config = {
                "vmid": vmid,
                "template": 1
            }
            
            result = await self.bot.proxmox.update_vm_config(vm["node"], vmid, template_config)
            
            # Store template in database
            template_data = {
                "name": template_name,
                "display_name": template_name,
                "description": description,
                "template_file": f"vztmpl/{template_name}.tar.zst",
                "min_memory": vm["memory"],
                "min_cores": vm["cores"],
                "min_disk": vm["disk_size"],
                "default_user": "root",
                "ssh_port": 22,
                "is_active": True,
                "metadata": {
                    "created_from_vm": vmid,
                    "created_by": interaction.user.id,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            await self.bot.database.create_template(template_data)
            
            embed = discord.Embed(
                title="✅ Template Created",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Template Name", value=template_name, inline=True)
            embed.add_field(name="Source VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            embed.add_field(name="Description", value=description or "No description", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            await interaction.followup.send(f"❌ Failed to create template: {str(e)}")
            
    @app_commands.command(name="template_delete", description="Delete a custom template")
    @app_commands.describe(template_name="Name of the template to delete")
    async def template_delete(self, interaction: discord.Interaction, template_name: str):
        """Delete a custom template"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to delete templates.")
                return
                
            # Check if template exists
            template = await self.bot.database.get_template_by_name(template_name)
            if not template:
                await interaction.followup.send(f"❌ Template '{template_name}' not found.")
                return
                
            # Check if user created this template
            if template.get("created_by") != interaction.user.id:
                await interaction.followup.send("❌ You can only delete templates you created.")
                return
                
            # Delete template from database
            await self.bot.database.delete_template(template_name)
            
            embed = discord.Embed(
                title="✅ Template Deleted",
                color=0xff0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Template Name", value=template_name, inline=True)
            embed.add_field(name="Status", value="Deleted", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error deleting template: {e}")
            await interaction.followup.send(f"❌ Failed to delete template: {str(e)}")
            
    @app_commands.command(name="template_update", description="Update template information")
    @app_commands.describe(
        template_name="Name of the template to update",
        new_name="New name for the template (optional)",
        description="New description for the template (optional)",
        min_memory="New minimum memory requirement (optional)",
        min_cores="New minimum cores requirement (optional)",
        min_disk="New minimum disk requirement (optional)"
    )
    async def template_update(
        self,
        interaction: discord.Interaction,
        template_name: str,
        new_name: Optional[str] = None,
        description: Optional[str] = None,
        min_memory: Optional[int] = None,
        min_cores: Optional[int] = None,
        min_disk: Optional[int] = None
    ):
        """Update template information"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to update templates.")
                return
                
            # Check if template exists
            template = await self.bot.database.get_template_by_name(template_name)
            if not template:
                await interaction.followup.send(f"❌ Template '{template_name}' not found.")
                return
                
            # Check if user created this template
            if template.get("created_by") != interaction.user.id:
                await interaction.followup.send("❌ You can only update templates you created.")
                return
                
            # Prepare update data
            update_data = {}
            if new_name:
                update_data["name"] = new_name
                update_data["display_name"] = new_name
            if description is not None:
                update_data["description"] = description
            if min_memory is not None:
                update_data["min_memory"] = min_memory
            if min_cores is not None:
                update_data["min_cores"] = min_cores
            if min_disk is not None:
                update_data["min_disk"] = min_disk
                
            if not update_data:
                await interaction.followup.send("❌ No updates provided.")
                return
                
            # Update template
            await self.bot.database.update_template(template_name, update_data)
            
            embed = discord.Embed(
                title="✅ Template Updated",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Template", value=template_name, inline=True)
            
            for key, value in update_data.items():
                embed.add_field(name=key.replace("_", " ").title(), value=str(value), inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating template: {e}")
            await interaction.followup.send(f"❌ Failed to update template: {str(e)}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(TemplateManagementCog(bot))