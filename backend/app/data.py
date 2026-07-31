from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from app.schemas import CheckInCreate


EQUIPMENT_TYPES = ["Excavator", "Crane", "Bulldozer", "Grader"]
SITES = ["S001", "S002", "S003", "S004", "S006"]
OPERATORS = ["OP101", "OP106", "OP114", "OP203", "OP301"]


def seed_logs_from_improved_results() -> list[dict]:
    path = Path(__file__).resolve().parent / "ml" / "artifacts" / "improved_anomaly_results_test.csv"
    if not path.exists():
        return []

    df = pd.read_csv(path, keep_default_na=False)
    logs = []
    for idx, row in df.iterrows():
        reasons = [reason.strip() for reason in str(row["Reasons"]).split(";") if reason.strip()]
        risk = str(row["Risk Level"])
        status = "Anomaly" if row["Prediction"] == "Anomaly" else "Active"
        if risk == "High":
            status = "Anomaly"
        elif "Missing site assignment" in reasons:
            status = "Missing Site"
        elif "High idle hours" in "; ".join(reasons) or "Extremely high idle hours" in "; ".join(reasons):
            status = "Idle Risk"
        elif int(row["Rental Days"]) >= 32:
            status = "Overdue"

        logs.append(
            {
                "id": int(idx) + 1,
                "equipment_id": row["Equipment ID"],
                "type": row["Type"],
                "site_id": None if str(row["Site ID"]).upper() == "NULL" else row["Site ID"],
                "check_in_date": date.fromisoformat(row["Check-In Date"]),
                "check_out_date": date.fromisoformat(row["Check-Out Date"]),
                "engine_hours_per_day": float(row["Engine Hours/Day"]),
                "idle_hours_per_day": float(row["Idle Hours/Day"]),
                "rental_days": int(row["Rental Days"]),
                "last_operator_id": None if str(row["Last Operator ID"]).upper() == "NULL" else row["Last Operator ID"],
                "status": status,
                "prediction": row["Prediction"],
                "risk_level": risk,
                "anomaly_score": float(row["Anomaly Score"]),
                "reasons": reasons,
                "created_at": datetime.now(),
            }
        )
    return logs


def seed_logs() -> list[dict]:
    improved_logs = seed_logs_from_improved_results()
    if improved_logs:
        return improved_logs

    rows = [
        ("EQX1001", "Excavator", "S003", "2025-04-01", "2025-04-16", 1.5, 10, 15, "OP101"),
        ("EQX1002", "Crane", None, "2025-03-10", "2025-03-30", 0, 11, 20, None),
        ("EQX1003", "Bulldozer", "S002", "2025-02-15", "2025-03-11", 7.5, 0.5, 25, "OP203"),
        ("EQX1004", "Excavator", "S004", "2025-05-05", "2025-05-15", 2, 9, 10, "OP106"),
        ("EQX1005", "Bulldozer", "S006", "2025-01-01", "2025-01-31", 8, 0, 30, "OP301"),
        ("EQX1006", "Grader", "S001", "2025-04-05", "2025-04-23", 3, 6, 18, "OP114"),
        ("EQX1007", "Excavator", None, "2025-03-20", "2025-04-01", 0, 12, 12, None),
    ]
    logs = []
    for idx, row in enumerate(rows, start=1):
        item = CheckInCreate(
            equipment_id=row[0],
            type=row[1],
            site_id=row[2],
            check_in_date=date.fromisoformat(row[3]),
            check_out_date=date.fromisoformat(row[4]),
            engine_hours_per_day=row[5],
            idle_hours_per_day=row[6],
            rental_days=row[7],
            last_operator_id=row[8],
        )
        logs.append(build_log(idx, item))

    base_date = date(2025, 5, 1)
    for idx in range(8, 168):
        equipment_type = EQUIPMENT_TYPES[idx % len(EQUIPMENT_TYPES)]
        missing_site = idx % 19 == 0
        missing_operator = idx % 23 == 0
        engine_hours = round(((idx * 1.7) % 9) + (0 if idx % 13 else -1), 1)
        engine_hours = max(engine_hours, 0)
        idle_hours = round((idx * 2.3) % 12, 1)
        if idx % 17 == 0:
            idle_hours = 11.5
        rental_days = 5 + (idx * 3) % 31
        item = CheckInCreate(
            equipment_id=f"EQX{1000 + idx}",
            type=equipment_type,
            site_id=None if missing_site else SITES[idx % len(SITES)],
            check_in_date=base_date + timedelta(days=idx % 75),
            check_out_date=base_date + timedelta(days=(idx % 75) + rental_days),
            engine_hours_per_day=engine_hours,
            idle_hours_per_day=idle_hours,
            rental_days=rental_days,
            last_operator_id=None if missing_operator else OPERATORS[idx % len(OPERATORS)],
        )
        logs.append(build_log(idx, item))
    return logs


def build_log(row_id: int, item: CheckInCreate) -> dict:
    from app.ml.predictor import predict

    result = predict(item)
    return {
        "id": row_id,
        **item.model_dump(),
        "status": status_for(item, result["risk_level"]),
        "prediction": result["prediction"],
        "risk_level": result["risk_level"],
        "anomaly_score": result["anomaly_score"],
        "reasons": result["reasons"],
        "created_at": datetime.now(),
    }


def status_for(item: CheckInCreate, risk_level: str) -> str:
    if risk_level == "High":
        return "Anomaly"
    if not item.site_id:
        return "Missing Site"
    if item.idle_hours_per_day >= 8:
        return "Idle Risk"
    if item.rental_days > 28:
        return "Overdue"
    return "Active"


USAGE_LOGS = seed_logs()
QR_LOGS: list[dict] = []
