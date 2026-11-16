import math
from functools import lru_cache
from pathlib import Path

from backend.app.schemas import Driver, PatientProfile, Retention, SurvivalPoint, Trial
from backend.app.settings import get_settings

FEATURES = ["age", "comorbidity_count", "visits_per_month", "phase", "distance_km"]
LABELS = ["Age", "Comorbidity count", "Visit frequency", "Trial phase", "Travel distance"]


def features(patient: PatientProfile, trial: Trial) -> dict | None:
    phases = {"PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}
    if trial.distance_km is None or trial.visits_per_month is None or trial.phase not in phases:
        return None
    return dict(
        zip(
            FEATURES,
            [
                patient.age,
                len({f.code for f in patient.facts if f.kind == "Condition" and not f.negative}),
                trial.visits_per_month,
                phases[trial.phase],
                trial.distance_km,
            ],
        )
    )


@lru_cache
def load_artifacts(path: str, modified: float):
    import joblib

    # Only server-managed local artifacts are loaded; never deserialize an uploaded model.
    return joblib.load(path)


def score_retention(patient: PatientProfile, trial: Trial) -> Retention:
    values = features(patient, trial)
    if values is None:
        return Retention(
            source="unavailable",
            explanation="Distance, visit frequency, and a supported phase are required. Set measured patient–trial features before scoring live protocols.",
            driver_units="unavailable",
        )
    artifact: Path = get_settings().artifact_dir / "retention.joblib"
    if artifact.exists():
        import pandas as pd
        import shap

        models = load_artifacts(str(artifact.resolve()), artifact.stat().st_mtime)
        frame = pd.DataFrame([values], columns=FEATURES)
        probability = float(models["classifier"].predict_proba(frame)[0, 1])
        times = [0, 3, 6, 12, 18, 24]
        curve = models["survival"].predict_survival_function(frame, times=times).iloc[:, 0]
        contributions = shap.TreeExplainer(models["base_classifier"])(frame).values[0]
        return Retention(
            completion_probability=probability,
            source=models["source"],
            explanation="Calibrated XGBoost completion classifier and independently fitted CoxPH retention curve. SHAP explains the base classifier's log-odds, before calibration.",
            survival=[SurvivalPoint(month=t, probability=float(p)) for t, p in zip(times, curve)],
            drivers=sorted(
                [Driver(feature=label, impact=float(value)) for label, value in zip(LABELS, contributions)],
                key=lambda d: abs(d.impact),
                reverse=True,
            ),
            driver_units="base-model log-odds",
        )
    contributions = [
        Driver(feature="Visit frequency", impact=-0.023 * values["visits_per_month"]),
        Driver(feature="Travel distance", impact=-0.0007 * values["distance_km"]),
        Driver(feature="Comorbidity count", impact=-0.015 * values["comorbidity_count"]),
        Driver(feature="Age", impact=-0.001 * max(values["age"] - 50, 0)),
        Driver(feature="Trial phase", impact=0.006 * values["phase"]),
    ]
    probability = max(0.15, min(0.97, 0.94 + sum(d.impact for d in contributions)))
    hazard = -math.log(probability) / 12
    return Retention(
        completion_probability=probability,
        source="illustrative",
        explanation="Illustrative formula on synthetic inputs. Curve is exponential, not fitted Lifelines; impacts are formula terms, not SHAP values. Train artifacts to enable XGBoost, CoxPH, and SHAP.",
        survival=[SurvivalPoint(month=t, probability=math.exp(-hazard * t)) for t in [0, 3, 6, 12, 18, 24]],
        drivers=sorted(contributions, key=lambda d: abs(d.impact), reverse=True),
        driver_units="illustrative probability contribution",
    )
