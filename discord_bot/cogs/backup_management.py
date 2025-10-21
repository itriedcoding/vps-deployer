"""
Backup Management Cog for VPS Deployer Discord Bot
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

class BackupManagementCog(commands.Cog):
    """Backup Management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="backup_create", description="Create a backup of a virtual machine")
    @app_commands.describe(
        vmid="VM ID to backup",
        backup_name="Name for the backup (optional)",
        compression="Compression type (gzip, lzo, zstd)",
        mode="Backup mode (snapshot, suspend, stop)"
    )
    async def backup_create(
        self,
        interaction: discord.Interaction,
        vmid: int,
        backup_name: Optional[str] = None,
        compression: Optional[str] = "gzip",
        mode: Optional[str] = "snapshot"
    ):
        """Create a backup of a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to create backups.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Generate backup name if not provided
            if not backup_name:
                backup_name = f"backup-{vm['name']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                
            # Create backup configuration
            backup_config = {
                "vmid": vmid,
                "storage": vm["storage"],
                "mode": mode,
                "compress": compression,
                "remove": 0,  # Don't remove old backups
                "mailto": "",  # No email notification
                "mailnotification": "never"
            }
            
            # Create backup
            result = await self.bot.proxmox.create_backup(vm["node"], vmid, backup_config)
            
            # Store backup info in database
            backup_data = {
                "backup_id": backup_name,
                "vm_id": vmid,
                "backup_type": "manual",
                "status": "in_progress",
                "backup_data": backup_config
            }
            
            await self.bot.database.create_backup(backup_data)
            
            embed = discord.Embed(
                title="✅ Backup Created",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Backup Name", value=backup_name, inline=True)
            embed.add_field(name="Mode", value=mode, inline=True)
            embed.add_field(name="Compression", value=compression, inline=True)
            embed.add_field(name="Status", value="In Progress", inline=True)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            await interaction.followup.send(f"❌ Failed to create backup: {str(e)}")
            
    @app_commands.command(name="backup_list", description="List all backups for a virtual machine")
    @app_commands.describe(vmid="VM ID to list backups for")
    async def backup_list(self, interaction: discord.Interaction, vmid: int):
        """List all backups for a virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view backups.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Get backups from Proxmox
            backups = await self.bot.proxmox.get_backups(vm["node"], vmid)
            
            if not backups:
                await interaction.followup.send("📝 No backups found for this VM.")
                return
                
            embed = discord.Embed(
                title=f"💾 Backups: {vm['name']}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for backup in backups[:10]:  # Limit to 10 backups
                backup_name = backup.get("volid", "Unknown")
                backup_size = backup.get("size", 0) / 1024 / 1024 / 1024  # GB
                backup_format = backup.get("format", "Unknown")
                backup_ctime = backup.get("ctime", 0)
                
                # Convert timestamp to readable date
                backup_date = datetime.fromtimestamp(backup_ctime).strftime("%Y-%m-%d %H:%M:%S")
                
                embed.add_field(
                    name=backup_name,
                    value=f"**Size:** {backup_size:.1f}GB\n"
                          f"**Format:** {backup_format}\n"
                          f"**Created:** {backup_date}",
                    inline=True
                )
                
            if len(backups) > 10:
                embed.set_footer(text=f"Showing 10 of {len(backups)} backups")
                
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            await interaction.followup.send(f"❌ Failed to list backups: {str(e)}")
            
    @app_commands.command(name="backup_restore", description="Restore a VM from backup")
    @app_commands.describe(
        vmid="VM ID to restore to",
        backup_name="Name of the backup to restore from"
    )
    async def backup_restore(
        self,
        interaction: discord.Interaction,
        vmid: int,
        backup_name: str
    ):
        """Restore a VM from backup"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to restore backups.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Check if backup exists
            backups = await self.bot.proxmox.get_backups(vm["node"], vmid)
            backup_exists = any(backup.get("volid") == backup_name for backup in backups)
            
            if not backup_exists:
                await interaction.followup.send(f"❌ Backup '{backup_name}' not found.")
                return
                
            # Restore from backup
            restore_config = {
                "vmid": vmid,
                "storage": vm["storage"],
                "force": 1  # Force restore
            }
            
            result = await self.bot.proxmox.restore_backup(vm["node"], backup_name, restore_config)
            
            embed = discord.Embed(
                title="✅ Backup Restore Started",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Backup", value=backup_name, inline=True)
            embed.add_field(name="Status", value="Restoring...", inline=True)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            await interaction.followup.send(f"❌ Failed to restore backup: {str(e)}")
            
    @app_commands.command(name="backup_delete", description="Delete a backup")
    @app_commands.describe(
        vmid="VM ID that the backup belongs to",
        backup_name="Name of the backup to delete"
    )
    async def backup_delete(
        self,
        interaction: discord.Interaction,
        vmid: int,
        backup_name: str
    ):
        """Delete a backup"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to delete backups.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Check if backup exists
            backups = await self.bot.proxmox.get_backups(vm["node"], vmid)
            backup_exists = any(backup.get("volid") == backup_name for backup in backups)
            
            if not backup_exists:
                await interaction.followup.send(f"❌ Backup '{backup_name}' not found.")
                return
                
            # Delete backup
            result = await self.bot.proxmox.delete_backup(vm["node"], backup_name)
            
            # Remove from database
            await self.bot.database.delete_backup(backup_name)
            
            embed = discord.Embed(
                title="✅ Backup Deleted",
                color=0xff0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Backup", value=backup_name, inline=True)
            embed.add_field(name="Status", value="Deleted", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error deleting backup: {e}")
            await interaction.followup.send(f"❌ Failed to delete backup: {str(e)}")
            
    @app_commands.command(name="backup_schedule", description="Schedule automatic backups for a VM")
    @app_commands.describe(
        vmid="VM ID to schedule backups for",
        schedule="Cron schedule (e.g., '0 2 * * *' for daily at 2 AM)",
        retention="Number of backups to keep",
        compression="Compression type (gzip, lzo, zstd)"
    )
    async def backup_schedule(
        self,
        interaction: discord.Interaction,
        vmid: int,
        schedule: str,
        retention: Optional[int] = 7,
        compression: Optional[str] = "gzip"
    ):
        """Schedule automatic backups for a VM"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to schedule backups.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Create backup schedule
            schedule_config = {
                "vmid": vmid,
                "storage": vm["storage"],
                "schedule": schedule,
                "retention": retention,
                "compress": compression,
                "mode": "snapshot",
                "enabled": 1
            }
            
            # Store schedule in database
            await self.bot.database.create_backup_schedule(vmid, schedule_config)
            
            embed = discord.Embed(
                title="✅ Backup Schedule Created",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Schedule", value=schedule, inline=True)
            embed.add_field(name="Retention", value=f"{retention} backups", inline=True)
            embed.add_field(name="Compression", value=compression, inline=True)
            embed.add_field(name="Status", value="Active", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error scheduling backup: {e}")
            await interaction.followup.send(f"❌ Failed to schedule backup: {str(e)}")
            
    @app_commands.command(name="backup_unschedule", description="Remove backup schedule for a VM")
    @app_commands.describe(vmid="VM ID to remove backup schedule for")
    async def backup_unschedule(self, interaction: discord.Interaction, vmid: int):
        """Remove backup schedule for a VM"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to modify backup schedules.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Remove backup schedule
            await self.bot.database.delete_backup_schedule(vmid)
            
            embed = discord.Embed(
                title="✅ Backup Schedule Removed",
                color=0xff9900,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Status", value="Schedule Removed", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error removing backup schedule: {e}")
            await interaction.followup.send(f"❌ Failed to remove backup schedule: {str(e)}")
            
    @app_commands.command(name="backup_cleanup", description="Clean up old backups based on retention policy")
    @app_commands.describe(vmid="VM ID to clean up backups for")
    async def backup_cleanup(self, interaction: discord.Interaction, vmid: int):
        """Clean up old backups based on retention policy"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to clean up backups.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Get backup schedule
            schedule = await self.bot.database.get_backup_schedule(vmid)
            if not schedule:
                await interaction.followup.send("❌ No backup schedule found for this VM.")
                return
                
            retention = schedule.get("retention", 7)
            
            # Get all backups
            backups = await self.bot.proxmox.get_backups(vm["node"], vmid)
            
            if len(backups) <= retention:
                await interaction.followup.send("📝 No backups to clean up.")
                return
                
            # Sort backups by creation time (newest first)
            backups.sort(key=lambda x: x.get("ctime", 0), reverse=True)
            
            # Delete old backups
            deleted_count = 0
            for backup in backups[retention:]:
                try:
                    await self.bot.proxmox.delete_backup(vm["node"], backup["volid"])
                    await self.bot.database.delete_backup(backup["volid"])
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete backup {backup['volid']}: {e}")
                    
            embed = discord.Embed(
                title="✅ Backup Cleanup Completed",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="VM", value=f"{vm['name']} (ID: {vmid})", inline=True)
            embed.add_field(name="Retention Policy", value=f"{retention} backups", inline=True)
            embed.add_field(name="Deleted", value=f"{deleted_count} old backups", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            await interaction.followup.send(f"❌ Failed to clean up backups: {str(e)}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(BackupManagementCog(bot))