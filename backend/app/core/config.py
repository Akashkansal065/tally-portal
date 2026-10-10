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
    
    # Email (Gmail SMTP). SMTP_USER is the Gmail address; SMTP_PASS is a Google app password (needs 2-Step
    # Verification on that account), not the normal password. Used only when the "email" integration is on.
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_FROM_NAME: Optional[str] = None  # display name; defaults to the company name
    EMAIL_DAILY_LIMIT: int = 450  # personal Gmail allows about 500 a day

    # WhatsApp (Meta WhatsApp Cloud API). Used only when the "whatsapp_api" integration is on.
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None  # permanent system-user token
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_TEMPLATE: Optional[str] = None  # approved template name, e.g. payment_reminder
    WHATSAPP_TEMPLATE_LANG: str = "en"
    WHATSAPP_API_VERSION: str = "v23.0"
    WHATSAPP_APP_SECRET: Optional[str] = None  # checks the signature on delivery receipts
    WHATSAPP_VERIFY_TOKEN: Optional[str] = None  # any string; also entered in Meta's webhook setup

    # Automatic payment reminders: log what would be sent instead of sending (for the first days on real data)
    REMINDERS_DRY_RUN: bool = False

    # e-Invoice / e-Way bill through a GST Suvidha Provider (Phase 4; only "mastergst" is built). These are the
    # GSP account's keys; each company's e-invoice / e-way bill portal API username and password are entered in
    # Admin → Integrations. Used only when the "einvoice" / "eway_bill" switches are on and set to Live.
    GSP_PROVIDER: str = "mastergst"
    GSP_BASE_URL: str = "https://api.mastergst.com"
    GSP_EMAIL: Optional[str] = None  # the email registered with the GSP
    GSP_CLIENT_ID: Optional[str] = None
    GSP_CLIENT_SECRET: Optional[str] = None
    GSP_IP_ADDRESS: str = "127.0.0.1"  # sent in the ip_address header; set to the server's public IP if the GSP asks
    
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

    # Firebase service account (JSON text, or a path to the JSON file) for Android app push. Unset = off.
    FCM_SERVICE_ACCOUNT_JSON: Optional[str] = None

    # Rate Limiting Settings
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "5/minute"
    # Where people open the app, e.g. https://app.example.com. Used for the link in invitation emails; without
    # it the email carries the invitation code to paste into the app's "Accept invite" page.
    APP_PUBLIC_URL: Optional[str] = None
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

    # Successful sync traffic logs older than this are deleted daily; failed ones stay until an admin clears them
    SYNC_LOG_PURGE_SUCCESS_AFTER_DAYS: int = 30

    # Read notifications older than this are deleted daily; unread ones are kept twice as long
    NOTIFICATION_RETENTION_DAYS: int = 90

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
