from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.config import settings
from app.models.company import Company

class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    role_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(200), nullable=True)
    
    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", back_populates="role", cascade="all, delete-orphan")

class UserCompanyAccess(Base):
    __tablename__ = "user_company_access"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    access_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    
    user = relationship("User", back_populates="company_access")
    company = relationship("Company")

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    user_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.roles.role_id"), nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    

    ledger_scope = Column(String(64), default='dr_only')
    stock_scope = Column(String(64), default='full')
    allowed_stock_groups = Column(String(1024), nullable=True)
    allowed_ledger_groups = Column(String(1024), nullable=True)
    allowed_report_categories = Column(String(1024), nullable=True)
    
    company = relationship("Company", back_populates="users")
    role = relationship("Role", back_populates="users")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    overrides = relationship("UserPermissionOverride", back_populates="user", cascade="all, delete-orphan", foreign_keys="[UserPermissionOverride.user_id]")
    granted_overrides = relationship("UserPermissionOverride", back_populates="granter", foreign_keys="[UserPermissionOverride.granted_by]")
    company_access = relationship("UserCompanyAccess", back_populates="user", cascade="all, delete-orphan")

class Module(Base):
    __tablename__ = "modules"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    module_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, default=True)
    
    permissions = relationship("Permission", back_populates="module", cascade="all, delete-orphan")
    overrides = relationship("UserPermissionOverride", back_populates="module", cascade="all, delete-orphan")

class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    permission_id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.roles.role_id", ondelete="CASCADE"), nullable=False)
    module_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.modules.module_id"), nullable=True)
    can_create = Column(Boolean, default=False)
    can_read = Column(Boolean, default=True)
    can_update = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    
    role = relationship("Role", back_populates="permissions")
    module = relationship("Module", back_populates="permissions")

class UserPermissionOverride(Base):
    __tablename__ = "user_permission_overrides"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    override_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    module_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.modules.module_id"), nullable=False)
    can_create = Column(Boolean, nullable=True)
    can_read = Column(Boolean, nullable=True)
    can_update = Column(Boolean, nullable=True)
    can_delete = Column(Boolean, nullable=True)
    reason = Column(String(255), nullable=True)
    granted_by = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=False)
    granted_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="overrides", foreign_keys=[user_id])
    module = relationship("Module", back_populates="overrides")
    granter = relationship("User", back_populates="granted_overrides", foreign_keys=[granted_by])

class UserDataScope(Base):
    __tablename__ = "user_data_scopes"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    scope_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(Enum('Godown', 'CostCenter', 'VoucherType', name='user_data_scope_type'), nullable=False)
    scope_ref_id = Column(Integer, nullable=False)

class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}
    
    session_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="sessions")
