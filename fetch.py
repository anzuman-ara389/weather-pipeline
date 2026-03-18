import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Dict, List

import requests
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'weather.db'
DOCS_DIR = BASE_DIR / 'docs'
LOCATIONS_PATH = BASE_DIR / 'locations.json'

GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'

TARGET_DATE = date.today() + timedelta(days=1)
DAILY_VARS = [
    'temperature_2m_max',
    'precipitation_sum',
    'wind_speed_10m_max',
]


@dataclass
class Location:
    label: str
    query: str


class PipelineError(Exception):
    pass


def load_locations() -> List[Location]:
    if not LOCATIONS_PATH.exists():
        raise PipelineError(
            'locations.json is missing. Create it based on the example in the README.'
        )

    with open(LOCATIONS_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    locations = [Location(item['label'], item['query']) for item in raw['locations']]
    if len(locations) != 3:
        raise PipelineError('locations.json must contain exactly 3 locations.')
    return locations


def geocode_location(query: str) -> Dict:
    response = requests.get(
        GEOCODING_URL,
        params={'name': query, 'count': 1, 'language': 'en', 'format': 'json'},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    results = payload.get('results') or []
    if not results:
        raise PipelineError(f'Could not geocode location: {query}')
    return results[0]


def fetch_daily_forecast(lat: float, lon: float) -> Dict:
    response = requests.get(
        FORECAST_URL,
        params={
            'latitude': lat,
            'longitude': lon,
            'daily': ','.join(DAILY_VARS),
            'timezone': 'auto',
            'forecast_days': 2,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    daily = payload.get('daily', {})
    times = daily.get('time', [])
    if str(TARGET_DATE) not in times:
        raise PipelineError(f'No forecast found for {TARGET_DATE.isoformat()}')

    idx = times.index(str(TARGET_DATE))
    return {
        'forecast_date': daily['time'][idx],
        'temperature_2m_max': daily['temperature_2m_max'][idx],
        'precipitation_sum': daily['precipitation_sum'][idx],
        'wind_speed_10m_max': daily['wind_speed_10m_max'][idx],
        'timezone': payload.get('timezone'),
    }


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_timestamp TEXT NOT NULL,
                location_label TEXT NOT NULL,
                location_query TEXT NOT NULL,
                resolved_name TEXT NOT NULL,
                country TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timezone TEXT,
                forecast_date TEXT NOT NULL,
                temperature_2m_max REAL,
                precipitation_sum REAL,
                wind_speed_10m_max REAL
            )
            '''
        )
        conn.commit()


def save_forecast(row: Dict) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            '''
            INSERT INTO forecasts (
                run_timestamp,
                location_label,
                location_query,
                resolved_name,
                country,
                latitude,
                longitude,
                timezone,
                forecast_date,
                temperature_2m_max,
                precipitation_sum,
                wind_speed_10m_max
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                row['run_timestamp'],
                row['location_label'],
                row['location_query'],
                row['resolved_name'],
                row['country'],
                row['latitude'],
                row['longitude'],
                row['timezone'],
                row['forecast_date'],
                row['temperature_2m_max'],
                row['precipitation_sum'],
                row['wind_speed_10m_max'],
            ),
        )
        conn.commit()


def generate_poem(forecasts: List[Dict]) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise PipelineError('GROQ_API_KEY is not set.')

    client = Groq(api_key=api_key)

    weather_lines = []
    for item in forecasts:
        weather_lines.append(
            f"- {item['location_label']} ({item['resolved_name']}, {item['country']}): "
            f"max temp {item['temperature_2m_max']}°C, "
            f"precipitation {item['precipitation_sum']} mm, "
            f"max wind {item['wind_speed_10m_max']} km/h"
        )

    prompt = f"""
Write a short bilingual poem in exactly two clearly separated sections:
1) English
2) Bengali


The poem must:
- compare the weather in the three locations below
- describe the differences creatively but still grounded in the numbers
- say where it would be nicest to be tomorrow and why
- stay under 180 words total
- sound human and vivid

Forecast date: {TARGET_DATE.isoformat()}
Weather facts:
{chr(10).join(weather_lines)}
""".strip()

    completion = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are a poetic assistant. Be accurate with numbers and locations. '
                    'Do not invent weather facts.'
                ),
            },
            {'role': 'user', 'content': prompt},
        ],
        temperature=0.8,
    )

    return completion.choices[0].message.content.strip()


def build_html(forecasts: List[Dict], poem: str, generated_at: str) -> str:
    rows = '\n'.join(
        f"""
        <tr>
          <td>{item['location_label']}</td>
          <td>{item['resolved_name']}, {item['country']}</td>
          <td>{item['forecast_date']}</td>
          <td>{item['temperature_2m_max']} °C</td>
          <td>{item['precipitation_sum']} mm</td>
          <td>{item['wind_speed_10m_max']} km/h</td>
        </tr>
        """.strip()
        for item in forecasts
    )

    escaped_poem = (
        poem.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Automated Weather Poem</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f7fb; color: #1f2937; }}
    main {{ max-width: 900px; margin: 40px auto; background: white; padding: 32px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }}
    h1, h2 {{ margin-top: 0; }}
    .meta {{ color: #6b7280; margin-bottom: 24px; }}
    .poem {{ white-space: pre-wrap; background: #f9fafb; padding: 20px; border-radius: 12px; line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; text-align: left; padding: 12px; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #eef2ff; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <main>
    <h1>Automated Weather Pipeline</h1>
    <p class="meta">Generated at: {generated_at} UTC</p>

    <h2>Bilingual Weather Poem</h2>
    <div class="poem">{escaped_poem}</div>

    <h2>Forecast summary for tomorrow</h2>
    <table>
      <thead>
        <tr>
          <th>Label</th>
          <th>Resolved place</th>
          <th>Date</th>
          <th>Max temperature</th>
          <th>Precipitation</th>
          <th>Max wind</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>

    <p>This page is updated automatically by GitHub Actions and published with GitHub Pages.</p>
  </main>
</body>
</html>
"""


def write_outputs(forecasts: List[Dict], poem: str, generated_at: str) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    with open(DOCS_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(build_html(forecasts, poem, generated_at))

    with open(DOCS_DIR / 'data.json', 'w', encoding='utf-8') as f:
        json.dump(
            {
                'generated_at_utc': generated_at,
                'forecast_date': TARGET_DATE.isoformat(),
                'forecasts': forecasts,
                'poem': poem,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:
    locations = load_locations()
    init_db()

    run_timestamp = datetime.utcnow().replace(microsecond=0).isoformat()
    forecasts: List[Dict] = []

    for location in locations:
        geo = geocode_location(location.query)
        forecast = fetch_daily_forecast(geo['latitude'], geo['longitude'])
        row = {
            'run_timestamp': run_timestamp,
            'location_label': location.label,
            'location_query': location.query,
            'resolved_name': geo['name'],
            'country': geo.get('country', ''),
            'latitude': geo['latitude'],
            'longitude': geo['longitude'],
            **forecast,
        }
        save_forecast(row)
        forecasts.append(row)

    poem = generate_poem(forecasts)
    write_outputs(forecasts, poem, run_timestamp)
    print('Pipeline completed successfully.')


if __name__ == '__main__':
    main()
