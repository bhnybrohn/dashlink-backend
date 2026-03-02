"""DashLink configuration — loaded from environment variables via Pydantic."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ──
    environment: str = "development"
    secret_key: str = "change-me-to-a-256-bit-secret"
    debug: bool = False
    app_name: str = "DashLink"
    api_v1_prefix: str = "/api"

    # ── Database ──
    database_url: str = "postgresql+asyncpg://dashlink:dashlink_dev@localhost:5432/dashlink"
    database_echo: bool = False

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ──
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # ── Storage (S3/R2) ──
    s3_bucket_name: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "auto"


    # ── Payment Gateways ──
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    paystack_secret_key: str = ""
    paystack_webhook_secret: str = ""
    flutterwave_secret_key: str = ""
    flutterwave_webhook_secret: str = ""

    # ── AI ──
    openai_api_key: str = ""
    removebg_api_key: str = ""

    # ── Notifications ──
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_sms_from: str = ""
    resend_api_key: str = ""
    resend_from_email: str = "noreply@dashlink.to"
    firebase_credentials_path: str = ""

    # ── OAuth Providers ──
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""

    facebook_oauth_client_id: str = ""
    facebook_oauth_client_secret: str = ""
    facebook_oauth_redirect_uri: str = ""

    twitter_oauth_client_id: str = ""
    twitter_oauth_client_secret: str = ""
    twitter_oauth_redirect_uri: str = ""

    # ── Social Media Publishing ──
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_redirect_uri: str = ""

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = ""

    facebook_social_redirect_uri: str = ""  # for social publishing (separate from auth OAuth)
    twitter_social_redirect_uri: str = ""   # for social publishing (separate from auth OAuth)
    twitter_api_key: str = ""               # v1.1 consumer key (for media upload)
    twitter_api_secret: str = ""            # v1.1 consumer secret

    pinterest_app_id: str = ""
    pinterest_app_secret: str = ""
    pinterest_redirect_uri: str = ""

    # ── Encryption ──
    encryption_key: str = "change-me-32-byte-key-for-aes256"

    # ── CORS ──
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
