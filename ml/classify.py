"""
ml/classify.py — Tier-2 decision tree scoring for the ambiguous slice only.

Novelty 2: Tier 1 filters everything cheaply in-kernel; only IPs in the
soft–hard band reach this classifier. Missing model → callers treat as no-op.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(__file__).resolve().parent / "model" / "tree.joblib"

_model = None
_feature_names: Optional[list[str]] = None


def model_available() -> bool:
    return MODEL_PATH.exists()


def _load():
    global _model, _feature_names
    if _model is not None:
        return _model
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No model at {MODEL_PATH}. Train with: python3 ml/train_tree.py"
        )
    import joblib

    payload = joblib.load(MODEL_PATH)
    if isinstance(payload, dict):
        _model = payload["model"]
        _feature_names = payload.get("features")
    else:
        _model = payload
        _feature_names = None
    return _model


def features_from_flow(flow: dict[str, Any]) -> list[float]:
    """
    Compact feature vector derived from live map stats.

    Full CIC-IDS has dozens of columns; at inference time we only have what
    Tier 1 observed. We map those into a small fixed vector the training
    script also uses (see train_tree.synthetic_or_cic_features).
    """
    count = float(flow.get("packet_count", 0))
    thr = float(flow.get("threshold", 1) or 1)
    ratio = count / thr
    # Placeholder protocol/byte proxies — real CIC training uses richer cols;
    # live path approximates with count-based signals so the architecture runs.
    return [
        count,
        ratio,
        float(flow.get("byte_rate", count * 64)),
        float(flow.get("syn_ratio", 0.8 if ratio > 0.7 else 0.2)),
        float(flow.get("duration_s", 1.0)),
    ]


def classify_flow(flow: dict[str, Any]) -> Tuple[str, float]:
    """
    Returns (label, confidence) where label is 'attack' or 'benign'.
    """
    import numpy as np

    model = _load()
    x = np.array([features_from_flow(flow)])
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(x)[0]
        # Assume class 1 = attack if binary.
        classes = list(getattr(model, "classes_", [0, 1]))
        if "attack" in classes or 1 in classes:
            attack_idx = classes.index("attack") if "attack" in classes else classes.index(1)
        else:
            attack_idx = int(proba.argmax())
        score = float(proba[attack_idx])
        label = "attack" if score >= 0.5 else "benign"
        return label, score
    pred = model.predict(x)[0]
    label = str(pred)
    if label in ("1", "attack", "Attack"):
        return "attack", 1.0
    return "benign", 1.0
