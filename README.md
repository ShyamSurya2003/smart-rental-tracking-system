# Smart Rental Tracking System

Chart-first hackathon dashboard for equipment rental tracking, QR/check-in simulation, anomaly detection, alerts, usage logs, and demand forecasting.

## Run locally

```bash
npm run install:all
npm run dev
```

Frontend: http://localhost:5173

Backend: http://localhost:8000/docs

## Docker

```bash
docker compose up --build
```

Docker runs:

- PostgreSQL on `5432`
- FastAPI backend on `8001`
- React static frontend on `5199`

The backend uses PostgreSQL when `DATABASE_URL` is set. Without it, the app falls back to local SQLite for quick demos.

## Model result APIs

```text
GET /api/model-results
GET /api/model-metrics
GET /api/database-status
```

The dashboard reads improved anomaly model outputs from the database. On first backend startup, the database is seeded from:

```text
backend/app/ml/artifacts/improved_anomaly_results_test.csv
backend/app/ml/artifacts/improved_classification_metrics.csv
```

## Model integration

The live prediction endpoint is `POST /api/checkin`. It currently uses deterministic mock-model logic based on the 9 dataset columns:

- Equipment ID
- Type
- Site ID
- Check-In Date
- Check-Out Date
- Engine Hours/Day
- Idle Hours/Day
- Rental Days
- Last Operator ID

When the trained model is ready, place the pipeline/model file in `backend/app/ml/artifacts/` and replace the logic in `backend/app/ml/predictor.py`.
