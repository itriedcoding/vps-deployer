"""
Database models for VPS Deployer Discord Bot
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """User model for Discord users"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String(20), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    discriminator = Column(String(10))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    vms = relationship("VM", back_populates="owner", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="user", cascade="all, delete-orphan")

class VM(Base):
    """Virtual Machine model"""
    __tablename__ = "vms"
    
    id = Column(Integer, primary_key=True)
    vm_id = Column(Integer, unique=True, nullable=False, index=True)  # Proxmox VM ID
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="stopped")  # running, stopped, paused, etc.
    template = Column(String(50), nullable=False)
    memory = Column(Integer, nullable=False)
    cores = Column(Integer, nullable=False)
    disk_size = Column(Integer, nullable=False)  # in GB
    ip_address = Column(String(45))  # IPv4 or IPv6
    mac_address = Column(String(17))
    ssh_port = Column(Integer, default=22)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_modified = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Proxmox specific fields
    node = Column(String(50), nullable=False)
    storage = Column(String(50), nullable=False)
    network_bridge = Column(String(50), default="vmbr0")
    proxmox_config = Column(JSON)  # Store full Proxmox config
    
    # Relationships
    owner = relationship("User", back_populates="vms")
    deployments = relationship("Deployment", back_populates="vm", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="vm", cascade="all, delete-orphan")

class Snapshot(Base):
    """VM Snapshot model"""
    __tablename__ = "snapshots"
    
    id = Column(Integer, primary_key=True)
    snapshot_name = Column(String(100), nullable=False)
    description = Column(Text)
    size = Column(Integer)  # Size in bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=False)
    
    # Relationships
    vm = relationship("VM", back_populates="snapshots")

class Deployment(Base):
    """Deployment tracking model"""
    __tablename__ = "deployments"
    
    id = Column(Integer, primary_key=True)
    deployment_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    status = Column(String(20), default="pending")  # pending, in_progress, completed, failed
    deployment_type = Column(String(50), nullable=False)  # vm_create, vm_clone, vm_migrate, etc.
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=True)
    
    # Deployment specific data
    deployment_data = Column(JSON)
    
    # Relationships
    user = relationship("User", back_populates="deployments")
    vm = relationship("VM", back_populates="deployments")

class Template(Base):
    """OS Template model"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    template_file = Column(String(200), nullable=False)
    min_memory = Column(Integer, nullable=False)
    min_cores = Column(Integer, nullable=False)
    min_disk = Column(Integer, nullable=False)
    default_user = Column(String(50), nullable=False)
    ssh_port = Column(Integer, default=22)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Template metadata
    metadata = Column(JSON)

class Node(Base):
    """Proxmox Node model"""
    __tablename__ = "nodes"
    
    id = Column(Integer, primary_key=True)
    node_name = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), default="online")
    cpu_cores = Column(Integer)
    memory_total = Column(Integer)  # in MB
    memory_used = Column(Integer)   # in MB
    disk_total = Column(Integer)    # in GB
    disk_used = Column(Integer)     # in GB
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Node specific data
    node_data = Column(JSON)

class Backup(Base):
    """Backup model"""
    __tablename__ = "backups"
    
    id = Column(Integer, primary_key=True)
    backup_id = Column(String(100), unique=True, nullable=False)
    vm_id = Column(Integer, ForeignKey("vms.id"), nullable=False)
    backup_type = Column(String(20), default="manual")  # manual, scheduled, auto
    status = Column(String(20), default="pending")  # pending, in_progress, completed, failed
    size = Column(Integer)  # Size in bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    retention_until = Column(DateTime)
    
    # Backup specific data
    backup_data = Column(JSON)
    
    # Relationships
    vm = relationship("VM")

class AuditLog(Base):
    """Audit log for tracking all actions"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100))
    details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")