from __future__ import annotations

import os
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DEFAULT_DATABASE_URL = "sqlite:///./smart_rental.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    equipment_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    check_in_date: Mapped[date] = mapped_column(Date)
    check_out_date: Mapped[date] = mapped_column(Date)
    engine_hours_per_day: Mapped[float] = mapped_column(Float)
    idle_hours_per_day: Mapped[float] = mapped_column(Float)
    rental_days: Mapped[int] = mapped_column(Integer)
    last_operator_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    prediction: Mapped[str] = mapped_column(String(16), index=True)
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    anomaly_score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class QrLogRecord(Base):
    __tablename__ = "qr_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action: Mapped[str] = mapped_column(String(16), index=True)
    equipment_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(32))
    site_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_date: Mapped[date] = mapped_column(Date)
    engine_hours_per_day: Mapped[float] = mapped_column(Float)
    idle_hours_per_day: Mapped[float] = mapped_column(Float)
    rental_days: Mapped[int] = mapped_column(Integer)
    last_operator_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    split: Mapped[str] = mapped_column(String(16), index=True)
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1: Mapped[float] = mapped_column(Float)
    actual_anomalies: Mapped[int] = mapped_column(Integer)
    predicted_anomalies: Mapped[int] = mapped_column(Integer)
    total_records: Mapped[int] = mapped_column(Integer)


def to_dict_usage(row: UsageRecord) -> dict:
    return {
        "id": row.id,
        "equipment_id": row.equipment_id,
        "type": row.type,
        "site_id": row.site_id,
        "check_in_date": row.check_in_date,
        "check_out_date": row.check_out_date,
        "engine_hours_per_day": row.engine_hours_per_day,
        "idle_hours_per_day": row.idle_hours_per_day,
        "rental_days": row.rental_days,
        "last_operator_id": row.last_operator_id,
        "status": row.status,
        "prediction": row.prediction,
        "risk_level": row.risk_level,
        "anomaly_score": row.anomaly_score,
        "reasons": [item.strip() for item in row.reasons.split(";") if item.strip()],
        "recommended_action": row.recommended_action,
        "created_at": row.created_at,
    }


def to_dict_qr(row: QrLogRecord) -> dict:
    return {
        "id": row.id,
        "action": row.action,
        "equipment_id": row.equipment_id,
        "type": row.type,
        "site_id": row.site_id,
        "event_date": row.event_date,
        "engine_hours_per_day": row.engine_hours_per_day,
        "idle_hours_per_day": row.idle_hours_per_day,
        "rental_days": row.rental_days,
        "last_operator_id": row.last_operator_id,
        "status": row.status,
        "created_at": row.created_at,
    }


def init_db(retries: int = 8, delay_seconds: float = 1.5) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception as error:
            last_error = error
            time.sleep(delay_seconds)
    else:
        raise last_error  # type: ignore[misc]

    with SessionLocal() as session:
        has_usage = session.scalar(select(UsageRecord.id).limit(1))
        if not has_usage:
            seed_usage_records(session)
        has_metrics = session.scalar(select(ModelMetric.id).limit(1))
        if not has_metrics:
            seed_model_metrics(session)
        session.commit()


def seed_usage_records(session: Session) -> None:
    path = Path(__file__).resolve().parent / "ml" / "artifacts" / "improved_anomaly_results_test.csv"
    if not path.exists():
        return
    df = pd.read_csv(path, keep_default_na=False)
    records = []
    for _, row in df.iterrows():
        reasons = str(row["Reasons"])
        risk = str(row["Risk Level"])
        status = "Anomaly" if row["Prediction"] == "Anomaly" else "Active"
        if int(row["Rental Days"]) >= 32:
            status = "Overdue"
        elif "Missing site assignment" in reasons:
            status = "Missing Site"
        elif "idle hours" in reasons.lower():
            status = "Idle Risk"
        elif risk == "High":
            status = "Anomaly"
        records.append(
            UsageRecord(
                equipment_id=row["Equipment ID"],
                type=row["Type"],
                site_id=None if str(row["Site ID"]).upper() == "NULL" else row["Site ID"],
                check_in_date=date.fromisoformat(row["Check-In Date"]),
                check_out_date=date.fromisoformat(row["Check-Out Date"]),
                engine_hours_per_day=float(row["Engine Hours/Day"]),
                idle_hours_per_day=float(row["Idle Hours/Day"]),
                rental_days=int(row["Rental Days"]),
                last_operator_id=None if str(row["Last Operator ID"]).upper() == "NULL" else row["Last Operator ID"],
                status=status,
                prediction=row["Prediction"],
                risk_level=risk,
                anomaly_score=float(row["Anomaly Score"]),
                reasons=reasons,
                recommended_action=str(row["Recommended Action"]),
            )
        )
    session.add_all(records)


def seed_model_metrics(session: Session) -> None:
    path = Path(__file__).resolve().parent / "ml" / "artifacts" / "improved_classification_metrics.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        session.add(
            ModelMetric(
                split=str(row["Split"]),
                accuracy=float(row["Accuracy"]),
                precision=float(row["Precision"]),
                recall=float(row["Recall"]),
                f1=float(row["F1"]),
                actual_anomalies=int(row["Actual Anomalies"]),
                predicted_anomalies=int(row["Predicted Anomalies"]),
                total_records=int(row["Total Records"]),
            )
        )
