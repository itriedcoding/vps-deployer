"""
Main Discord Bot for VPS Deployer
"""
import discord
from discord.ext import commands
import asyncio
import logging
import traceback
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from utils.logger import setup_logging
from utils.database import DatabaseManager
from proxmox.proxmox_client import ProxmoxClient
from discord_bot.cogs.vm_management import VMManagementCog
from discord_bot.cogs.node_management import NodeManagementCog
from discord_bot.cogs.backup_management import BackupManagementCog
from discord_bot.cogs.monitoring import MonitoringCog
from discord_bot.cogs.template_management import TemplateManagementCog
from discord_bot.cogs.user_management import UserManagementCog
from discord_bot.cogs.system_management import SystemManagementCog
from discord_bot.cogs.console_access import ConsoleAccessCog
from discord_bot.cogs.migration import MigrationCog
from discord_bot.cogs.snapshots import SnapshotCog
from discord_bot.cogs.networking import NetworkingCog

# Setup logging
logger = setup_logging()

class VPSDeployerBot(commands.Bot):
    """Advanced VPS Deployer Discord Bot"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=settings.bot_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        
        self.database = None
        self.proxmox = None
        self.start_time = None
        
    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        logger.info("Setting up VPS Deployer Bot...")
        
        # Initialize database
        self.database = DatabaseManager()
        await self.database.initialize()
        
        # Initialize Proxmox client
        self.proxmox = ProxmoxClient(
            host=settings.proxmox_host,
            user=settings.proxmox_user,
            password=settings.proxmox_password,
            realm=settings.proxmox_realm,
            verify_ssl=settings.proxmox_verify_ssl
        )
        
        # Load cogs
        await self.load_cogs()
        
        # Sync slash commands
        if settings.discord_guild_id:
            guild = discord.Object(id=settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
            
        logger.info("Bot setup completed")
        
    async def load_cogs(self):
        """Load all bot cogs"""
        cogs = [
            VMManagementCog,
            NodeManagementCog,
            BackupManagementCog,
            MonitoringCog,
            TemplateManagementCog,
            UserManagementCog,
            SystemManagementCog,
            ConsoleAccessCog,
            MigrationCog,
            SnapshotCog,
            NetworkingCog
        ]
        
        for cog in cogs:
            try:
                await self.add_cog(cog(self))
                logger.info(f"Loaded cog: {cog.__name__}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog.__name__}: {e}")
                
    async def on_ready(self):
        """Called when bot is ready"""
        self.start_time = discord.utils.utcnow()
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Guilds: {len(self.guilds)}")
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="VPS deployments | /help"
        )
        await self.change_presence(activity=activity)
        
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
            return
            
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {error}")
            return
            
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
            return
            
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"❌ Command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
            return
            
        # Log unexpected errors
        logger.error(f"Unexpected error in command {ctx.command}: {error}")
        logger.error(traceback.format_exc())
        
        await ctx.send("❌ An unexpected error occurred. Please try again later.")
        
    async def on_error(self, event, *args, **kwargs):
        """Handle general errors"""
        logger.error(f"Error in event {event}: {traceback.format_exc()}")
        
    async def close(self):
        """Cleanup when bot is shutting down"""
        logger.info("Shutting down bot...")
        
        if self.proxmox:
            await self.proxmox.disconnect()
            
        if self.database:
            await self.database.close()
            
        await super().close()
        
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in settings.admin_user_ids
        
    def has_permission(self, user: discord.Member) -> bool:
        """Check if user has permission to use bot commands"""
        if self.is_admin(user.id):
            return True
            
        # Check for allowed roles
        for role_name in settings.allowed_roles:
            if any(role.name == role_name for role in user.roles):
                return True
                
        return False

# Bot instance
bot = VPSDeployerBot()

async def main():
    """Main function to run the bot"""
    try:
        await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        logger.error(traceback.format_exc())
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())