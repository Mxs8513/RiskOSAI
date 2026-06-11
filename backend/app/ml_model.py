"""Optional ML fraud-scoring layer (hybrid ML + rule-based scoring).

The deterministic rule engine remains the explainability and audit layer.
The ML model (trained offline by scripts/train_model.py) adds learned pattern
detection. Both are surfaced; routing uses the hybrid of the two.

Safety properties:
- If the model artifact is missing or unloadable, every function degrades
  gracefully: predictions return None and the hybrid score equals the rule
  score. The app must keep working with rules only.
- The ML model is never the final authority — humans still review Critical
  cases, and the rule score stays visible everywhere.
- scikit-learn is only needed if an artifact exists (pickle imports it at
  load time); the base app runs without it.
"""
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

logger = logging.getLogger("riskos.ml")

_ARTIFACT_DIR = Path(__file__).resolve().parent / "model_artifacts"
MODEL_PATH = Path(os.getenv("ML_MODEL_PATH", _ARTIFACT_DIR / "fraud_model.pkl"))
METRICS_PATH = Path(os.getenv("ML_METRICS_PATH", _ARTIFACT_DIR / "model_metrics.json"))

# Feature contract shared with scripts/train_model.py — order matters.
FEATURE_NAMES = ["amount_ratio", "is_new_device", "velocity_10_min",
                 "distance_from_home_miles", "merchant_risk_score",
                 "card_not_present", "dataset_label"]

HYBRID_ML_WEIGHT = 0.6  # hybrid = 0.6 * ml_prob*100 + 0.4 * rule_score

_cache: dict = {"attempted": False, "artifact": None}


def featurize(txn: dict) -> list:
    """Map a transaction/enriched dict onto the model's feature vector."""
    avg = max(float(txn.get("user_avg_amount") or 0), 0.01)
    return [
        float(txn["amount"]) / avg,
        1.0 if txn.get("is_new_device") else 0.0,
        float(txn.get("velocity_10_min") or 0),
        float(txn.get("distance_from_home_miles") or 0),
        float(txn.get("merchant_risk_score") or 0),
        1.0 if txn.get("transaction_type") == "card_not_present" else 0.0,
        1.0 if txn.get("dataset_label") else 0.0,
    ]


def load_model(force: bool = False):
    """Load (and cache) the model artifact. Returns None when unavailable."""
    if _cache["attempted"] and not force:
        return _cache["artifact"]
    _cache["attempted"] = True
    _cache["artifact"] = None
    if not MODEL_PATH.exists():
        logger.info("ML model artifact not found at %s — running rules-only", MODEL_PATH)
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            artifact = pickle.load(f)
        if artifact.get("feature_names") != FEATURE_NAMES:
            logger.warning("ML artifact feature mismatch — ignoring model (retrain with scripts/train_model.py)")
            return None
        _cache["artifact"] = artifact
        logger.info("ML model loaded: %s (trained %s)", artifact.get("model_name"), artifact.get("trained_at"))
    except Exception as e:
        logger.warning("Failed to load ML model artifact (%s) — running rules-only", type(e).__name__)
    return _cache["artifact"]


def model_available() -> bool:
    return load_model() is not None


def predict_fraud_probability(txn: dict) -> Optional[float]:
    """Fraud probability in [0, 1], or None if no model is available."""
    artifact = load_model()
    if artifact is None:
        return None
    try:
        prob = float(artifact["model"].predict_proba([featurize(txn)])[0][1])
        return min(max(prob, 0.0), 1.0)
    except Exception as e:
        logger.warning("ML prediction failed (%s) — falling back to rules-only", type(e).__name__)
        return None


def compute_hybrid_score(rule_score: int, ml_probability: Optional[float]) -> int:
    """0.6 × ML(0–100) + 0.4 × rule score; equals the rule score without ML."""
    if ml_probability is None:
        return int(rule_score)
    raw = HYBRID_ML_WEIGHT * (ml_probability * 100) + (1 - HYBRID_ML_WEIGHT) * rule_score
    return max(0, min(100, round(raw)))


def score_agreement(rule_score: int, ml_probability: Optional[float]) -> Optional[str]:
    """How closely the model and the rules agree: high | medium | low."""
    if ml_probability is None:
        return None
    diff = abs(rule_score - ml_probability * 100)
    return "high" if diff <= 15 else "medium" if diff <= 35 else "low"


def get_model_metadata() -> Optional[dict]:
    """Training metadata/metrics written by scripts/train_model.py, or None."""
    if not METRICS_PATH.exists():
        return None
    try:
        return json.loads(METRICS_PATH.read_text())
    except Exception:
        return None
