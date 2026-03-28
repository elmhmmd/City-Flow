"""
Extraction des donnees meteo horaires via l'API Open-Meteo (archive historique).
Lit sa configuration depuis config.json.
Sortie : paths.weather_json
"""

import json
import os
import requests


BASE_URL  = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = "temperature_2m,precipitation,windspeed_10m"


def load_config(config_path: str = "config.json") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def fetch_weather_for_year(year: int, latitude: float, longitude: float) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": VARIABLES,
        "timezone": "America/Chicago",
    }
    response = requests.get(BASE_URL, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def merge_yearly_results(yearly_results: list[dict]) -> dict:
    merged = {
        "latitude": yearly_results[0]["latitude"],
        "longitude": yearly_results[0]["longitude"],
        "timezone": yearly_results[0]["timezone"],
        "hourly_units": yearly_results[0]["hourly_units"],
        "hourly": {
            "time": [],
            "temperature_2m": [],
            "precipitation": [],
            "windspeed_10m": [],
        },
    }
    for result in yearly_results:
        merged["hourly"]["time"].extend(result["hourly"]["time"])
        merged["hourly"]["temperature_2m"].extend(result["hourly"]["temperature_2m"])
        merged["hourly"]["precipitation"].extend(result["hourly"]["precipitation"])
        merged["hourly"]["windspeed_10m"].extend(result["hourly"]["windspeed_10m"])
    return merged


def main(config_path: str = "config.json"):
    cfg = load_config(config_path)
    lat        = cfg["weather"]["latitude"]
    lon        = cfg["weather"]["longitude"]
    start_year = int(cfg["weather"]["start_date"][:4])
    end_year   = int(cfg["weather"]["end_date"][:4])
    output     = cfg["paths"]["weather_json"]

    os.makedirs(os.path.dirname(output), exist_ok=True)

    years = list(range(start_year, end_year + 1))
    print(f"Extraction meteo ({start_year} -> {end_year})...")
    yearly_results = []
    for year in years:
        print(f"  Fetching {year}...", end=" ")
        data = fetch_weather_for_year(year, lat, lon)
        records = len(data["hourly"]["time"])
        print(f"{records} enregistrements horaires")
        yearly_results.append(data)

    print("Fusion des donnees...")
    merged = merge_yearly_results(yearly_results)
    total = len(merged["hourly"]["time"])

    with open(output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Sauvegarde : {output} ({total} enregistrements horaires)")


if __name__ == "__main__":
    main()
