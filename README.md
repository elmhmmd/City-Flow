# CityFlow

AI platform for scooter-sharing companies. Predicts scooter demand by zone and hour using historical trip data, weather conditions, and time features, then serves predictions through a secured REST API with a live React dashboard.

---

## Stack

| Layer | Technology |
|---|---|
| Data | Austin TX scooter trips 2018–2022 (~15M rows), Open-Meteo weather API |
| Models | LinearRegression, RandomForest, XGBoost, LinearSVR — tracked with MLflow |
| Backend | FastAPI, SQLAlchemy, JWT auth, Prometheus metrics |
| Frontend | React 19, Vite, Tailwind CSS, Leaflet, Recharts |
| Infrastructure | Docker Compose, Prometheus, Grafana |
| CI/CD | GitHub Actions — test on every push, build and push images to ghcr.io on master |

---

## Quick Start

### Prerequisites
- Docker Desktop

### Run everything

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:80 |
| API | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

Default credentials: `admin` / `admin`

---

## Project Structure

```
City_Flow/
├── etl.py                      # Cleans and aggregates raw trip + weather data
├── extract_weather_openmeteo.py # Fetches historical weather from Open-Meteo
├── models.py                   # Trains and registers ML models with MLflow
├── config.json                 # Thresholds, paths, API settings
├── api/
│   ├── main.py                 # FastAPI routes + Prometheus instrumentation
│   ├── auth.py                 # JWT access/refresh tokens, bcrypt
│   ├── predictor.py            # Loads MLflow model, assembles features
│   ├── schemas.py              # Pydantic request/response models
│   ├── models.py               # SQLAlchemy ORM (User, RefreshToken)
│   ├── database.py             # SQLite engine and session
│   └── dependencies.py         # DB session, JWT guard, role-based access
├── frontend/
│   └── src/pages/
│       ├── DemandMap.jsx       # Leaflet heatmap + time slider + weather popups
│       └── Performance.jsx     # MLflow metrics + actual vs predicted scatter
├── tests/                      # 15 pytest tests (auth + predictions)
├── monitoring/
│   ├── prometheus.yml          # Scrape config
│   └── grafana/                # Provisioned datasource + dashboard
├── Dockerfile.backend
├── Dockerfile.frontend
└── docker-compose.yml
```

---

## API Endpoints

All endpoints except `/api/v1/auth/login` require a `Bearer` token.

| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login` | public | Returns access + refresh tokens |
| POST | `/api/v1/auth/refresh` | public | Rotates tokens |
| GET | `/api/v1/predictions/demand` | any | Single zone demand prediction |
| POST | `/api/v1/predictions/batch` | any | Up to 500 predictions in one call |
| GET | `/api/v1/performance/actual-vs-predicted` | admin, manager | Sample of actual vs predicted trips |
| GET | `/api/v1/users/me` | any | Current user info |
| POST | `/api/v1/users` | admin | Create a new user |

Interactive docs at `/docs`.

---

## Running Tests

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

---

## Development

**Backend**
```bash
.venv/Scripts/uvicorn api.main:app --reload
```

**Frontend**
```bash
cd frontend && npm run dev
```

**MLflow UI**
```bash
.venv/Scripts/mlflow ui
```
