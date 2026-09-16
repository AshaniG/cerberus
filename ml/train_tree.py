#!/usr/bin/env python3
"""
train_tree.py — train a shallow sklearn decision tree for Tier 2 (M5).

Prefers CIC-IDS-2017 CSVs under data/cic-ids-2017/ when present. If the
dataset is missing, builds a *synthetic* training set so the pipeline and
demo still run (thesis evaluation should use the real CIC files).

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python3 ml/train_tree.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "cic-ids-2017"
MODEL_DIR = Path(__file__).resolve().parent / "model"
MODEL_PATH = MODEL_DIR / "tree.joblib"

# Must match ml/classify.features_from_flow order.
FEATURE_NAMES = [
    "packet_count",
    "count_threshold_ratio",
    "byte_rate",
    "syn_ratio",
    "duration_s",
]


def load_cic_simplified():
    """
    Load CIC-IDS-2017 CSVs if available and project to our 5 live features.

    CIC column names vary by file; we map common ones and derive proxies.
    """
    import pandas as pd

    csvs = sorted(DATA_DIR.glob("*.csv"))
    if not csvs:
        return None

    frames = []
    for path in csvs[:3]:  # keep training time modest for a BSc prototype
        print(f"Reading {path.name} ...")
        df = pd.read_csv(path, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)

    # Label column is usually 'Label'
    label_col = "Label" if "Label" in raw.columns else None
    if label_col is None:
        for c in raw.columns:
            if c.lower() == "label":
                label_col = c
                break
    if label_col is None:
        print("No Label column — falling back to synthetic data")
        return None

    # Heuristic projections from common CIC features into our live vector.
    def col(*names):
        for n in names:
            if n in raw.columns:
                return raw[n]
        return None

    tot_fwd = col("Total Fwd Packets", "Total Fwd Packet")
    tot_bwd = col("Total Backward Packets", "Total Bwd packets")
    pkt = (tot_fwd.fillna(0) + (tot_bwd.fillna(0) if tot_bwd is not None else 0)) if tot_fwd is not None else None
    if pkt is None:
        pkt = col("Flow Duration")
        if pkt is None:
            return None
        pkt = pkt.clip(lower=1) / 1000.0

    flow_bytes = col("Flow Bytes/s", "Flow Byts/s")
    if flow_bytes is None:
        flow_bytes = pkt * 64
    duration = col("Flow Duration")
    if duration is None:
        duration = pkt * 0 + 1.0
    else:
        duration = duration.clip(lower=1) / 1_000_000.0  # µs → s approx
    syn = col("SYN Flag Count", "SYN Flag Cnt")
    if syn is None:
        syn = pkt * 0 + 0.3
    else:
        syn = (syn / pkt.replace(0, 1)).clip(0, 1)

    # Fake a threshold mid distribution so ratio is meaningful.
    thr = float(pkt.quantile(0.9)) or 250.0
    ratio = pkt / thr

    import numpy as np

    X = np.column_stack(
        [
            pkt.to_numpy(dtype=float),
            ratio.to_numpy(dtype=float),
            flow_bytes.to_numpy(dtype=float),
            syn.to_numpy(dtype=float),
            duration.to_numpy(dtype=float),
        ]
    )
    y = raw[label_col].astype(str).str.upper().ne("BENIGN").astype(int).to_numpy()
    # Drop NaNs / inf
    mask = np.isfinite(X).all(axis=1)
    return X[mask], y[mask]


def make_synthetic(n: int = 4000):
    import numpy as np

    rng = np.random.default_rng(42)
    # Benign: modest counts, low syn ratio
    n_b = n // 2
    n_a = n - n_b
    thr = 250.0
    benign = np.column_stack(
        [
            rng.integers(5, 120, n_b),
            rng.uniform(0.02, 0.45, n_b),
            rng.uniform(500, 8000, n_b),
            rng.uniform(0.05, 0.35, n_b),
            rng.uniform(0.5, 30, n_b),
        ]
    )
    attack = np.column_stack(
        [
            rng.integers(180, 2000, n_a),
            rng.uniform(0.7, 4.0, n_a),
            rng.uniform(20000, 200000, n_a),
            rng.uniform(0.6, 1.0, n_a),
            rng.uniform(0.1, 5, n_a),
        ]
    )
    # Recompute ratio consistently-ish
    benign[:, 1] = benign[:, 0] / thr
    attack[:, 1] = attack[:, 0] / thr
    X = np.vstack([benign, attack])
    y = np.array([0] * n_b + [1] * n_a)
    perm = rng.permutation(n)
    return X[perm], y[perm]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-depth", type=int, default=4, help="Keep shallow (architecture > size)")
    parser.add_argument("--synthetic", action="store_true", help="Force synthetic training data")
    args = parser.parse_args()

    import joblib
    import numpy as np
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.tree import DecisionTreeClassifier

    data = None if args.synthetic else load_cic_simplified()
    if data is None:
        print("Using synthetic training data (download CIC-IDS-2017 into data/cic-ids-2017/ for real eval).")
        X, y = make_synthetic()
    else:
        X, y = data
        print(f"Loaded CIC-projected samples: {len(y)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    clf = DecisionTreeClassifier(max_depth=args.max_depth, random_state=42)
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    print(classification_report(y_test, pred, target_names=["benign", "attack"]))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "features": FEATURE_NAMES}, MODEL_PATH)
    print(f"Saved {MODEL_PATH}")


if __name__ == "__main__":
    main()
