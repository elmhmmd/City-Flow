"""
Demand forecasting models for CityFlow.
Trains LinearRegression, RandomForest, XGBoost, and LinearSVR,
logs everything to MLflow, and registers the best model.
"""

import json
import logging
import os
import warnings

import mlflow
import mlflow.sklearn
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVR
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

DATASET_PATH  = "data/processed/dataset_final.csv"
EXPERIMENT    = "cityflow_demand"
REGISTRY_NAME = "cityflow_demand_best"
TEST_RATIO    = 0.2
RANDOM_STATE  = 42

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ── Feature engineering ───────────────────────────────────────────────────────

def add_lag_features(df):
    logging.info("Computing lag features...")
    df = df.sort_values(["zone_start", "vehicle_type", "timestamp_hour"]).reset_index(drop=True)
    grp = df.groupby(["zone_start", "vehicle_type"])["trip_count"]

    df["lag_1"]           = grp.shift(1)
    df["lag_24"]          = grp.shift(24)
    df["lag_168"]         = grp.shift(168)
    df["rolling_mean_24"] = grp.shift(1).transform(lambda x: x.rolling(24,  min_periods=1).mean())
    df["rolling_mean_168"]= grp.shift(1).transform(lambda x: x.rolling(168, min_periods=1).mean())

    before = len(df)
    df = df.dropna(subset=["lag_1", "lag_24", "lag_168"])
    logging.info(f"Dropped {before - len(df):,} rows with missing lags — {len(df):,} remaining")
    return df


def encode_categoricals(df):
    le_zone    = LabelEncoder()
    le_vehicle = LabelEncoder()
    df["zone_start_enc"]    = le_zone.fit_transform(df["zone_start"].astype(str))
    df["vehicle_type_enc"]  = le_vehicle.fit_transform(df["vehicle_type"].astype(str))
    return df, le_zone, le_vehicle


FEATURES = [
    "zone_start_enc", "vehicle_type_enc",
    "year", "month", "weekday", "hour", "is_weekend",
    "temperature_c", "precipitation_mm", "windspeed_kmh",
    "lag_1", "lag_24", "lag_168",
    "rolling_mean_24", "rolling_mean_168",
]
TARGET = "trip_count"


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(y_true, y_pred):
    mae   = mean_absolute_error(y_true, y_pred)
    rmse  = np.sqrt(mean_squared_error(y_true, y_pred))
    r2    = r2_score(y_true, y_pred)

    # MAPE — skip zeros to avoid division by zero
    mask  = y_true > 0
    mape  = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

    # RMSLE — clip negative predictions
    y_pred_clipped = np.clip(y_pred, 0, None)
    rmsle = np.sqrt(mean_squared_error(np.log1p(y_true), np.log1p(y_pred_clipped)))

    return {"MAE": mae, "RMSE": rmse, "R2": r2, "MAPE": mape, "RMSLE": rmsle}


# ── Training ──────────────────────────────────────────────────────────────────

MODELS = {
    "LinearRegression": (
        LinearRegression(),
        {},
    ),
    "RandomForest": (
        RandomForestRegressor(n_estimators=50, max_depth=15, n_jobs=-1, random_state=RANDOM_STATE),
        {"n_estimators": 50, "max_depth": 15, "random_state": RANDOM_STATE},
    ),
    "XGBoost": (
        XGBRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        ),
        {"n_estimators": 300, "learning_rate": 0.05, "max_depth": 6},
    ),
    # LinearSVR: kernel SVM is O(n²) — LinearSVR scales linearly and is feasible at this scale
    "LinearSVR": (
        LinearSVR(max_iter=500, random_state=RANDOM_STATE),
        {"max_iter": 500},
    ),
}


def train_and_evaluate(name, model, params, X_train, y_train, X_test, y_test):
    logging.info(f"Training {name}...")
    with mlflow.start_run(run_name=name):
        mlflow.log_params(params)

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        metrics = compute_metrics(y_test.values, y_pred)
        mlflow.log_metrics(metrics)

        if name == "XGBoost":
            mlflow.xgboost.log_model(model, artifact_path="model")
        else:
            mlflow.sklearn.log_model(model, artifact_path="model")

        run_id = mlflow.active_run().info.run_id
        logging.info(
            f"  {name} — RMSE={metrics['RMSE']:.4f}  MAE={metrics['MAE']:.4f}  "
            f"R²={metrics['R2']:.4f}  MAPE={metrics['MAPE']:.2f}%  RMSLE={metrics['RMSLE']:.4f}"
        )
        return run_id, metrics, model


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load
    logging.info("Loading dataset...")
    df = pd.read_csv(DATASET_PATH, parse_dates=["timestamp_hour"])
    logging.info(f"Loaded {len(df):,} rows")

    # Feature engineering
    df = add_lag_features(df)
    df, _, _ = encode_categoricals(df)

    # Chronological train/test split
    timestamps = df["timestamp_hour"].sort_values().unique()
    split_ts   = timestamps[int(len(timestamps) * (1 - TEST_RATIO))]
    train_df   = df[df["timestamp_hour"] < split_ts]
    test_df    = df[df["timestamp_hour"] >= split_ts]
    logging.info(f"Train: {len(train_df):,} rows | Test: {len(test_df):,} rows | Split at {split_ts}")

    X_train, y_train = train_df[FEATURES], train_df[TARGET]
    X_test,  y_test  = test_df[FEATURES],  test_df[TARGET]

    # MLflow
    mlflow.set_experiment(EXPERIMENT)

    results = {}
    for name, (model, params) in MODELS.items():
        run_id, metrics, trained_model = train_and_evaluate(
            name, model, params, X_train, y_train, X_test, y_test
        )
        results[name] = {"run_id": run_id, "metrics": metrics, "model": trained_model}

    # Best model by RMSE
    best_name = min(results, key=lambda n: results[n]["metrics"]["RMSE"])
    best      = results[best_name]
    logging.info(f"\nBest model: {best_name} (RMSE={best['metrics']['RMSE']:.4f})")

    # Register best model
    model_uri = f"runs:/{best['run_id']}/model"
    mlflow.register_model(model_uri=model_uri, name=REGISTRY_NAME)
    logging.info(f"Registered '{REGISTRY_NAME}' from run {best['run_id']}")

    # Summary
    print("\n── Results ──────────────────────────────────────────")
    for name, r in sorted(results.items(), key=lambda x: x[1]["metrics"]["RMSE"]):
        m = r["metrics"]
        print(
            f"{name:<20} RMSE={m['RMSE']:.4f}  MAE={m['MAE']:.4f}  "
            f"R²={m['R2']:.4f}  MAPE={m['MAPE']:.2f}%  RMSLE={m['RMSLE']:.4f}"
        )
    print(f"\n★ Best: {best_name}")


if __name__ == "__main__":
    main()
