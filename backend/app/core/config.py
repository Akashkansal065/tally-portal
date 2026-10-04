from typing import Optional
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    TALLY_DATABASE_NAME: str = "tally_sync"
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    DB_SSL: bool = False
    
    # ImageKit Integration
    IMAGEKIT_PUBLIC_KEY: Optional[str] = None
    IMAGEKIT_PRIVATE_KEY: Optional[str] = None
    IMAGEKIT_URL_ENDPOINT: Optional[str] = None
    
    # SMTP Settings
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    
    # Tally Synchronization Settings
    TALLY_URL: Optional[str] = None

    # GST provider adapter. Credentials stay server-side; the adapter is API-shape agnostic.
    GST_PROVIDER_URL: Optional[str] = None
    GST_PROVIDER_API_KEY: Optional[str] = None
    
    # UPI / Payment Settings
    DEFAULT_UPI_VPA: str = "***@upi"
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    
    # Web Push / VAPID Settings
    VAPID_PUBLIC_KEY: Optional[str] = None
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_CLAIM_EMAIL: str = "mailto:admin@snehdistributors.com"

    # Rate Limiting Settings
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "5/minute; 20/hour"

    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"  # 'text' or 'json'

    # Device sessions
    # What happens when a role's max_active_devices is reached: "evict_oldest" signs out the
    # least recently used device; "refuse" rejects the new login
    DEVICE_LIMIT_POLICY: str = "evict_oldest"
    SESSION_PURGE_EXPIRED_AFTER_DAYS: int = 30
    SESSION_PURGE_REVOKED_AFTER_DAYS: int = 90

    # Pagination Settings
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 50000
    
    @property
    def PORTAL_DATABASE_NAME(self) -> str:
        db_name = self.DATABASE_URL.rsplit('/', 1)[-1]
        if '?' in db_name:
            db_name = db_name.split('?')[0]
        return db_name
    
    class Config:
        env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        extra = "ignore"

settings = Settings()
