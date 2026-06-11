"""RiskOS AI — application configuration.

All values can be overridden via environment variables (see backend/.env.example).
SQLite is the zero-setup default so the demo runs immediately; point
DATABASE_URL at PostgreSQL for a production-style setup.
"""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load backend/.env regardless of the working directory uvicorn was started
# from. Existing process env vars always win (load_dotenv never overrides).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseModel):
    app_name: str = "RiskOS AI — Fraud Operations Console"
    org_name: str = "Northstar Financial"
    environment_label: str = "Simulation"

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./riskos.db")

    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    # AI provider. If ANTHROPIC_API_KEY is unset (or MOCK_AI=true), RiskOS
    # falls back to a deterministic mock generator so the full workflow is
    # demoable offline.
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    mock_ai: bool = os.getenv("MOCK_AI", "").lower() in ("1", "true", "yes") or not os.getenv("ANTHROPIC_API_KEY")

    # Outbound SMS verification (Phase 2). Safety: when enabled, SMS goes ONLY
    # to DEMO_CUSTOMER_PHONE — never to generated customer numbers.
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from_number: str = os.getenv("TWILIO_FROM_NUMBER", "")
    demo_customer_phone: str = os.getenv("DEMO_CUSTOMER_PHONE", "")
    sms_enabled: bool = os.getenv("SMS_ENABLED", "").lower() in ("1", "true", "yes")

    # CORS is scoped to known frontend origins only — local dev ports by
    # default. For a deployed frontend, list its exact origin(s) in the
    # CORS_ORIGINS env var (comma-separated); never use "*".
    cors_origins: list[str] = [o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
