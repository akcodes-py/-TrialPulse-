"""Train calibrated XGBoost and CoxPH from one independent row per participant."""

import argparse
import json
from pathlib import Path

from backend.app.retention import FEATURES


def synthetic_cohort(rows=1200):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(42)
    frame = pd.DataFrame(
        {
            "age": rng.integers(25, 86, rows),
            "comorbidity_count": rng.poisson(2, rows),
            "visits_per_month": rng.integers(1, 7, rows),
            "phase": rng.integers(1, 5, rows),
            "distance_km": rng.uniform(1, 160, rows),
        }
    )
    hazard = np.exp(
        -4.7
        + 0.016 * (frame.age - 40)
        + 0.18 * frame.comorbidity_count
        + 0.23 * frame.visits_per_month
        + 0.005 * frame.distance_km
        - 0.12 * frame.phase
    )
    dropout_time = rng.exponential(1 / hazard)
    planned_completion = rng.choice([12, 18, 24], rows)
    frame["duration_months"] = np.minimum(dropout_time, planned_completion)
    frame["event_observed"] = (dropout_time < planned_completion).astype(int)
    frame["completed"] = 1 - frame.event_observed
    return frame


def train(csv_path: Path | None, output: Path, synthetic: bool):
    import joblib
    import numpy as np
    import pandas as pd
    from lifelines import CoxPHFitter
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
    from xgboost import XGBClassifier

    frame = synthetic_cohort() if synthetic else pd.read_csv(csv_path)
    columns = FEATURES + ["completed", "duration_months", "event_observed"]
    if set(columns) - set(frame.columns):
        raise ValueError(f"Required CSV columns: {columns}")
    frame = frame[columns].apply(pd.to_numeric, errors="raise")
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Training data must be finite and complete")
    if (
        len(frame) < 100
        or set(frame.completed.unique()) != {0, 1}
        or set(frame.event_observed.unique()) != {0, 1}
    ):
        raise ValueError("At least 100 rows and both binary outcomes are required")
    if (frame.duration_months <= 0).any() or (frame[FEATURES] < 0).any().any():
        raise ValueError("Durations must be positive and features nonnegative")
    if ((frame.completed == 1) & (frame.event_observed == 1)).any():
        raise ValueError("A completed participant cannot also have a dropout event")
    train_frame, test_frame = train_test_split(
        frame, test_size=0.2, stratify=frame.completed, random_state=42
    )
    fit_frame, calibration_frame = train_test_split(
        train_frame, test_size=0.25, stratify=train_frame.completed, random_state=43
    )
    base = XGBClassifier(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        eval_metric="logloss",
        random_state=42,
        n_jobs=2,
    )
    fold_scores = cross_val_score(
        base,
        train_frame[FEATURES],
        train_frame.completed,
        cv=StratifiedKFold(5, shuffle=True, random_state=42),
        scoring="roc_auc",
    )
    base.fit(fit_frame[FEATURES], fit_frame.completed)
    calibrated = CalibratedClassifierCV(FrozenEstimator(base), method="sigmoid")
    calibrated.fit(calibration_frame[FEATURES], calibration_frame.completed)
    predictions = calibrated.predict_proba(test_frame[FEATURES])[:, 1]
    survival = CoxPHFitter(penalizer=0.1)
    survival.fit(
        train_frame[FEATURES + ["duration_months", "event_observed"]],
        duration_col="duration_months",
        event_col="event_observed",
    )
    report = {
        "source": "synthetic-trained" if synthetic else "cohort-trained",
        "rows": len(frame),
        "seed": 42,
        "cv_base_roc_auc": [float(x) for x in fold_scores],
        "cv_base_roc_auc_mean": float(fold_scores.mean()),
        "heldout_calibrated_roc_auc": float(roc_auc_score(test_frame.completed, predictions)),
        "heldout_brier_score": float(brier_score_loss(test_frame.completed, predictions)),
        "heldout_survival_concordance": float(
            survival.score(
                test_frame[FEATURES + ["duration_months", "event_observed"]],
                scoring_method="concordance_index",
            )
        ),
        "features": FEATURES,
        "note": "Synthetic performance is not evidence of clinical validity. Completion labels must be known; do not label early-censored participants as dropouts. One independent row per participant; grouped/site/time splits required for repeated or clustered data.",
    }
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / "retention.joblib.partial"
    joblib.dump(
        {
            "classifier": calibrated,
            "base_classifier": base,
            "survival": survival,
            "source": report["source"],
            "report": report,
        },
        temporary,
    )
    temporary.replace(output / "retention.joblib")
    (output / "training_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path)
    source.add_argument("--synthetic", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    train(args.csv, args.output, args.synthetic)
