"""
Loads the best registered MLflow model and assembles features for inference.
Feature assembly mirrors the training pipeline in models.py.
"""

import json
import logging
from datetime import datetime, timedelta

import mlflow.pyfunc
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

DATASET_PATH = "data/processed/dataset_final.csv"
WEATHER_PATH = "data/raw/weather/weather_hourly.json"
REGISTRY_NAME = "cityflow_demand_best"

FEATURES = [
    "zone_start_enc", "vehicle_type_enc",
    "year", "month", "weekday", "hour", "is_weekend",
    "temperature_c", "precipitation_mm", "windspeed_kmh",
    "lag_1", "lag_24", "lag_168",
    "rolling_mean_24", "rolling_mean_168",
]


class Predictor:
    def __init__(self):
        self.model = None
        self.le_zone = LabelEncoder()
        self.le_vehicle = LabelEncoder()
        self.trip_lookup: dict = {}   # (zone, vehicle_type, timestamp_hour) -> trip_count
        self.zone_means: dict = {}    # (zone, vehicle_type) -> mean trip_count
        self.weather_lookup: dict = {}  # timestamp_hour -> {temperature_c, precipitation_mm, windspeed_kmh}
        self.rmse: float = 1.0

    def load(self):
        logger.info("Loading dataset for feature assembly...")
        df = pd.read_csv(DATASET_PATH, parse_dates=["timestamp_hour"])

        # Label encoders
        self.le_zone.fit(df["zone_start"].astype(str).unique())
        self.le_vehicle.fit(df["vehicle_type"].astype(str).unique())

        # Trip count lookup for lag features
        df["timestamp_hour"] = df["timestamp_hour"].dt.floor("h")
        for row in df.itertuples(index=False):
            key = (str(row.zone_start), str(row.vehicle_type), row.timestamp_hour)
            self.trip_lookup[key] = row.trip_count

        # Per-zone mean as fallback when lags are unavailable
        means = df.groupby(["zone_start", "vehicle_type"])["trip_count"].mean()
        for (zone, vtype), mean in means.items():
            self.zone_means[(str(zone), str(vtype))] = mean

        logger.info("Loading weather data...")
        with open(WEATHER_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        h = raw["hourly"]
        for ts, temp, prec, wind in zip(
            h["time"], h["temperature_2m"], h["precipitation"], h["windspeed_10m"]
        ):
            key = pd.Timestamp(ts).floor("h")
            self.weather_lookup[key] = {
                "temperature_c":    temp,
                "precipitation_mm": prec,
                "windspeed_kmh":    wind,
            }

        logger.info(f"Loading MLflow model '{REGISTRY_NAME}'...")
        self.model = mlflow.pyfunc.load_model(f"models:/{REGISTRY_NAME}/latest")
        logger.info("Predictor ready.")

    def _get_lag(self, zone: str, vtype: str, ts: pd.Timestamp, offset_hours: int) -> float:
        key = (zone, vtype, ts - timedelta(hours=offset_hours))
        if key in self.trip_lookup:
            return self.trip_lookup[key]
        return self.zone_means.get((zone, vtype), 1.0)

    def _get_rolling_mean(self, zone: str, vtype: str, ts: pd.Timestamp, window: int) -> float:
        values = [
            self.trip_lookup.get((zone, vtype, ts - timedelta(hours=i)), None)
            for i in range(1, window + 1)
        ]
        valid = [v for v in values if v is not None]
        if valid:
            return float(np.mean(valid))
        return self.zone_means.get((zone, vtype), 1.0)

    def predict(self, zone_id: str, timestamp: datetime, vehicle_type: str) -> tuple[float, float, float, dict]:
        ts = pd.Timestamp(timestamp).floor("h")
        zone = str(zone_id)
        vtype = str(vehicle_type)

        # Encode categoricals — unknown zones/vehicles fall back to 0
        try:
            zone_enc = int(self.le_zone.transform([zone])[0])
        except ValueError:
            zone_enc = 0
        try:
            vtype_enc = int(self.le_vehicle.transform([vtype])[0])
        except ValueError:
            vtype_enc = 0

        # Weather
        weather = self.weather_lookup.get(ts, {"temperature_c": 20.0, "precipitation_mm": 0.0, "windspeed_kmh": 10.0})

        # Lags
        lag_1   = self._get_lag(zone, vtype, ts, 1)
        lag_24  = self._get_lag(zone, vtype, ts, 24)
        lag_168 = self._get_lag(zone, vtype, ts, 168)
        roll_24  = self._get_rolling_mean(zone, vtype, ts, 24)
        roll_168 = self._get_rolling_mean(zone, vtype, ts, 168)

        features = pd.DataFrame([{
            "zone_start_enc":    zone_enc,
            "vehicle_type_enc":  vtype_enc,
            "year":              ts.year,
            "month":             ts.month,
            "weekday":           ts.weekday(),
            "hour":              ts.hour,
            "is_weekend":        int(ts.weekday() >= 5),
            "temperature_c":     weather["temperature_c"],
            "precipitation_mm":  weather["precipitation_mm"],
            "windspeed_kmh":     weather["windspeed_kmh"],
            "lag_1":             lag_1,
            "lag_24":            lag_24,
            "lag_168":           lag_168,
            "rolling_mean_24":   roll_24,
            "rolling_mean_168":  roll_168,
        }])[FEATURES]

        predicted = float(max(0.0, self.model.predict(features)[0]))
        lower = max(0.0, predicted - 1.96 * self.rmse)
        upper = predicted + 1.96 * self.rmse
        return predicted, lower, upper, weather


predictor = Predictor()
