"""
User Management Cog for VPS Deployer Discord Bot
"""
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class UserManagementCog(commands.Cog):
    """User Management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="user_info", description="Get information about your account")
    async def user_info(self, interaction: discord.Interaction):
        """Get information about your account"""
        await interaction.response.defer()
        
        try:
            # Get user from database
            user = await self.bot.database.get_user(interaction.user.id)
            
            if not user:
                # Create user if doesn't exist
                user_data = {
                    "discord_id": str(interaction.user.id),
                    "username": interaction.user.name,
                    "discriminator": interaction.user.discriminator,
                    "is_admin": self.bot.is_admin(interaction.user.id),
                    "is_active": True
                }
                user = await self.bot.database.create_user(user_data)
            
            # Get user's VMs
            vms = await self.bot.database.get_user_vms(interaction.user.id)
            
            # Get user's deployments
            deployments = await self.bot.database.get_user_deployments(interaction.user.id)
            
            # Calculate statistics
            total_vms = len(vms)
            running_vms = len([vm for vm in vms if vm["status"] == "running"])
            total_memory = sum(vm["memory"] for vm in vms)
            total_cores = sum(vm["cores"] for vm in vms)
            total_disk = sum(vm["disk_size"] for vm in vms)
            
            # Get recent activity
            recent_deployments = deployments[-5:] if deployments else []
            
            embed = discord.Embed(
                title=f"👤 User Information: {user['username']}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            # Basic info
            embed.add_field(name="Discord ID", value=str(user["discord_id"]), inline=True)
            embed.add_field(name="Username", value=user["username"], inline=True)
            embed.add_field(name="Admin", value="Yes" if user["is_admin"] else "No", inline=True)
            embed.add_field(name="Status", value="Active" if user["is_active"] else "Inactive", inline=True)
            embed.add_field(name="Member Since", value=user["created_at"].strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="Last Seen", value=user["last_seen"].strftime("%Y-%m-%d %H:%M"), inline=True)
            
            # VM statistics
            embed.add_field(
                name="📊 VM Statistics",
                value=f"**Total VMs:** {total_vms}\n"
                      f"**Running VMs:** {running_vms}\n"
                      f"**Total Memory:** {total_memory} MB\n"
                      f"**Total Cores:** {total_cores}\n"
                      f"**Total Disk:** {total_disk} GB",
                inline=False
            )
            
            # Recent activity
            if recent_deployments:
                activity_text = ""
                for deployment in recent_deployments:
                    status_emoji = "✅" if deployment["status"] == "completed" else "⏳" if deployment["status"] == "in_progress" else "❌"
                    activity_text += f"{status_emoji} {deployment['deployment_type']} - {deployment['created_at'].strftime('%m/%d %H:%M')}\n"
                
                embed.add_field(
                    name="📈 Recent Activity",
                    value=activity_text,
                    inline=False
                )
            
            # Permissions
            permissions = []
            if user["is_admin"]:
                permissions.append("Admin")
            if self.bot.has_permission(interaction.user):
                permissions.append("VPS Manager")
            if not permissions:
                permissions.append("User")
            
            embed.add_field(
                name="🔐 Permissions",
                value=", ".join(permissions),
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            await interaction.followup.send(f"❌ Failed to get user info: {str(e)}")
            
    @app_commands.command(name="user_vms", description="Get detailed list of your virtual machines")
    async def user_vms(self, interaction: discord.Interaction):
        """Get detailed list of your virtual machines"""
        await interaction.response.defer()
        
        try:
            # Get user's VMs
            vms = await self.bot.database.get_user_vms(interaction.user.id)
            
            if not vms:
                await interaction.followup.send("📝 You don't have any VMs yet.")
                return
                
            embed = discord.Embed(
                title="🖥️ Your Virtual Machines",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for vm in vms:
                status_emoji = "🟢" if vm["status"] == "running" else "🔴"
                
                # Get uptime if running
                uptime_text = "N/A"
                if vm["status"] == "running":
                    try:
                        status = await self.bot.proxmox.get_vm_status(vm["node"], vm["vm_id"])
                        if status.get("uptime"):
                            uptime_seconds = status["uptime"]
                            uptime_days = uptime_seconds // 86400
                            uptime_hours = (uptime_seconds % 86400) // 3600
                            uptime_minutes = (uptime_seconds % 3600) // 60
                            uptime_text = f"{uptime_days}d {uptime_hours}h {uptime_minutes}m"
                    except Exception as e:
                        logger.warning(f"Failed to get uptime for VM {vm['vm_id']}: {e}")
                
                embed.add_field(
                    name=f"{status_emoji} {vm['name']} (ID: {vm['vm_id']})",
                    value=f"**Template:** {vm['template']}\n"
                          f"**Resources:** {vm['memory']}MB RAM, {vm['cores']} cores, {vm['disk_size']}GB disk\n"
                          f"**Node:** {vm['node']}\n"
                          f"**IP:** {vm.get('ip_address', 'Not assigned')}\n"
                          f"**Uptime:** {uptime_text}\n"
                          f"**Created:** {vm['created_at'].strftime('%Y-%m-%d %H:%M')}",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting user VMs: {e}")
            await interaction.followup.send(f"❌ Failed to get user VMs: {str(e)}")
            
    @app_commands.command(name="user_deployments", description="Get your deployment history")
    @app_commands.describe(limit="Number of deployments to show (default: 10)")
    async def user_deployments(self, interaction: discord.Interaction, limit: Optional[int] = 10):
        """Get your deployment history"""
        await interaction.response.defer()
        
        try:
            # Get user's deployments
            deployments = await self.bot.database.get_user_deployments(interaction.user.id, limit)
            
            if not deployments:
                await interaction.followup.send("📝 No deployments found.")
                return
                
            embed = discord.Embed(
                title="🚀 Your Deployments",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for deployment in deployments:
                status_emoji = "✅" if deployment["status"] == "completed" else "⏳" if deployment["status"] == "in_progress" else "❌"
                
                embed.add_field(
                    name=f"{status_emoji} {deployment['deployment_type']} - {deployment['created_at'].strftime('%Y-%m-%d %H:%M')}",
                    value=f"**Status:** {deployment['status']}\n"
                          f"**Progress:** {deployment['progress']}%\n"
                          f"**VM ID:** {deployment.get('vm_id', 'N/A')}\n"
                          f"**Error:** {deployment.get('error_message', 'None')}",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting user deployments: {e}")
            await interaction.followup.send(f"❌ Failed to get user deployments: {str(e)}")
            
    @app_commands.command(name="user_stats", description="Get detailed statistics about your usage")
    async def user_stats(self, interaction: discord.Interaction):
        """Get detailed statistics about your usage"""
        await interaction.response.defer()
        
        try:
            # Get user's VMs
            vms = await self.bot.database.get_user_vms(interaction.user.id)
            
            # Get user's deployments
            deployments = await self.bot.database.get_user_deployments(interaction.user.id)
            
            # Calculate statistics
            total_vms = len(vms)
            running_vms = len([vm for vm in vms if vm["status"] == "running"])
            stopped_vms = len([vm for vm in vms if vm["status"] == "stopped"])
            
            total_memory = sum(vm["memory"] for vm in vms)
            total_cores = sum(vm["cores"] for vm in vms)
            total_disk = sum(vm["disk_size"] for vm in vms)
            
            # Deployment statistics
            total_deployments = len(deployments)
            completed_deployments = len([d for d in deployments if d["status"] == "completed"])
            failed_deployments = len([d for d in deployments if d["status"] == "failed"])
            in_progress_deployments = len([d for d in deployments if d["status"] == "in_progress"])
            
            # VM template usage
            template_usage = {}
            for vm in vms:
                template = vm["template"]
                template_usage[template] = template_usage.get(template, 0) + 1
            
            # Node usage
            node_usage = {}
            for vm in vms:
                node = vm["node"]
                node_usage[node] = node_usage.get(node, 0) + 1
            
            embed = discord.Embed(
                title="📊 Your Usage Statistics",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            # VM statistics
            embed.add_field(
                name="🖥️ VM Statistics",
                value=f"**Total VMs:** {total_vms}\n"
                      f"**Running:** {running_vms}\n"
                      f"**Stopped:** {stopped_vms}\n"
                      f"**Total Memory:** {total_memory} MB\n"
                      f"**Total Cores:** {total_cores}\n"
                      f"**Total Disk:** {total_disk} GB",
                inline=True
            )
            
            # Deployment statistics
            embed.add_field(
                name="🚀 Deployment Statistics",
                value=f"**Total Deployments:** {total_deployments}\n"
                      f"**Completed:** {completed_deployments}\n"
                      f"**Failed:** {failed_deployments}\n"
                      f"**In Progress:** {in_progress_deployments}\n"
                      f"**Success Rate:** {(completed_deployments/total_deployments*100):.1f}%" if total_deployments > 0 else "N/A",
                inline=True
            )
            
            # Template usage
            if template_usage:
                template_text = "\n".join([f"**{template}:** {count}" for template, count in template_usage.items()])
                embed.add_field(
                    name="📦 Template Usage",
                    value=template_text,
                    inline=True
                )
            
            # Node usage
            if node_usage:
                node_text = "\n".join([f"**{node}:** {count}" for node, count in node_usage.items()])
                embed.add_field(
                    name="🖥️ Node Usage",
                    value=node_text,
                    inline=True
                )
            
            # Resource limits
            max_vms = self.bot.database.settings.max_vms_per_user
            embed.add_field(
                name="📋 Limits",
                value=f"**Max VMs:** {max_vms}\n"
                      f"**Used VMs:** {total_vms}\n"
                      f"**Remaining:** {max_vms - total_vms}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            await interaction.followup.send(f"❌ Failed to get user stats: {str(e)}")
            
    @app_commands.command(name="user_cleanup", description="Clean up old deployments and logs")
    async def user_cleanup(self, interaction: discord.Interaction):
        """Clean up old deployments and logs"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to perform cleanup.")
                return
                
            # Clean up old deployments (older than 30 days)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            cleaned_deployments = await self.bot.database.cleanup_old_deployments(interaction.user.id, cutoff_date)
            
            # Clean up old audit logs (older than 90 days)
            audit_cutoff_date = datetime.utcnow() - timedelta(days=90)
            cleaned_audit_logs = await self.bot.database.cleanup_old_audit_logs(interaction.user.id, audit_cutoff_date)
            
            embed = discord.Embed(
                title="✅ Cleanup Completed",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Old Deployments Removed", value=str(cleaned_deployments), inline=True)
            embed.add_field(name="Old Audit Logs Removed", value=str(cleaned_audit_logs), inline=True)
            embed.add_field(name="Status", value="Cleanup completed successfully", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error performing cleanup: {e}")
            await interaction.followup.send(f"❌ Failed to perform cleanup: {str(e)}")
            
    @app_commands.command(name="user_export", description="Export your VM configurations")
    async def user_export(self, interaction: discord.Interaction):
        """Export your VM configurations"""
        await interaction.response.defer()
        
        try:
            # Get user's VMs
            vms = await self.bot.database.get_user_vms(interaction.user.id)
            
            if not vms:
                await interaction.followup.send("📝 No VMs to export.")
                return
                
            # Create export data
            export_data = {
                "user": {
                    "discord_id": str(interaction.user.id),
                    "username": interaction.user.name,
                    "export_date": datetime.utcnow().isoformat()
                },
                "vms": []
            }
            
            for vm in vms:
                vm_data = {
                    "name": vm["name"],
                    "vm_id": vm["vm_id"],
                    "template": vm["template"],
                    "memory": vm["memory"],
                    "cores": vm["cores"],
                    "disk_size": vm["disk_size"],
                    "node": vm["node"],
                    "storage": vm["storage"],
                    "network_bridge": vm["network_bridge"],
                    "ip_address": vm.get("ip_address"),
                    "mac_address": vm.get("mac_address"),
                    "ssh_port": vm.get("ssh_port"),
                    "created_at": vm["created_at"].isoformat(),
                    "last_modified": vm["last_modified"].isoformat()
                }
                export_data["vms"].append(vm_data)
            
            # Create JSON file
            json_data = json.dumps(export_data, indent=2)
            
            # Create file attachment
            file = discord.File(
                io.BytesIO(json_data.encode()),
                filename=f"vm_export_{interaction.user.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            embed = discord.Embed(
                title="📤 VM Export Complete",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VMs Exported", value=str(len(vms)), inline=True)
            embed.add_field(name="File Name", value=file.filename, inline=True)
            embed.add_field(name="Status", value="Export completed successfully", inline=True)
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            logger.error(f"Error exporting VMs: {e}")
            await interaction.followup.send(f"❌ Failed to export VMs: {str(e)}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(UserManagementCog(bot))