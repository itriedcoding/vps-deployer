"""
Configuration management for VPS Deployer Discord Bot
"""
import os
from typing import Optional, List, Dict, Any
from pydantic import BaseSettings, Field
from pathlib import Path

class Settings(BaseSettings):
    """Application settings"""
    
    # Discord Bot Configuration
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_guild_id: Optional[int] = Field(None, env="DISCORD_GUILD_ID")
    bot_prefix: str = Field("!", env="BOT_PREFIX")
    
    # Proxmox Configuration
    proxmox_host: str = Field(..., env="PROXMOX_HOST")
    proxmox_user: str = Field(..., env="PROXMOX_USER")
    proxmox_password: str = Field(..., env="PROXMOX_PASSWORD")
    proxmox_realm: str = Field("pam", env="PROXMOX_REALM")
    proxmox_verify_ssl: bool = Field(True, env="PROXMOX_VERIFY_SSL")
    
    # Database Configuration
    database_url: str = Field("postgresql://user:password@localhost/vps_deployer", env="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # VPS Configuration
    default_vm_memory: int = Field(2048, env="DEFAULT_VM_MEMORY")
    default_vm_cores: int = Field(2, env="DEFAULT_VM_CORES")
    default_vm_disk: int = Field(32, env="DEFAULT_VM_DISK")
    default_storage: str = Field("local-lvm", env="DEFAULT_STORAGE")
    default_network_bridge: str = Field("vmbr0", env="DEFAULT_NETWORK_BRIDGE")
    
    # Security Configuration
    admin_user_ids: List[int] = Field(default_factory=list, env="ADMIN_USER_IDS")
    allowed_roles: List[str] = Field(default_factory=lambda: ["VPS Manager"], env="ALLOWED_ROLES")
    max_vms_per_user: int = Field(5, env="MAX_VMS_PER_USER")
    
    # Monitoring Configuration
    enable_monitoring: bool = Field(True, env="ENABLE_MONITORING")
    monitoring_interval: int = Field(300, env="MONITORING_INTERVAL")  # 5 minutes
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # API Configuration
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    
    # Backup Configuration
    backup_enabled: bool = Field(True, env="BACKUP_ENABLED")
    backup_retention_days: int = Field(30, env="BACKUP_RETENTION_DAYS")
    
    # OS Templates
    available_templates: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "ubuntu-22.04": {
            "name": "Ubuntu 22.04 LTS",
            "template": "ubuntu-22.04-standard_22.04-1_amd64.tar.zst",
            "min_memory": 1024,
            "min_cores": 1,
            "min_disk": 20,
            "default_user": "ubuntu",
            "ssh_port": 22
        },
        "ubuntu-20.04": {
            "name": "Ubuntu 20.04 LTS",
            "template": "ubuntu-20.04-standard_20.04-1_amd64.tar.zst",
            "min_memory": 1024,
            "min_cores": 1,
            "min_disk": 20,
            "default_user": "ubuntu",
            "ssh_port": 22
        },
        "debian-12": {
            "name": "Debian 12 (Bookworm)",
            "template": "debian-12-standard_12.0-1_amd64.tar.zst",
            "min_memory": 1024,
            "min_cores": 1,
            "min_disk": 20,
            "default_user": "debian",
            "ssh_port": 22
        },
        "debian-11": {
            "name": "Debian 11 (Bullseye)",
            "template": "debian-11-standard_11.7-1_amd64.tar.zst",
            "min_memory": 1024,
            "min_cores": 1,
            "min_disk": 20,
            "default_user": "debian",
            "ssh_port": 22
        },
        "centos-8": {
            "name": "CentOS 8 Stream",
            "template": "centos-8-standard_8-1_amd64.tar.zst",
            "min_memory": 1024,
            "min_cores": 1,
            "min_disk": 20,
            "default_user": "centos",
            "ssh_port": 22
        },
        "alpine-3.18": {
            "name": "Alpine Linux 3.18",
            "template": "alpine-3.18-standard_3.18.4-1_amd64.tar.zst",
            "min_memory": 512,
            "min_cores": 1,
            "min_disk": 10,
            "default_user": "root",
            "ssh_port": 22
        }
    })
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()

# Create necessary directories
def create_directories():
    """Create necessary directories for the application"""
    directories = [
        "logs",
        "backups",
        "templates",
        "scripts",
        "data"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

# Initialize directories
create_directories()