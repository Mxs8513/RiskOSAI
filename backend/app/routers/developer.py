from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..ai import generate_test_scenarios
from ..database import get_db
from ..pipeline import active_rule_codes, log
from ..risk_engine import score_transaction
from ..security import require

router = APIRouter(prefix="/developer", tags=["developer"])


class ScenarioRequest(BaseModel):
    rule_code: str = Field(max_length=10)
    count: int = Field(5, ge=1, le=10)


@router.post("/generate-scenario")
def generate_scenario(body: ScenarioRequest, db: Session = Depends(get_db), user=Depends(require("developer"))):
    if not db.query(models.FraudRule).filter_by(rule_code=body.rule_code).first():
        raise HTTPException(404, f"Unknown rule {body.rule_code}")
    scenarios = generate_test_scenarios(body.rule_code, min(body.count, 10))
    out = []
    for s in scenarios:
        result = score_transaction(s["payload"], active_rule_codes(db))
        flagged = result["risk_level"] in ("High", "Critical")
        rule_hit = any(r["code"] == body.rule_code for r in result["rules_triggered"])
        passed = flagged and rule_hit
        ts = models.TestScenario(generated_by=user.id, rule_code=body.rule_code, scenario_payload=s["payload"],
                                 expected_result=s["expected_status"],
                                 actual_result=f"{result['risk_level']} ({result['score']})", passed=passed)
        db.add(ts)
        out.append({"payload": s["payload"], "expected": s["expected_status"],
                    "score": result["score"], "risk_level": result["risk_level"],
                    "rules_triggered": [r["code"] for r in result["rules_triggered"]],
                    "rule_under_test_triggered": rule_hit, "passed": passed})
    log(db, "test_scenario_generated", actor_id=user.id, actor_role=user.role,
        message=f"{user.name} generated {len(out)} test scenarios for {body.rule_code}",
        meta={"rule_code": body.rule_code, "passed": sum(1 for o in out if o["passed"])})
    db.commit()
    return {"rule_code": body.rule_code, "scenarios": out,
            "summary": {"total": len(out), "passed": sum(1 for o in out if o["passed"])}}


class RunPayload(BaseModel):
    amount: float = Field(ge=0, le=10_000_000)
    user_avg_amount: float = Field(80.0, ge=0, le=10_000_000)
    is_new_device: bool = False
    velocity_10_min: int = Field(1, ge=0, le=1000)
    distance_from_home_miles: float = Field(0, ge=0, le=20_000)
    merchant_risk_score: float = Field(0.2, ge=0, le=1)
    transaction_type: str = Field("card_present", max_length=30)
    dataset_label: bool = False
    device_id: str = Field("dev_test", max_length=64)


@router.post("/run-scenario")
def run_scenario(body: RunPayload, db: Session = Depends(get_db), user=Depends(require("developer"))):
    return score_transaction(body.model_dump(), active_rule_codes(db))


@router.get("/sample-payloads")
def sample_payloads(user=Depends(require("developer"))):
    return {
        "POST /investigations/{id}/review": {"decision": "confirm_fraud", "note": "Verified with customer — card reported stolen.", "review_time_seconds": 142},
        "POST /developer/run-scenario": RunPayload(amount=940.0, is_new_device=True, velocity_10_min=5, transaction_type="card_not_present").model_dump(),
        "POST /risk-intelligence/query": {"question": "Which fraud rule caused the most false positives?"},
        "POST /transactions/generate-batch?count=5": {},
    }


@router.get("/scenario-history")
def scenario_history(db: Session = Depends(get_db), user=Depends(require("developer")), limit: int = 30):
    rows = db.query(models.TestScenario).order_by(models.TestScenario.created_at.desc()).limit(limit).all()
    return [{"id": s.id, "rule_code": s.rule_code, "expected": s.expected_result, "actual": s.actual_result,
             "passed": s.passed, "payload": s.scenario_payload, "created_at": s.created_at.isoformat()} for s in rows]
