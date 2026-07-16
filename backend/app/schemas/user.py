from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role_id: int
    company_id: int

class UserResponse(BaseModel):
    user_id: int
    company_id: int
    username: str
    email: str
    role_id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class PermissionOverrideSchema(BaseModel):
    override_id: int
    user_id: int
    module_id: int
    can_create: Optional[bool] = None
    can_read: Optional[bool] = None
    can_update: Optional[bool] = None
    can_delete: Optional[bool] = None
    reason: Optional[str] = None
    granted_by: int
    granted_at: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
