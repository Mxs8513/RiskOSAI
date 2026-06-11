"""Shared fixtures: temp SQLite DB, seeded users/rules, authenticated clients.

Environment is configured BEFORE app imports so the cached Settings and the
SQLAlchemy engine bind to the test database, never the dev riskos.db.
"""
import os
import tempfile

_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="riskos-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["MOCK_AI"] = "true"
os.environ["JWT_SECRET"] = "test-secret"
# Hard-disable real SMS in tests: config loads backend/.env (which may hold
# real Twilio credentials on a dev machine), but pre-set process env always
# wins over .env. Individual tests re-enable via monkeypatched settings +
# a mocked _send_via_twilio — never the real client.
os.environ["SMS_ENABLED"] = "false"
os.environ["TWILIO_ACCOUNT_SID"] = ""
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["TWILIO_FROM_NUMBER"] = ""
os.environ["DEMO_CUSTOMER_PHONE"] = ""
# Tests never load a real ML artifact (a dev machine may have trained one);
# ML behavior is exercised via small fake models monkeypatched per test.
os.environ["ML_MODEL_PATH"] = os.path.join(tempfile.gettempdir(), "riskos-no-model.pkl")
os.environ["ML_METRICS_PATH"] = os.path.join(tempfile.gettempdir(), "riskos-no-metrics.json")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline import process_transaction  # noqa: E402
from app.risk_engine import RULES_CATALOG  # noqa: E402
from app.security import hash_password  # noqa: E402

# PBKDF2 is intentionally slow; hash once and reuse for every seeded user.
PASSWORD = "demo1234"
PASSWORD_HASH = hash_password(PASSWORD)

USERS = [
    ("analyst@test.demo", "Avery Test", "fraud_analyst"),
    ("manager@test.demo", "Jordan Test", "risk_manager"),
    ("developer@test.demo", "Sam Test", "developer"),
    ("admin@test.demo", "Riley Test", "admin"),
]


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded(db):
    """Users, rules, one customer, one merchant."""
    for email, name, role in USERS:
        db.add(models.User(email=email, password_hash=PASSWORD_HASH, name=name, role=role))
    for r in RULES_CATALOG:
        db.add(models.FraudRule(**r, status="active"))
    db.add(models.Customer(id="usr_9001", home_city="Dallas", home_state="TX",
                           avg_transaction_amount=100.0, risk_profile="standard"))
    db.add(models.Merchant(id="mer_9001", name="Test Mart", category="retail",
                           city="Dallas", state="TX", merchant_risk_score=0.2))
    db.commit()
    return db


@pytest.fixture()
def client(seeded):
    return TestClient(app)


def login(client: TestClient, email: str) -> dict:
    res = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture()
def analyst(client):
    return login(client, "analyst@test.demo")


@pytest.fixture()
def manager(client):
    return login(client, "manager@test.demo")


@pytest.fixture()
def developer(client):
    return login(client, "developer@test.demo")


def make_enriched(**overrides) -> dict:
    """Baseline transaction dict that triggers no rules; override to trigger."""
    base = {
        "id": overrides.pop("id", "txn_900001"),
        "customer_id": "usr_9001", "merchant_id": "mer_9001",
        "amount": 50.0, "currency": "USD", "city": "Dallas", "state": "TX",
        "device_id": "dev_1234", "transaction_type": "card_present",
        "is_new_device": False, "velocity_10_min": 1,
        "distance_from_home_miles": 5.0, "merchant_risk_score": 0.2,
        "dataset_label": False, "user_avg_amount": 100.0,
    }
    base.update(overrides)
    return base


def flag_transaction(db, txn_id="txn_900001"):
    """Push a Critical-band transaction through the pipeline; returns the investigation.

    Only Critical-tier transactions open human investigations since the
    Automated Response Orchestrator (score here: 25+20+20+20+10 = 95).
    """
    enriched = make_enriched(id=txn_id, amount=900.0, is_new_device=True,
                             velocity_10_min=5, distance_from_home_miles=1500,
                             transaction_type="card_not_present")
    _, _, inv = process_transaction(db, enriched)
    assert inv is not None, "expected a Critical investigation"
    return inv
