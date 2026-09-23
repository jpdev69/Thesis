"""Shared Open-Meteo client for Echague, Isabela weather data.

Used by both the daily operational update script
(examples/daily_update.py) and the operational API (backend/daily_api.py),
so the two always fetch identical weather from identical endpoints.

Stdlib-only (urllib) so it can be imported from any context.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

LAT = 16.695957
LON = 121.7192
TIMEZONE = "Asia/Manila"
WEATHER_VARS = "temperature_2m_mean,relative_humidity_2m_mean,rain_sum"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/era5"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_json(url: str, retries: int = 3, backoff: float = 5.0) -> dict:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "EnergyAI-thesis-daily-update/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(f"  [!] Fetch attempt {attempt}/{retries} failed ({e}); retrying...")
                time.sleep(backoff)
    raise last_err


def parse_daily(payload: dict) -> dict:
    """Return {date_str: [temperature, humidity, rainfall]} (None if missing)."""
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    out = {}
    for i, t in enumerate(times):
        vals = []
        for var in ("temperature_2m_mean", "relative_humidity_2m_mean", "rain_sum"):
            arr = daily.get(var) or []
            vals.append(arr[i] if i < len(arr) else None)
        out[t] = vals
    return out


def fetch_archive_range(start: str, end: str) -> dict:
    """Observed ERA5 archive days between start and end (ISO dates)."""
    url = (
        f"{ARCHIVE_URL}?latitude={LAT}&longitude={LON}"
        f"&start_date={start}&end_date={end}"
        f"&daily={WEATHER_VARS}&timezone={urllib.parse.quote(TIMEZONE)}"
    )
    return parse_daily(fetch_json(url))


def fetch_forecast_blend(past_days: int, forecast_days: int) -> dict:
    """One call returning recent actual days plus the forecast horizon."""
    url = (
        f"{FORECAST_URL}?latitude={LAT}&longitude={LON}"
        f"&daily={WEATHER_VARS}&past_days={past_days}&forecast_days={forecast_days}"
        f"&timezone={urllib.parse.quote(TIMEZONE)}"
    )
    return parse_daily(fetch_json(url))
