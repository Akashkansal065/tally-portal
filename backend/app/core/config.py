from typing import Optional
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    TALLY_DATABASE_NAME: str = "tally_sync"
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    DB_SSL: bool = False
    
    # ImageKit Integration
    IMAGEKIT_PUBLIC_KEY: Optional[str] = None
    IMAGEKIT_PRIVATE_KEY: Optional[str] = None
    IMAGEKIT_URL_ENDPOINT: Optional[str] = None
    
    # SMTP Settings
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    
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
