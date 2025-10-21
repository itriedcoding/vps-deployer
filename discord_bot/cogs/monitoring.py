"""
Monitoring Cog for VPS Deployer Discord Bot
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

class MonitoringCog(commands.Cog):
    """Monitoring commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="monitor_status", description="Get overall system status")
    async def monitor_status(self, interaction: discord.Interaction):
        """Get overall system status"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view system status.")
                return
                
            # Get all nodes
            nodes = await self.bot.proxmox.get_nodes()
            
            if not nodes:
                await interaction.followup.send("❌ No nodes found.")
                return
                
            embed = discord.Embed(
                title="📊 System Status",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            total_vms = 0
            running_vms = 0
            total_memory = 0
            used_memory = 0
            total_cpu = 0
            used_cpu = 0
            
            for node in nodes:
                try:
                    # Get node status
                    status = await self.bot.proxmox.get_node_status(node["node"])
                    
                    # Get node resources
                    resources = await self.bot.proxmox.get_node_resources(node["node"])
                    
                    # Get VMs on this node
                    vms = await self.bot.proxmox.get_vms(node["node"])
                    
                    # Count VMs
                    node_vms = len(vms)
                    node_running = len([vm for vm in vms if vm.get("status") == "running"])
                    total_vms += node_vms
                    running_vms += node_running
                    
                    # Calculate resources
                    if resources:
                        node_cpu = resources.get("cpu", 0) * 100
                        node_memory = resources.get("mem", 0) / 1024 / 1024 / 1024  # GB
                        node_max_memory = resources.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                        
                        total_cpu += 100  # Assume 100% per node
                        used_cpu += node_cpu
                        total_memory += node_max_memory
                        used_memory += node_memory
                    
                    # Add node info to embed
                    status_emoji = "🟢" if status.get("status") == "online" else "🔴"
                    embed.add_field(
                        name=f"{status_emoji} {node['node']}",
                        value=f"**VMs:** {node_running}/{node_vms} running\n"
                              f"**CPU:** {node_cpu:.1f}%\n"
                              f"**Memory:** {node_memory:.1f}GB / {node_max_memory:.1f}GB",
                        inline=True
                    )
                    
                except Exception as e:
                    logger.warning(f"Failed to get status for node {node['node']}: {e}")
                    embed.add_field(
                        name=f"🔴 {node['node']}",
                        value="**Status:** Error\n**Details:** Unable to fetch status",
                        inline=True
                    )
            
            # Overall stats
            overall_cpu = (used_cpu / total_cpu * 100) if total_cpu > 0 else 0
            overall_memory = (used_memory / total_memory * 100) if total_memory > 0 else 0
            
            embed.add_field(
                name="📈 Overall Statistics",
                value=f"**Total VMs:** {running_vms}/{total_vms} running\n"
                      f"**CPU Usage:** {overall_cpu:.1f}%\n"
                      f"**Memory Usage:** {overall_memory:.1f}%",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            await interaction.followup.send(f"❌ Failed to get system status: {str(e)}")
            
    @app_commands.command(name="monitor_vm", description="Monitor a specific virtual machine")
    @app_commands.describe(vmid="VM ID to monitor")
    async def monitor_vm(self, interaction: discord.Interaction, vmid: int):
        """Monitor a specific virtual machine"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to monitor VMs.")
                return
                
            # Check if user owns this VM
            vm = await self.bot.database.get_vm_by_id(vmid)
            if not vm or vm["owner_id"] != interaction.user.id:
                await interaction.followup.send("❌ VM not found or you don't own it.")
                return
                
            # Get VM status
            status = await self.bot.proxmox.get_vm_status(vm["node"], vmid)
            
            # Get VM statistics
            stats = await self.bot.proxmox.get_vm_stats(vm["node"], vmid)
            
            embed = discord.Embed(
                title=f"📊 VM Monitor: {vm['name']}",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            # Basic info
            embed.add_field(name="VM ID", value=str(vmid), inline=True)
            embed.add_field(name="Status", value=status.get("status", "Unknown"), inline=True)
            embed.add_field(name="Node", value=vm["node"], inline=True)
            
            # Uptime
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
            
            # Resource usage
            if stats:
                cpu_usage = stats.get("cpu", 0) * 100
                memory_usage = stats.get("mem", 0) / 1024 / 1024 / 1024  # GB
                memory_total = stats.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                memory_percent = (memory_usage / memory_total * 100) if memory_total > 0 else 0
                
                embed.add_field(name="CPU Usage", value=f"{cpu_usage:.1f}%", inline=True)
                embed.add_field(
                    name="Memory Usage",
                    value=f"{memory_usage:.1f}GB / {memory_total:.1f}GB ({memory_percent:.1f}%)",
                    inline=True
                )
                
                # Network stats
                net_in = stats.get("netin", 0) / 1024 / 1024  # MB
                net_out = stats.get("netout", 0) / 1024 / 1024  # MB
                embed.add_field(name="Network In", value=f"{net_in:.1f} MB", inline=True)
                embed.add_field(name="Network Out", value=f"{net_out:.1f} MB", inline=True)
                
                # Disk stats
                disk_read = stats.get("diskread", 0) / 1024 / 1024  # MB
                disk_write = stats.get("diskwrite", 0) / 1024 / 1024  # MB
                embed.add_field(name="Disk Read", value=f"{disk_read:.1f} MB", inline=True)
                embed.add_field(name="Disk Write", value=f"{disk_write:.1f} MB", inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error monitoring VM: {e}")
            await interaction.followup.send(f"❌ Failed to monitor VM: {str(e)}")
            
    @app_commands.command(name="monitor_alerts", description="Get system alerts and warnings")
    async def monitor_alerts(self, interaction: discord.Interaction):
        """Get system alerts and warnings"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view alerts.")
                return
                
            alerts = []
            
            # Check all nodes
            nodes = await self.bot.proxmox.get_nodes()
            for node in nodes:
                try:
                    # Get node status
                    status = await self.bot.proxmox.get_node_status(node["node"])
                    
                    # Get node resources
                    resources = await self.bot.proxmox.get_node_resources(node["node"])
                    
                    # Check for alerts
                    if status.get("status") != "online":
                        alerts.append({
                            "type": "error",
                            "node": node["node"],
                            "message": f"Node is {status.get('status', 'unknown')}"
                        })
                    
                    if resources:
                        cpu_usage = resources.get("cpu", 0) * 100
                        memory_usage = resources.get("mem", 0) / 1024 / 1024 / 1024  # GB
                        memory_total = resources.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                        memory_percent = (memory_usage / memory_total * 100) if memory_total > 0 else 0
                        
                        if cpu_usage > 90:
                            alerts.append({
                                "type": "warning",
                                "node": node["node"],
                                "message": f"High CPU usage: {cpu_usage:.1f}%"
                            })
                        
                        if memory_percent > 90:
                            alerts.append({
                                "type": "warning",
                                "node": node["node"],
                                "message": f"High memory usage: {memory_percent:.1f}%"
                            })
                    
                    # Check VMs on this node
                    vms = await self.bot.proxmox.get_vms(node["node"])
                    for vm in vms:
                        if vm.get("status") == "running":
                            try:
                                vm_stats = await self.bot.proxmox.get_vm_stats(node["node"], vm["vmid"])
                                if vm_stats:
                                    vm_cpu = vm_stats.get("cpu", 0) * 100
                                    vm_memory = vm_stats.get("mem", 0) / 1024 / 1024 / 1024  # GB
                                    vm_max_memory = vm_stats.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                                    vm_memory_percent = (vm_memory / vm_max_memory * 100) if vm_max_memory > 0 else 0
                                    
                                    if vm_cpu > 95:
                                        alerts.append({
                                            "type": "warning",
                                            "node": node["node"],
                                            "message": f"VM {vm['name']} high CPU usage: {vm_cpu:.1f}%"
                                        })
                                    
                                    if vm_memory_percent > 95:
                                        alerts.append({
                                            "type": "warning",
                                            "node": node["node"],
                                            "message": f"VM {vm['name']} high memory usage: {vm_memory_percent:.1f}%"
                                        })
                            except Exception as e:
                                logger.warning(f"Failed to get stats for VM {vm['vmid']}: {e}")
                    
                except Exception as e:
                    logger.warning(f"Failed to check alerts for node {node['node']}: {e}")
                    alerts.append({
                        "type": "error",
                        "node": node["node"],
                        "message": f"Failed to check node status: {str(e)}"
                    })
            
            # Create embed
            if not alerts:
                embed = discord.Embed(
                    title="✅ No Alerts",
                    description="All systems are running normally.",
                    color=0x00ff00,
                    timestamp=datetime.utcnow()
                )
            else:
                embed = discord.Embed(
                    title="⚠️ System Alerts",
                    color=0xff9900,
                    timestamp=datetime.utcnow()
                )
                
                for alert in alerts[:10]:  # Limit to 10 alerts
                    alert_emoji = "🔴" if alert["type"] == "error" else "⚠️"
                    embed.add_field(
                        name=f"{alert_emoji} {alert['node']}",
                        value=alert["message"],
                        inline=False
                    )
                
                if len(alerts) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(alerts)} alerts")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            await interaction.followup.send(f"❌ Failed to get alerts: {str(e)}")
            
    @app_commands.command(name="monitor_logs", description="Get recent system logs")
    @app_commands.describe(
        node="Node to get logs from (optional)",
        lines="Number of log lines to show (default: 50)"
    )
    async def monitor_logs(
        self,
        interaction: discord.Interaction,
        node: Optional[str] = None,
        lines: Optional[int] = 50
    ):
        """Get recent system logs"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to view logs.")
                return
                
            # Get nodes
            if node:
                nodes = [{"node": node}]
            else:
                nodes = await self.bot.proxmox.get_nodes()
            
            if not nodes:
                await interaction.followup.send("❌ No nodes found.")
                return
                
            embed = discord.Embed(
                title="📋 System Logs",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            for node_info in nodes[:3]:  # Limit to 3 nodes
                try:
                    # Get logs from node
                    logs = await self.bot.proxmox.get_logs(node_info["node"], lines)
                    
                    if logs:
                        log_text = "\n".join(logs[:10])  # Limit to 10 lines per node
                        if len(logs) > 10:
                            log_text += f"\n... and {len(logs) - 10} more lines"
                        
                        embed.add_field(
                            name=f"📋 {node_info['node']}",
                            value=f"```\n{log_text}\n```",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name=f"📋 {node_info['node']}",
                            value="No logs available",
                            inline=False
                        )
                        
                except Exception as e:
                    logger.warning(f"Failed to get logs for node {node_info['node']}: {e}")
                    embed.add_field(
                        name=f"📋 {node_info['node']}",
                        value=f"Error: {str(e)}",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            await interaction.followup.send(f"❌ Failed to get logs: {str(e)}")
            
    @app_commands.command(name="monitor_health", description="Perform a comprehensive health check")
    async def monitor_health(self, interaction: discord.Interaction):
        """Perform a comprehensive health check"""
        await interaction.response.defer()
        
        try:
            # Check permissions
            if not self.bot.has_permission(interaction.user):
                await interaction.followup.send("❌ You don't have permission to perform health checks.")
                return
                
            health_checks = []
            
            # Check all nodes
            nodes = await self.bot.proxmox.get_nodes()
            for node in nodes:
                try:
                    # Get node status
                    status = await self.bot.proxmox.get_node_status(node["node"])
                    
                    # Get node resources
                    resources = await self.bot.proxmox.get_node_resources(node["node"])
                    
                    # Check node health
                    node_health = {
                        "node": node["node"],
                        "status": "healthy",
                        "issues": []
                    }
                    
                    if status.get("status") != "online":
                        node_health["status"] = "unhealthy"
                        node_health["issues"].append(f"Node is {status.get('status', 'unknown')}")
                    
                    if resources:
                        cpu_usage = resources.get("cpu", 0) * 100
                        memory_usage = resources.get("mem", 0) / 1024 / 1024 / 1024  # GB
                        memory_total = resources.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                        memory_percent = (memory_usage / memory_total * 100) if memory_total > 0 else 0
                        
                        if cpu_usage > 80:
                            node_health["issues"].append(f"High CPU usage: {cpu_usage:.1f}%")
                            if cpu_usage > 95:
                                node_health["status"] = "unhealthy"
                        
                        if memory_percent > 80:
                            node_health["issues"].append(f"High memory usage: {memory_percent:.1f}%")
                            if memory_percent > 95:
                                node_health["status"] = "unhealthy"
                    
                    # Check VMs
                    vms = await self.bot.proxmox.get_vms(node["node"])
                    for vm in vms:
                        if vm.get("status") == "running":
                            try:
                                vm_stats = await self.bot.proxmox.get_vm_stats(node["node"], vm["vmid"])
                                if vm_stats:
                                    vm_cpu = vm_stats.get("cpu", 0) * 100
                                    vm_memory = vm_stats.get("mem", 0) / 1024 / 1024 / 1024  # GB
                                    vm_max_memory = vm_stats.get("maxmem", 0) / 1024 / 1024 / 1024  # GB
                                    vm_memory_percent = (vm_memory / vm_max_memory * 100) if vm_max_memory > 0 else 0
                                    
                                    if vm_cpu > 90:
                                        node_health["issues"].append(f"VM {vm['name']} high CPU: {vm_cpu:.1f}%")
                                    
                                    if vm_memory_percent > 90:
                                        node_health["issues"].append(f"VM {vm['name']} high memory: {vm_memory_percent:.1f}%")
                            except Exception as e:
                                logger.warning(f"Failed to check VM {vm['vmid']} health: {e}")
                    
                    health_checks.append(node_health)
                    
                except Exception as e:
                    logger.warning(f"Failed to check health for node {node['node']}: {e}")
                    health_checks.append({
                        "node": node["node"],
                        "status": "error",
                        "issues": [f"Health check failed: {str(e)}"]
                    })
            
            # Create embed
            embed = discord.Embed(
                title="🏥 Health Check Report",
                color=0x0099ff,
                timestamp=datetime.utcnow()
            )
            
            healthy_nodes = 0
            unhealthy_nodes = 0
            error_nodes = 0
            
            for health in health_checks:
                if health["status"] == "healthy":
                    healthy_nodes += 1
                    status_emoji = "✅"
                elif health["status"] == "unhealthy":
                    unhealthy_nodes += 1
                    status_emoji = "⚠️"
                else:
                    error_nodes += 1
                    status_emoji = "❌"
                
                issues_text = "\n".join(health["issues"][:3]) if health["issues"] else "No issues"
                if len(health["issues"]) > 3:
                    issues_text += f"\n... and {len(health['issues']) - 3} more issues"
                
                embed.add_field(
                    name=f"{status_emoji} {health['node']}",
                    value=issues_text,
                    inline=True
                )
            
            # Summary
            embed.add_field(
                name="📊 Summary",
                value=f"**Healthy:** {healthy_nodes}\n"
                      f"**Unhealthy:** {unhealthy_nodes}\n"
                      f"**Errors:** {error_nodes}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            await interaction.followup.send(f"❌ Failed to perform health check: {str(e)}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(MonitoringCog(bot))