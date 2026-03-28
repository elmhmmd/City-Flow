"""
ETL script for CityFlow.
Reads config.json, cleans and aggregates the raw trip CSV,
joins weather data, and writes the final dataset to data/processed/.
"""

import json
import logging
import os
from datetime import datetime

import pandas as pd


DTYPE_OVERRIDES = {
    'Census Tract Start': str,
    'Census Tract End':   str,
}

USECOLS = [
    'ID',
    'Vehicle Type',
    'Trip Duration',
    'Trip Distance',
    'Start Time (US/Central)',
    'Census Tract Start',
]

CHUNK_SIZE = 500_000


def load_config(path='config.json'):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def setup_logging(logs_dir):
    os.makedirs(logs_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(logs_dir, f'etl_{ts}.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )
    return log_path


def load_weather(weather_json_path):
    with open(weather_json_path, encoding='utf-8') as f:
        raw = json.load(f)
    h = raw['hourly']
    df = pd.DataFrame({
        'timestamp_hour':   pd.to_datetime(h['time']),
        'temperature_c':    h['temperature_2m'],
        'precipitation_mm': h['precipitation'],
        'windspeed_kmh':    h['windspeed_10m'],
    })
    df['timestamp_hour'] = df['timestamp_hour'].dt.floor('h')
    return df.set_index('timestamp_hour')


def clean_chunk(chunk, cfg):
    c = cfg['cleaning']
    initial = len(chunk)

    chunk = chunk.dropna(subset=['Start Time (US/Central)', 'Census Tract Start'])

    chunk['Census Tract Start'] = (
        chunk['Census Tract Start']
        .str.replace(r'\.0$', '', regex=True)
        .str.strip()
    )

    chunk['timestamp_hour'] = pd.to_datetime(
        chunk['Start Time (US/Central)'], errors='coerce'
    ).dt.floor('h')

    chunk = chunk.dropna(subset=['timestamp_hour'])
    chunk = chunk[chunk['timestamp_hour'].dt.year != 1970]

    chunk = chunk[
        (chunk['Trip Duration'] >= c['min_trip_duration_s']) &
        (chunk['Trip Duration'] <= c['max_trip_duration_s']) &
        (chunk['Trip Distance'] >= c['min_trip_distance_m']) &
        (chunk['Trip Distance'] <= c['max_trip_distance_m'])
    ]

    return chunk, initial - len(chunk)


def aggregate_chunk(chunk):
    return (
        chunk
        .groupby(['timestamp_hour', 'Census Tract Start', 'Vehicle Type'])
        .agg(
            trip_count=('ID', 'count'),
            dur_sum=('Trip Duration', 'sum'),
            dist_sum=('Trip Distance', 'sum'),
        )
        .reset_index()
    )


def main(config_path='config.json'):
    cfg = load_config(config_path)
    setup_logging(cfg['paths']['logs_dir'])
    logging.info('ETL started')

    logging.info('Loading weather data...')
    weather_df = load_weather(cfg['paths']['weather_json'])
    logging.info(f'Weather loaded: {len(weather_df):,} hourly records')

    partial_aggs = []
    total_rows = 0
    total_dropped = 0

    logging.info(f'Processing trips: {cfg["paths"]["trips_csv"]}')
    for i, chunk in enumerate(pd.read_csv(
        cfg['paths']['trips_csv'],
        chunksize=CHUNK_SIZE,
        dtype=DTYPE_OVERRIDES,
        usecols=USECOLS,
    )):
        chunk, dropped = clean_chunk(chunk, cfg)
        total_rows += len(chunk)
        total_dropped += dropped
        partial_aggs.append(aggregate_chunk(chunk))
        if (i + 1) % 5 == 0:
            logging.info(f'  {(i + 1) * CHUNK_SIZE:,} rows processed...')

    logging.info(f'Cleaning done — kept {total_rows:,}, dropped {total_dropped:,}')

    logging.info('Combining partial aggregations...')
    combined = pd.concat(partial_aggs, ignore_index=True)
    del partial_aggs

    final = (
        combined
        .groupby(['timestamp_hour', 'Census Tract Start', 'Vehicle Type'], as_index=False)
        .agg(trip_count=('trip_count', 'sum'), dur_sum=('dur_sum', 'sum'), dist_sum=('dist_sum', 'sum'))
    )
    del combined

    final['avg_trip_duration_s'] = (final['dur_sum'] / final['trip_count']).round(2)
    final['avg_trip_distance_m'] = (final['dist_sum'] / final['trip_count']).round(2)
    final = final.drop(columns=['dur_sum', 'dist_sum'])

    final = final.rename(columns={
        'Census Tract Start': 'zone_start',
        'Vehicle Type':       'vehicle_type',
    })

    ts = final['timestamp_hour']
    final['year']       = ts.dt.year
    final['month']      = ts.dt.month
    final['weekday']    = ts.dt.weekday
    final['hour']       = ts.dt.hour
    final['is_weekend'] = (ts.dt.weekday >= 5).astype(int)

    logging.info('Joining weather...')
    final = final.join(weather_df, on='timestamp_hour', how='left')
    missing_weather = int(final['temperature_c'].isna().sum())
    if missing_weather > 0:
        logging.warning(f'{missing_weather} rows have no weather match')

    out_path = cfg['paths']['output_csv']
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    final.to_csv(out_path, index=False, encoding='utf-8')
    logging.info(f'Saved {len(final):,} rows → {out_path}')

    report = {
        'timestamp':            datetime.now().isoformat(),
        'rows_kept':            total_rows,
        'rows_dropped':         total_dropped,
        'aggregated_rows':      len(final),
        'zones':                int(final['zone_start'].nunique()),
        'vehicle_types':        final['vehicle_type'].value_counts().to_dict(),
        'date_range':           [str(final['timestamp_hour'].min()), str(final['timestamp_hour'].max())],
        'missing_weather_rows': missing_weather,
    }
    report_path = cfg['paths']['output_report']
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logging.info(f'Quality report → {report_path}')
    logging.info('ETL complete')


if __name__ == '__main__':
    main()
