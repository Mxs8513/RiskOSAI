"""Evidence Intake & Cross-Check: deterministic cross-check engine,
upload endpoint, RBAC, validation, audit trail, and mock provider."""
import pytest

from app import models
from app.document_intel import cross_check

from .conftest import flag_transaction

TXN = {"amount": 1890.0, "merchant": "VertMart Fuel", "timestamp": "2026-06-05T14:00:00",
       "city": "Atlanta", "state": "GA"}


def extraction(**overrides):
    base = {"document_type": "receipt", "merchant_or_issuer": "VertMart Fuel",
            "total_amount": 1890.0, "currency": "USD", "dates": ["2026-06-05"],
            "location_city": "Atlanta", "location_state": "GA",
            "claim_summary": "Receipt for $1,890 at VertMart Fuel.",
            "handwritten": False, "signatures_present": False,
            "readable_text_quality": "high", "suspicious_artifacts": []}
    base.update(overrides)
    return base


# ---- deterministic cross-check ----

def test_fully_consistent_document():
    r = cross_check(extraction(), TXN)
    assert r["verdict"] == "consistent"
    assert r["confidence"] == 1.0
    assert r["mismatches"] == []
    assert all(c["match"] for c in r["checks"])


def test_amount_mismatch_detected():
    r = cross_check(extraction(total_amount=1250.0), TXN)
    amount_check = next(c for c in r["checks"] if c["field"] == "amount")
    assert amount_check["match"] is False
    assert any("amount" in m for m in r["mismatches"])
    assert r["verdict"] == "partially_consistent"  # 3 of 4 still match


def test_amount_within_tolerance_matches():
    r = cross_check(extraction(total_amount=1885.0), TXN)  # within 2%
    assert next(c for c in r["checks"] if c["field"] == "amount")["match"] is True


def test_date_outside_window_mismatches():
    r = cross_check(extraction(dates=["2026-06-12"]), TXN)
    assert next(c for c in r["checks"] if c["field"] == "date")["match"] is False


def test_merchant_and_location_mismatch_inconsistent():
    r = cross_check(extraction(total_amount=900.0, merchant_or_issuer="QuickServe Holdings",
                               dates=["2026-06-12"], location_city="Miami", location_state="FL"), TXN)
    assert r["verdict"] == "inconsistent"
    assert len(r["mismatches"]) == 4


def test_unreadable_document_unverifiable():
    r = cross_check(extraction(total_amount=None, merchant_or_issuer=None,
                               dates=[], location_city=None), TXN)
    assert r["verdict"] == "unverifiable"
    assert r["confidence"] == 0.0


def test_tampering_artifacts_block_consistent_verdict():
    r = cross_check(extraction(suspicious_artifacts=["total digits appear edited"]), TXN)
    assert r["verdict"] == "partially_consistent"
    assert "edited" in r["summary"]


def test_low_quality_reduces_confidence():
    high = cross_check(extraction(readable_text_quality="high"), TXN)["confidence"]
    low = cross_check(extraction(readable_text_quality="low"), TXN)["confidence"]
    assert low < high


# ---- upload endpoint ----

def upload(client, headers, inv_id, filename="receipt.jpg", content=b"fake-image-bytes",
           content_type="image/jpeg"):
    return client.post(f"/investigations/{inv_id}/evidence",
                       files={"file": (filename, content, content_type)}, headers=headers)


def test_upload_creates_analyzed_evidence(client, seeded, analyst, monkeypatch):
    inv = flag_transaction(seeded, "txn_940001")
    monkeypatch.setattr("app.routers.evidence.extract_document",
                        lambda data, mt, fn, ctx: (extraction(
                            total_amount=ctx["amount"], merchant_or_issuer=ctx["merchant"],
                            dates=[ctx["timestamp"][:10]], location_city=ctx["city"],
                            location_state=ctx["state"]), "mock"))
    res = upload(client, analyst, inv.id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verdict"] == "consistent"
    assert body["provider"] == "mock"
    assert body["confidence"] == 1.0

    listed = client.get(f"/investigations/{inv.id}/evidence", headers=analyst).json()
    assert len(listed) == 1
    assert listed[0]["uploaded_by"] == "Avery Test"

    events = {a.event_type for a in seeded.query(models.AuditLog)
              .filter_by(investigation_id=inv.id)}
    assert "evidence_document_uploaded" in events
    assert "evidence_document_analyzed" in events


def test_upload_mock_provider_runs_offline(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_940002")
    res = upload(client, analyst, inv.id, filename="airline-ticket.png",
                 content=b"png-bytes", content_type="image/png")
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "mock"
    assert body["document_type"] == "ticket"  # filename hint
    assert body["verdict"] in ("consistent", "partially_consistent", "inconsistent", "unverifiable")


def test_upload_rejects_bad_type_and_oversize(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_940003")
    assert upload(client, analyst, inv.id, filename="doc.pdf",
                  content_type="application/pdf").status_code == 422
    big = b"x" * (8 * 1024 * 1024 + 1)
    assert upload(client, analyst, inv.id, content=big).status_code == 422
    assert upload(client, analyst, inv.id, content=b"").status_code == 422


def test_upload_requires_auth_and_valid_case(client, seeded, analyst):
    res = client.post("/investigations/inv_999999/evidence",
                      files={"file": ("a.jpg", b"x", "image/jpeg")}, headers=analyst)
    assert res.status_code == 404
    res = client.post("/investigations/inv_999999/evidence",
                      files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert res.status_code == 401


def test_evidence_file_retrievable(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_940004")
    doc_id = upload(client, analyst, inv.id).json()["id"]
    res = client.get(f"/evidence/{doc_id}/file", headers=analyst)
    assert res.status_code == 200
    assert res.content == b"fake-image-bytes"
