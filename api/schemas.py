from datetime import datetime

from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Predictions ───────────────────────────────────────────────────────────────

class DemandRequest(BaseModel):
    zone_id:      str = Field(..., description="Census Tract FIPS code (e.g. 48453001100)")
    timestamp:    datetime = Field(..., description="Target datetime (ISO 8601)")
    vehicle_type: str = Field(default="scooter", description="Vehicle type: scooter, bicycle, moped")


class ConfidenceInterval(BaseModel):
    lower: float
    upper: float


class WeatherSnapshot(BaseModel):
    temperature_c:    float
    precipitation_mm: float
    windspeed_kmh:    float


class DemandResponse(BaseModel):
    zone_id:             str
    timestamp:           datetime
    vehicle_type:        str
    predicted_trips:     float
    confidence_interval: ConfidenceInterval
    weather:             WeatherSnapshot | None = None


class BatchRequest(BaseModel):
    predictions: list[DemandRequest] = Field(..., max_length=500)


class BatchResponse(BaseModel):
    predictions: list[DemandResponse]
    total:       int


# ── Users ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id:         int
    username:   str
    role:       str
    is_active:  bool
    created_at: datetime

    model_config = {"from_attributes": True}
