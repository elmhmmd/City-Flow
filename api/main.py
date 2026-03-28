from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from api.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
    decode_token,
)
from api.database import init_db
from api.dependencies import get_db, get_current_user, require_roles
from api.models import RefreshToken, User
from api.predictor import predictor
from api.schemas import (
    BatchRequest,
    BatchResponse,
    ConfidenceInterval,
    DemandRequest,
    DemandResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
    WeatherSnapshot,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_admin()
    predictor.load()
    yield


def _seed_admin():
    """Create a default admin user if none exists."""
    from api.database import SessionLocal
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(
                username="admin",
                hashed_password=hash_password("admin"),
                role="admin",
            ))
            db.commit()
    finally:
        db.close()


app = FastAPI(
    title="CityFlow API",
    description="Scooter demand forecasting API",
    version="1.0.0",
    lifespan=lifespan,
)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username, User.is_active == True).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token({"sub": user.username, "role": user.role})
    refresh_token, expires_at = create_refresh_token({"sub": user.username, "role": user.role})

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    ))
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@app.post("/api/v1/auth/refresh", response_model=TokenResponse, tags=["Auth"])
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        username = payload.get("sub")
        role     = payload.get("role")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    token_hash = hash_token(body.refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked or expired")

    stored.revoked = True
    new_access = create_access_token({"sub": username, "role": role})
    new_refresh, expires_at = create_refresh_token({"sub": username, "role": role})
    db.add(RefreshToken(user_id=stored.user_id, token_hash=hash_token(new_refresh), expires_at=expires_at))
    db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


# ── Predictions ───────────────────────────────────────────────────────────────

def _make_prediction(req: DemandRequest) -> DemandResponse:
    predicted, lower, upper, weather = predictor.predict(req.zone_id, req.timestamp, req.vehicle_type)
    return DemandResponse(
        zone_id=req.zone_id,
        timestamp=req.timestamp,
        vehicle_type=req.vehicle_type,
        predicted_trips=round(predicted, 2),
        confidence_interval=ConfidenceInterval(lower=round(lower, 2), upper=round(upper, 2)),
        weather=WeatherSnapshot(**weather),
    )


@app.get("/api/v1/predictions/demand", response_model=DemandResponse, tags=["Predictions"])
def predict_demand(
    zone_id: str,
    timestamp: datetime,
    vehicle_type: str = "scooter",
    _: User = Depends(require_roles("admin", "manager", "api_client")),
):
    return _make_prediction(DemandRequest(zone_id=zone_id, timestamp=timestamp, vehicle_type=vehicle_type))


@app.post("/api/v1/predictions/batch", response_model=BatchResponse, tags=["Predictions"])
def predict_batch(
    body: BatchRequest,
    _: User = Depends(require_roles("admin", "manager", "api_client")),
):
    results = [_make_prediction(req) for req in body.predictions]
    return BatchResponse(predictions=results, total=len(results))


# ── Performance ──────────────────────────────────────────────────────────────

@app.get("/api/v1/performance/actual-vs-predicted", tags=["Performance"])
def actual_vs_predicted(
    n: int = 200,
    _: User = Depends(require_roles("admin", "manager")),
):
    import pandas as pd
    import numpy as np

    df = pd.read_csv("data/processed/dataset_final.csv", parse_dates=["timestamp_hour"])
    sample = df.sample(min(n, len(df)), random_state=42).reset_index(drop=True)

    results = []
    for row in sample.itertuples(index=False):
        try:
            pred, _, _, _ = predictor.predict(
                str(row.zone_start), row.timestamp_hour, str(row.vehicle_type)
            )
            results.append({
                "timestamp": row.timestamp_hour.isoformat(),
                "actual":    float(row.trip_count),
                "predicted": round(pred, 2),
            })
        except Exception:
            continue

    return {"data": results, "total": len(results)}


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/users/me", response_model=UserOut, tags=["Users"])
def me(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/api/v1/users", response_model=UserOut, tags=["Users"])
def create_user(
    username: str,
    password: str,
    role: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    if role not in ("admin", "manager", "api_client"):
        raise HTTPException(status_code=400, detail="Invalid role")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(username=username, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
