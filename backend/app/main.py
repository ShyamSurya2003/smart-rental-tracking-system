from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import select

from app.data import USAGE_LOGS, build_log
from app.db import ModelMetric, QrLogRecord, SessionLocal, UsageRecord, init_db, to_dict_qr, to_dict_usage
from app.ml.predictor import predict
from app.schemas import CheckInCreate, CheckInResponse, DashboardResponse, QrLogCreate, QrLogResponse

app = FastAPI(title="Smart Rental Tracking System API")

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"http://.*:(5173|5199)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def load_model_metrics() -> dict:
    with SessionLocal() as session:
        row = session.scalar(select(ModelMetric).where(ModelMetric.split == "test"))
        if not row:
            row = session.scalar(select(ModelMetric).limit(1))
        if not row:
            return {}
        return {
            "accuracy": round(row.accuracy * 100, 2),
            "precision": round(row.precision * 100, 2),
            "recall": round(row.recall * 100, 2),
            "f1": round(row.f1 * 100, 2),
        }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now()}


@app.get("/api/database-status")
def database_status() -> dict:
    with SessionLocal() as session:
        usage_count = len([row for row in session.scalars(select(UsageRecord.id))])
        qr_count = len([row for row in session.scalars(select(QrLogRecord.id))])
        metric_count = len([row for row in session.scalars(select(ModelMetric.id))])

    top_location = next((row["name"] for row in usage_per_site if row["name"] != "NULL"), "N/A")
    return {
        "database_url": "postgresql" if "postgresql" in os.getenv("DATABASE_URL", "") else "sqlite-local-fallback",
        "usage_records": usage_count,
        "qr_logs": qr_count,
        "model_metrics": metric_count,
    }


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(date_range: str | None = Query("30d", alias="range")) -> dict:
    rows = all_usage_rows()
    rows = apply_date_range(rows, date_range)
    total = len(rows)
    anomalies = [row for row in rows if row["prediction"] == "Anomaly"]
    active = [row for row in rows if row["status"] == "Active"]
    avg_utilization = round(
        sum(row["engine_hours_per_day"] / max(row["engine_hours_per_day"] + row["idle_hours_per_day"], 1) for row in rows)
        / max(total, 1)
        * 100
    )

    status_counts = Counter(row["status"] for row in rows)
    risk_counts = Counter(row["risk_level"] for row in rows)
    by_type = defaultdict(list)
    for row in rows:
        by_type[row["type"]].append(row)

    utilization_by_type = []
    for equipment_type, type_rows in by_type.items():
        utilization = sum(
            row["engine_hours_per_day"] / max(row["engine_hours_per_day"] + row["idle_hours_per_day"], 1) for row in type_rows
        )
        utilization_by_type.append({"name": equipment_type, "utilization": round(utilization / len(type_rows) * 100)})

    trend = []
    latest_day = max((row["check_in_date"] for row in rows), default=date.today())
    start = min((row["check_in_date"] for row in rows), default=latest_day)
    step_days = max(1, (latest_day - start).days // 9)
    for i in range(10):
        bucket_start = start + timedelta(days=i * step_days)
        bucket_end = bucket_start + timedelta(days=step_days - 1)
        day_rows = [row for row in rows if bucket_start <= row["check_in_date"] <= bucket_end]
        trend.append({
            "date": bucket_start.strftime("%b %d"),
            "engine": round(sum(row["engine_hours_per_day"] for row in day_rows), 1),
            "idle": round(sum(row["idle_hours_per_day"] for row in day_rows), 1),
        })

    demand_forecast = [
        {"day": "Day 1", "Excavator": 32, "Crane": 18, "Bulldozer": 24, "Grader": 14},
        {"day": "Day 3", "Excavator": 36, "Crane": 16, "Bulldozer": 27, "Grader": 16},
        {"day": "Day 7", "Excavator": 43, "Crane": 21, "Bulldozer": 29, "Grader": 18},
        {"day": "Day 15", "Excavator": 48, "Crane": 20, "Bulldozer": 34, "Grader": 17},
        {"day": "Day 30", "Excavator": 57, "Crane": 24, "Bulldozer": 39, "Grader": 22},
    ]

    return {
        "kpis": {
            "total_equipment": total,
            "active_rentals": len(active),
            "available_equipment": max(220 - total, 18),
            "overdue_assets": status_counts.get("Overdue", 0),
            "anomaly_alerts": len(anomalies),
            "average_utilization": avg_utilization,
            "model_f1": load_model_metrics().get("f1"),
            "model_precision": load_model_metrics().get("precision"),
        },
        "status_distribution": [{"name": key, "value": value} for key, value in status_counts.items()],
        "utilization_by_type": utilization_by_type,
        "engine_idle_trend": trend,
        "risk_distribution": [{"name": key, "value": value} for key, value in risk_counts.items()],
        "demand_forecast": demand_forecast,
        "recent_alerts": [
            {
                "equipment_id": row["equipment_id"],
                "type": row["type"],
                "risk_level": row["risk_level"],
                "message": ", ".join(row["reasons"][:2]),
            }
            for row in anomalies[-5:]
        ],
    }


def filter_rows(
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    equipment_type: str | None = None,
    site_id: str | None = None,
    operator_id: str | None = None,
    min_idle: float | None = None,
    max_idle: float | None = None,
    min_rental_days: int | None = None,
    max_rental_days: int | None = None,
):
    rows = all_usage_rows()
    if search:
        needle = search.lower()
        rows = [
            row for row in rows
            if needle in row["equipment_id"].lower()
            or needle in row["type"].lower()
            or needle in str(row["site_id"]).lower()
            or needle in str(row["last_operator_id"]).lower()
            or needle in row["status"].lower()
        ]
    if status and status != "All":
        rows = [row for row in rows if row["status"] == status]
    if risk and risk != "All":
        rows = [row for row in rows if row["risk_level"] == risk]
    if equipment_type and equipment_type != "All":
        rows = [row for row in rows if row["type"] == equipment_type]
    if site_id and site_id != "All":
        rows = [row for row in rows if str(row["site_id"] or "NULL") == site_id]
    if operator_id and operator_id != "All":
        rows = [row for row in rows if str(row["last_operator_id"] or "NULL") == operator_id]
    if min_idle is not None:
        rows = [row for row in rows if row["idle_hours_per_day"] >= min_idle]
    if max_idle is not None:
        rows = [row for row in rows if row["idle_hours_per_day"] <= max_idle]
    if min_rental_days is not None:
        rows = [row for row in rows if row["rental_days"] >= min_rental_days]
    if max_rental_days is not None:
        rows = [row for row in rows if row["rental_days"] <= max_rental_days]
    return rows


@app.get("/api/equipment")
def equipment(
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    equipment_type: str | None = None,
    site_id: str | None = None,
    operator_id: str | None = None,
    min_idle: float | None = None,
    max_idle: float | None = None,
    min_rental_days: int | None = None,
    max_rental_days: int | None = None,
) -> list[dict]:
    return filter_rows(search, status, risk, equipment_type, site_id, operator_id, min_idle, max_idle, min_rental_days, max_rental_days)[:250]


@app.get("/api/usage-logs")
def usage_logs(
    search: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    equipment_type: str | None = None,
    site_id: str | None = None,
    operator_id: str | None = None,
    min_idle: float | None = None,
    max_idle: float | None = None,
    min_rental_days: int | None = None,
    max_rental_days: int | None = None,
    limit: int = Query(default=50, le=250),
) -> dict:
    rows = filter_rows(search, status, risk, equipment_type, site_id, operator_id, min_idle, max_idle, min_rental_days, max_rental_days)
    total_runtime = round(sum(row["engine_hours_per_day"] for row in rows), 1)
    total_idle = round(sum(row["idle_hours_per_day"] for row in rows), 1)
    total_rented = sum(row["rental_days"] for row in rows)
    downtime = round(sum(max(0, row["idle_hours_per_day"] - row["engine_hours_per_day"]) for row in rows), 1)
    fuel_usage = round(total_runtime * 15.5, 1)
    known_site_rows = [row for row in rows if row["site_id"]]
    usage_per_site = sorted([
        {
            "name": site,
            "value": round(sum(row["engine_hours_per_day"] * row["rental_days"] for row in site_rows), 1),
        }
        for site, site_rows in group_rows(known_site_rows, "site_id").items()
    ], key=lambda row: row["value"], reverse=True)[:10]
    valid_usage_rows = [
        row for row in rows
        if row["engine_hours_per_day"] > 0 and row["rental_days"] > 0 and row["idle_hours_per_day"] >= 0
    ]
    low_use_rows = [row for row in valid_usage_rows if row["engine_hours_per_day"] < 8]
    low_use_rows = sorted(
        low_use_rows or valid_usage_rows,
        key=lambda row: (
            row["engine_hours_per_day"] / max(row["engine_hours_per_day"] + row["idle_hours_per_day"], 1),
            -row["rental_days"],
        ),
    )
    if len(low_use_rows) > 10:
        step = max(1, len(low_use_rows) // 10)
        sampled_under_used = low_use_rows[::step][:10]
    else:
        sampled_under_used = low_use_rows[:10]
    under_utilized = [
        {
            "name": row["equipment_id"],
            "value": round(
                min(100, (1 - (row["engine_hours_per_day"] / max(row["engine_hours_per_day"] + row["idle_hours_per_day"], 1))) * 70
                    + min(row["rental_days"], 45) / 45 * 30),
                1,
            ),
            "idle": round(row["idle_hours_per_day"], 1),
            "rental_days": row["rental_days"],
        }
        for row in sampled_under_used
    ]
    top_location = next((row["name"] for row in usage_per_site if row["name"] != "NULL"), "N/A")
    recommendations = []
    if total_idle > total_runtime * 0.35:
        recommendations.append("Reduce idle time by reallocating low-use equipment to active sites.")
    if downtime > 0:
        recommendations.append("Inspect assets with idle hours higher than runtime to reduce downtime.")
    if top_location != "N/A":
        recommendations.append(f"Prioritize availability at {top_location} because it has the highest runtime usage.")
    recommendations.append("Flag under-utilized assets for reassignment or early return.")
    return {
        "total": len(rows),
        "rows": rows[:limit],
        "summary": {
            "runtime_hours": total_runtime,
            "fuel_usage": fuel_usage,
            "idle_hours": total_idle,
            "total_rented_hours": total_rented * 24,
            "downtime": downtime,
            "top_location": top_location,
        },
        "usage_per_site": usage_per_site,
        "under_utilized": under_utilized,
        "recommendations": recommendations,
    }


@app.get("/api/filter-options")
def filter_options() -> dict:
    rows = all_usage_rows()

    def values(key: str, limit: int = 80) -> list[str]:
        items = sorted({str(row[key] or "NULL") for row in rows})
        return ["All", *items[:limit]]

    return {
        "equipment_types": values("type"),
        "statuses": values("status"),
        "risks": ["All", "Low", "Medium", "High"],
        "sites": values("site_id"),
        "operators": values("last_operator_id"),
        "predictions": ["All", "Anomaly", "Normal"],
    }


@app.get("/api/qr-logs")
def qr_logs(action: str | None = None) -> dict:
    with SessionLocal() as session:
        statement = select(QrLogRecord)
        if action and action != "All":
            statement = statement.where(QrLogRecord.action == action)
        rows = [to_dict_qr(row) for row in session.scalars(statement.order_by(QrLogRecord.id.desc()).limit(100))]
        return {"total": len(rows), "rows": rows}


@app.post("/api/qr-log", response_model=QrLogResponse)
def qr_log(payload: QrLogCreate) -> dict:
    engine_hours = float(payload.engine_hours_per_day or 0)
    idle_hours = float(payload.idle_hours_per_day or 0)
    rental_days = int(payload.rental_days or 1)
    checkin_like = CheckInCreate(
        equipment_id=payload.equipment_id,
        type=payload.type,
        site_id=payload.site_id,
        check_in_date=payload.event_date,
        check_out_date=payload.event_date,
        engine_hours_per_day=engine_hours,
        idle_hours_per_day=idle_hours,
        rental_days=rental_days,
        last_operator_id=payload.last_operator_id,
    )
    status = "Logged In" if payload.action == "LOG_IN" else "Logged Out"
    if not payload.site_id:
        status = "Missing Site"
    elif not payload.last_operator_id:
        status = "Missing Operator"
    elif idle_hours >= 8:
        status = "Idle Risk"
    with SessionLocal() as session:
        if payload.action == "LOG_OUT":
            last_login = session.scalar(
                select(QrLogRecord)
                .where(QrLogRecord.action == "LOG_IN", QrLogRecord.equipment_id == payload.equipment_id)
                .order_by(QrLogRecord.id.desc())
            )
            if not last_login:
                raise HTTPException(status_code=400, detail="No active log-in found for this equipment.")
            if (last_login.last_operator_id or "") != (payload.last_operator_id or ""):
                raise HTTPException(status_code=400, detail="Only the same operator who logged in can log out.")
        record_data = payload.model_dump()
        record_data.update(engine_hours_per_day=engine_hours, idle_hours_per_day=idle_hours, rental_days=rental_days)
        record = QrLogRecord(**record_data, status=status, created_at=datetime.now())
        session.add(record)
        session.flush()
        log = to_dict_qr(record)
        if payload.action == "LOG_OUT":
            result = predict(checkin_like)
            session.add(usage_record_from_log(build_log(0, checkin_like), result))
        session.commit()
    return {
        "log": log,
        "message": f"{payload.equipment_id} {'log-in' if payload.action == 'LOG_IN' else 'log-out'} details saved.",
    }


@app.get("/api/alerts")
def alerts(risk: str | None = None, date_range: str | None = Query("30d", alias="range")) -> list[dict]:
    today = date.today()
    rows = []
    for row in all_usage_rows():
        days_left = (row["check_out_date"] - today).days
        if -30 <= days_left <= 7:
            row = {**row, "days_left": days_left}
            rows.append(row)
    rows = apply_date_range(rows, date_range)
    if risk and risk != "All":
        rows = [row for row in rows if row["risk_level"] == risk]
    return [
        {
            "id": row["id"],
            "equipment_id": row["equipment_id"],
            "type": row["type"],
            "site_id": row["site_id"],
            "risk_level": row["risk_level"],
            "alert_type": "Overdue" if row["days_left"] < 0 else "Return Due",
            "check_out_date": row["check_out_date"],
            "message": (
                f"Return overdue by {abs(row['days_left'])} days."
                if row["days_left"] < 0
                else f"Return time approaching in {row['days_left']} days."
            ),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def apply_date_range(rows: list[dict], range_value: str | None) -> list[dict]:
    days_by_range = {"30d": 30, "3m": 90, "6m": 180, "1y": 365}
    days = days_by_range.get(range_value or "30d")
    if not days or not rows:
        return rows
    latest = max(row["check_in_date"] for row in rows)
    cutoff = latest - timedelta(days=days)
    return [row for row in rows if row["check_in_date"] >= cutoff]


@app.get("/api/forecast")
def forecast(range: str | None = Query("30d")) -> list[dict]:
    days_by_range = {"30d": 30, "3m": 90, "6m": 180, "1y": 365}
    max_day = days_by_range.get(range or "30d", 30)
    forecast_days = [1, 7, 15, 30, 60, 90, 180, 365]
    rows = []
    for day in [day for day in forecast_days if day <= max_day]:
        growth = day / 30
        rows.append({
            "day": f"Day {day}",
            "Excavator": round(32 + growth * 25),
            "Crane": round(18 + growth * 6),
            "Bulldozer": round(24 + growth * 15),
            "Grader": round(14 + growth * 8),
        })
    return rows


@app.post("/api/checkin", response_model=CheckInResponse)
def checkin(payload: CheckInCreate) -> dict:
    row = build_log(len(USAGE_LOGS) + 1, payload)
    result = predict(payload)
    with SessionLocal() as session:
        record = usage_record_from_log(row, result)
        session.add(record)
        session.commit()
        session.refresh(record)
        row = to_dict_usage(record)
    popup_triggered = result["prediction"] == "Anomaly"
    notification = {
        "popup_triggered": popup_triggered,
        "email_status": "queued" if popup_triggered else "not_required",
        "email_to": "manager@rental-ops.local",
        "message": (
            f"Alert queued for {payload.equipment_id}: {result['risk_level']} risk anomaly."
            if popup_triggered
            else f"No alert required for {payload.equipment_id}."
        ),
    }
    return {"usage_log": row, "prediction_result": result, "notification": notification}


def all_usage_rows() -> list[dict]:
    with SessionLocal() as session:
        return [to_dict_usage(row) for row in session.scalars(select(UsageRecord).order_by(UsageRecord.id))]


def group_rows(rows: list[dict], key: str) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


def usage_record_from_log(row: dict, result: dict | None = None) -> UsageRecord:
    return UsageRecord(
        equipment_id=row["equipment_id"],
        type=row["type"],
        site_id=row["site_id"],
        check_in_date=row["check_in_date"],
        check_out_date=row["check_out_date"],
        engine_hours_per_day=row["engine_hours_per_day"],
        idle_hours_per_day=row["idle_hours_per_day"],
        rental_days=row["rental_days"],
        last_operator_id=row["last_operator_id"],
        status=row["status"],
        prediction=row["prediction"],
        risk_level=row["risk_level"],
        anomaly_score=row["anomaly_score"],
        reasons="; ".join(row["reasons"]),
        recommended_action=(result or {}).get("recommended_action", ""),
        created_at=datetime.now(),
    )


@app.get("/api/model-results")
def model_results(
    search: str | None = None,
    prediction: str | None = None,
    risk: str | None = None,
    equipment_type: str | None = None,
    limit: int = Query(default=100, le=5000),
) -> dict:
    rows = filter_rows(search=search, risk=risk, equipment_type=equipment_type)
    if prediction and prediction != "All":
        rows = [row for row in rows if row["prediction"] == prediction]
    if not search and (not prediction or prediction == "All") and (not risk or risk == "All") and (not equipment_type or equipment_type == "All"):
        ordered = sorted(rows, key=lambda row: row["anomaly_score"])
        if len(ordered) > limit:
            step = max(1, len(ordered) // limit)
            rows = ordered[::step][:limit]
        else:
            rows = ordered
    return {"total": len(rows), "rows": rows[:limit]}


@app.get("/api/model-metrics")
def model_metrics() -> dict:
    with SessionLocal() as session:
        rows = [
            {
                "split": row.split,
                "accuracy": round(row.accuracy * 100, 2),
                "precision": round(row.precision * 100, 2),
                "recall": round(row.recall * 100, 2),
                "f1": round(row.f1 * 100, 2),
                "actual_anomalies": row.actual_anomalies,
                "predicted_anomalies": row.predicted_anomalies,
                "total_records": row.total_records,
            }
            for row in session.scalars(select(ModelMetric).order_by(ModelMetric.id))
        ]
    return {"rows": rows}


@app.get("/api/model-summary")
def model_summary() -> dict:
    rows = all_usage_rows()
    prediction_counts = Counter(row["prediction"] for row in rows)
    anomaly_rows = [row for row in rows if row["prediction"] == "Anomaly"]
    anomaly_type_counts = Counter(row["type"] for row in anomaly_rows)
    risk_counts = Counter(row["risk_level"] for row in rows)

    buckets = [
        {"name": "0-20", "min": 0, "max": 0.2, "value": 0},
        {"name": "20-40", "min": 0.2, "max": 0.4, "value": 0},
        {"name": "40-60", "min": 0.4, "max": 0.6, "value": 0},
        {"name": "60-80", "min": 0.6, "max": 0.8, "value": 0},
        {"name": "80-100", "min": 0.8, "max": 1.01, "value": 0},
    ]
    for row in rows:
        score = float(row["anomaly_score"])
        for bucket in buckets:
            if bucket["min"] <= score < bucket["max"]:
                bucket["value"] += 1
                break

    prediction_distribution = [
        {"name": "Normal", "value": prediction_counts.get("Normal", 0)},
        {"name": "Anomaly", "value": prediction_counts.get("Anomaly", 0)},
    ]
    scatter_rows = sorted(rows, key=lambda row: row["anomaly_score"], reverse=True)[:500]
    return {
        "total": len(rows),
        "anomalies": len(anomaly_rows),
        "normal": len(rows) - len(anomaly_rows),
        "prediction_distribution": prediction_distribution,
        "anomaly_types": [{"name": key, "value": value} for key, value in anomaly_type_counts.items()],
        "risk_distribution": [{"name": key, "value": value} for key, value in risk_counts.items()],
        "score_buckets": [{"name": bucket["name"], "value": bucket["value"]} for bucket in buckets],
        "scatter_rows": scatter_rows,
    }
