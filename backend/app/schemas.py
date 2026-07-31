from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


EquipmentType = Literal["Excavator", "Crane", "Bulldozer", "Grader"]
PredictionLabel = Literal["Normal", "Anomaly"]
RiskLevel = Literal["Low", "Medium", "High"]
QrAction = Literal["LOG_IN", "LOG_OUT"]


class CheckInCreate(BaseModel):
    equipment_id: str = Field(min_length=3, examples=["EQX1007"])
    type: EquipmentType
    site_id: str | None = Field(default=None, examples=["S003"])
    check_in_date: date
    check_out_date: date
    engine_hours_per_day: float = Field(ge=0, le=24)
    idle_hours_per_day: float = Field(ge=0, le=24)
    rental_days: int = Field(ge=1)
    last_operator_id: str | None = Field(default=None, examples=["OP114"])


class QrLogCreate(BaseModel):
    action: QrAction
    equipment_id: str = Field(min_length=3, examples=["EQX1007"])
    type: EquipmentType
    site_id: str | None = Field(default=None, examples=["S003"])
    event_date: date
    engine_hours_per_day: float | None = Field(default=None, ge=0, le=24)
    idle_hours_per_day: float | None = Field(default=None, ge=0, le=24)
    rental_days: int | None = Field(default=None, ge=1)
    last_operator_id: str | None = Field(default=None, examples=["OP114"])


class QrLog(QrLogCreate):
    id: int
    status: str
    created_at: datetime


class QrLogResponse(BaseModel):
    log: QrLog
    message: str


class PredictionResult(BaseModel):
    equipment_id: str
    prediction: PredictionLabel
    risk_level: RiskLevel
    anomaly_score: float
    reasons: list[str]
    recommended_action: str
    predicted_at: datetime


class NotificationResult(BaseModel):
    popup_triggered: bool
    email_status: str
    email_to: str
    message: str


class UsageLog(CheckInCreate):
    id: int
    status: str
    prediction: PredictionLabel
    risk_level: RiskLevel
    anomaly_score: float
    reasons: list[str]
    created_at: datetime


class DashboardResponse(BaseModel):
    kpis: dict
    status_distribution: list[dict]
    utilization_by_type: list[dict]
    engine_idle_trend: list[dict]
    risk_distribution: list[dict]
    demand_forecast: list[dict]
    recent_alerts: list[dict]


class CheckInResponse(BaseModel):
    usage_log: UsageLog
    prediction_result: PredictionResult
    notification: NotificationResult
