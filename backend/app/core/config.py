from typing import Optional
import os
from pydantic import field_validator
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
    # The Tally company (its GUID) that TALLY_URL belongs to. Set it on a server that holds more than one
    # customer: direct pushes to TALLY_URL are then made for that company only (see app/core/tally_target.py).
    TALLY_URL_COMPANY_GUID: Optional[str] = None
    # Better than the GUID: the MyTally company id that TALLY_URL belongs to. A GUID can be given to a company of
    # another account by whoever signs up; an id cannot. When set, it wins over TALLY_URL_COMPANY_GUID.
    TALLY_URL_COMPANY_ID: Optional[int] = None

    @field_validator("TALLY_URL_COMPANY_ID", mode="before")
    @classmethod
    def _blank_is_unset(cls, value):
        """TALLY_URL_COMPANY_ID= with nothing after it (as in .env.example) means not set, not a startup error."""
        return None if isinstance(value, str) and not value.strip() else value
    # Turn on after scripts/migrate_to_account.py has given every existing row its account: from then on a row
    # with no account belongs to nobody, instead of to the shared group a one-customer server started as.
    ACCOUNTS_ENFORCED: bool = False
    # Turn on once every sync agent PC has signed in as a PC: a sync agent still using a person's email and
    # password is then refused with a message to update and sign in.
    REQUIRE_AGENT_DEVICE_SIGNIN: bool = False
    # Emails (comma-separated) of the people who run this server. Only they may use what acts on the whole server
    # rather than one account: backups of the server's Tally and the backup schedule. Being an account's Admin is
    # not enough, since anyone who signs up from the sync agent is the Admin of their own account. Empty = nobody.
    PLATFORM_ADMIN_EMAILS: str = ""

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

    # Sign-in and sign-up with a mobile number and an OTP, next to email and password. Off until it has been
    # tested: while off the app does not offer it and the server refuses it.
    PHONE_SIGNIN_ENABLED: bool = False
    # The app confirms the OTP with Firebase Authentication and sends the server the ID token Firebase gives it.
    # This is the Firebase project those tokens must come from; left empty, the project of
    # FCM_SERVICE_ACCOUNT_JSON is used.
    FIREBASE_PROJECT_ID: Optional[str] = None
    # How long after the OTP was confirmed its token is still taken (long enough to fill in the sign-up form)
    PHONE_OTP_MAX_AGE_MINUTES: int = 30

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
    MAX_PAGE_SIZE: int = 500  # the page_size / limit query parameters already refuse more than this
    
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
