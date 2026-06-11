"""RiskOS AI — FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import (audit, auth, developer, evidence, intelligence, investigations,
                      metrics, notifications, rules, transactions)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Simulation environment. Synthetic transaction data only — no real customer records.",
    version="1.0.0",
)
Base.metadata.create_all(engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, transactions.router, investigations.router, rules.router,
          metrics.router, audit.router, intelligence.router, developer.router,
          notifications.router, evidence.router):
    app.include_router(r)


@app.get("/health")
def health():
    """Non-secret runtime status. Never exposes SIDs, tokens, or full phone numbers."""
    from .communications import twilio_configured
    return {"status": "ok", "environment": settings.environment_label, "org": settings.org_name,
            "ai_provider": "mock" if settings.mock_ai else "anthropic",
            "sms": {
                "sms_enabled": settings.sms_enabled,
                "twilio_configured": twilio_configured(),
                "from_number_present": bool(settings.twilio_from_number),
                "demo_phone_present": bool(settings.demo_customer_phone),
                "provider": "twilio" if settings.sms_enabled and twilio_configured() else "disabled",
            }}
