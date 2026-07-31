from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd

from app.schemas import CheckInCreate

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
PIPELINE_PATH = ARTIFACT_DIR / "improved_anomaly_pipeline.pkl"
PREPROCESSOR_PATH = ARTIFACT_DIR / "preprocessor.pkl"
ISOLATION_FOREST_PATH = ARTIFACT_DIR / "isolation_forest.pkl"
CALIBRATION_PATH = ARTIFACT_DIR / "isolation_forest_calibration.json"
_PIPELINE = None
_PREPROCESSOR = None
_ISOLATION_FOREST = None
_CALIBRATION = None


def get_pipeline():
    global _PIPELINE
    if _PIPELINE is None and PIPELINE_PATH.exists():
        _PIPELINE = joblib.load(PIPELINE_PATH)
    return _PIPELINE


def get_isolation_forest():
    global _PREPROCESSOR, _ISOLATION_FOREST, _CALIBRATION
    if _PREPROCESSOR is None and PREPROCESSOR_PATH.exists():
        _PREPROCESSOR = joblib.load(PREPROCESSOR_PATH)
    if _ISOLATION_FOREST is None and ISOLATION_FOREST_PATH.exists():
        _ISOLATION_FOREST = joblib.load(ISOLATION_FOREST_PATH)
    if _CALIBRATION is None and CALIBRATION_PATH.exists():
        _CALIBRATION = json.loads(CALIBRATION_PATH.read_text())
    if _PREPROCESSOR is None or _ISOLATION_FOREST is None:
        return None
    return _PREPROCESSOR, _ISOLATION_FOREST, _CALIBRATION or {}


def missing(value: str | None) -> bool:
    return value is None or str(value).strip().upper() in ["", "NULL", "NONE", "NAN"]


def feature_frame(item: CheckInCreate) -> pd.DataFrame:
    engine = float(item.engine_hours_per_day)
    idle = float(item.idle_hours_per_day)
    return pd.DataFrame(
        [
            {
                "Type": item.type,
                "Engine Hours/Day": engine,
                "Idle Hours/Day": idle,
                "Rental Days": int(item.rental_days),
                "Site Missing": int(missing(item.site_id)),
                "Operator Missing": int(missing(item.last_operator_id)),
                "Idle Ratio": idle / (engine + idle + 1e-6),
                "Utilisation %": engine / 24 * 100,
            }
        ]
    )


def corrected_feature_frame(item: CheckInCreate) -> pd.DataFrame:
    engine = float(item.engine_hours_per_day)
    idle = float(item.idle_hours_per_day)
    rental_days = int(item.rental_days)
    check_in = pd.to_datetime(item.check_in_date)
    check_out = pd.to_datetime(item.check_out_date)
    accounted_hours = engine + idle
    return pd.DataFrame(
        [
            {
                "Equipment ID": item.equipment_id,
                "Type": item.type,
                "Site ID": "NULL" if missing(item.site_id) else item.site_id,
                "Check-In Date": item.check_in_date.isoformat(),
                "Check-Out Date": item.check_out_date.isoformat(),
                "Engine Hours/Day": engine,
                "Idle Hours/Day": idle,
                "Rental Days": rental_days,
                "Last Operator ID": "NULL" if missing(item.last_operator_id) else item.last_operator_id,
                "Utilisation %": engine / 24 * 100,
                "Idle Ratio": idle / (accounted_hours + 1e-6),
                "Accounted Hours": accounted_hours,
                "Unused Hours": max(0.0, 24 - accounted_hours),
                "Check-In Year": int(check_in.year),
                "Check-In Month": int(check_in.month),
                "Check-In Week": int(check_in.isocalendar().week),
                "Check-In Day": int(check_in.day),
                "Check-In DayOfWeek": int(check_in.dayofweek),
                "Rental Duration": max(0, int((check_out - check_in).days)),
                "Estimated Fuel Consumption": round(engine * 15.5, 2),
            }
        ]
    )


def reasons_for(item: CheckInCreate) -> list[str]:
    reasons = []
    engine = float(item.engine_hours_per_day)
    idle = float(item.idle_hours_per_day)
    if missing(item.site_id):
        reasons.append("Missing site assignment")
    if missing(item.last_operator_id):
        reasons.append("Missing driver/operator ID")
    if engine == 0 and idle == 0:
        reasons.append("No engine or idle usage recorded")
    elif engine <= 1:
        reasons.append("Very low engine usage")
    if idle >= 10:
        reasons.append("Extremely high idle hours")
    elif idle >= 6:
        reasons.append("High idle hours")
    if idle > engine * 2 and idle >= 5:
        reasons.append("Idle time is much higher than engine time")
    if item.rental_days >= 32:
        reasons.append("Unusually long rental duration")
    return reasons or ["Usage pattern looks normal"]


def risk_from_score(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.45:
        return "Medium"
    return "Low"


def predict(item: CheckInCreate) -> dict:
    corrected_model = get_isolation_forest()
    if corrected_model is not None:
        preprocessor, model, calibration = corrected_model
        transformed = preprocessor.transform(corrected_feature_frame(item))
        raw_score = float(-model.decision_function(transformed)[0])
        low = float(calibration.get("raw_score_p01", -0.06))
        high = float(calibration.get("raw_score_p99", 0.16))
        score = (raw_score - low) / (high - low + 1e-9)
        score = max(0.0, min(score, 1.0))
        model_flag = int(model.predict(transformed)[0]) == -1
    else:
        pipeline = get_pipeline()
        model_flag = None
        if pipeline is not None:
            score = float(pipeline.predict_proba(feature_frame(item))[0, 1])
        else:
            # Fallback keeps the API usable if artifacts are not copied.
            score = 0.0
            if missing(item.site_id):
                score += 0.25
            if missing(item.last_operator_id):
                score += 0.22
            if item.engine_hours_per_day <= 1:
                score += 0.18
            if item.idle_hours_per_day >= 8:
                score += 0.24
            if item.rental_days >= 25:
                score += 0.16
            if item.idle_hours_per_day > item.engine_hours_per_day * 2 and item.idle_hours_per_day >= 5:
                score += 0.15

    score = min(round(score, 4), 0.9999)
    prediction = "Anomaly" if (model_flag if model_flag is not None else score >= 0.5) else "Normal"
    risk_level = risk_from_score(score)
    reasons = reasons_for(item)

    action = "Continue monitoring asset usage."
    if risk_level == "Medium":
        action = "Review equipment assignment and usage pattern."
    if risk_level == "High":
        action = "Verify equipment location, operator assignment, and rental extension immediately."

    return {
        "equipment_id": item.equipment_id,
        "prediction": prediction,
        "risk_level": risk_level,
        "anomaly_score": score,
        "reasons": reasons,
        "recommended_action": action,
        "predicted_at": datetime.now(),
    }
