"""Daily operational update for the EnergyAI campus forecasting system.

Single-script continuous-learning workflow. Run once per day:

1. Bill anchoring (monthly, when available):
   Re-reads the ISELCO billing workbook (per-building monthly bills) when
   its content changed and re-runs the preprocessing pipeline
   (clean_account_month.csv, campus_month_aggregate.csv, feature table,
   data quality report).
2. Weather update (daily):
   Fetches new observed days from the Open-Meteo ERA5 archive
   (Echague, Isabela) with automatic fallback to Open-Meteo forecast-API
   actuals for the most recent days (ERA5 publication lag), and merges
   them into data/external/echague_weather_daily.json.
3. Dataset rebuild:
   - data/daily_canonical_dataset.csv: anchored days only (bill-anchored,
     thesis-grade; changes only when new bills arrive).
   - data/daily_ops_dataset.csv: anchored days + provisional days for the
     current unbilled month (shape-model estimates, IsDisaggregated=0).
4. Retraining (auto):
   Retrains the hybrid LSTM-SVM on anchored days only when the set of
   anchored monthly bills changed or the operational model is missing.
5. 7-day forecast:
   Recursive hybrid forecast using the live Open-Meteo 7-day weather
   forecast and the proxy academic calendar, with cost translation,
   anomaly flags, and peak analysis.

Usage:
    python examples/daily_update.py
    python examples/daily_update.py --xlsx C:\\path\\ISUE_ISELCO_Monitoring.xlsx
    python examples/daily_update.py --retrain never --no-forecast

Outputs:
    models/ops/daily/                          trained operational model
    models/ops/state.json                      run state (fingerprints, metrics)
    data/processed/ops/latest_forecast.json
    data/processed/ops/forecast_<YYYYMMDD>.csv
    data/processed/ops/update_log.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.data.build_daily_canonical import (
    SOURCE_SCHEDULE,
    SOURCE_WEATHER,
    build_calendar,
    disaggregate,
    assemble,
    fit_monthly_shape,
    has_classes_on,
    load_monthly,
    load_weather,
    write_qa_report,
)
from src.data.preprocess_iselco_dataset import _render_report, run_pipeline
from src.models.daily_prediction_model import DailyEnergyPredictor, HAS_TF

LAT = 16.695957
LON = 121.7192
TIMEZONE = "Asia/Manila"
WEATHER_VARS = "temperature_2m_mean,relative_humidity_2m_mean,rain_sum"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/era5"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
COST_PER_KWH = 12.383
PROVISIONAL_SOURCE = "provisional_unanchored"
RECENT_MONTHS_FOR_SCALE = 6

OPS_DIR = ROOT / "models" / "ops"
MODEL_DIR = OPS_DIR / "daily"
STATE_PATH = OPS_DIR / "state.json"
WEATHER_STORE = ROOT / "data" / "external" / "echague_weather_daily.json"
MONTHLY_CSV = ROOT / "data" / "processed" / "campus_month_aggregate.csv"
CANONICAL_CSV = ROOT / "data" / "daily_canonical_dataset.csv"
OPS_CSV = ROOT / "data" / "daily_ops_dataset.csv"
QA_REPORT = ROOT / "docs" / "daily_data_quality_report.md"
OPS_OUT = ROOT / "data" / "processed" / "ops"
UPDATE_LOG = OPS_OUT / "update_log.jsonl"

WORKBOOK_NAME = "ISUE_ISELCO_Monitoring.xlsx"


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] Could not read state file ({e}); starting fresh")
    return {}


def _save_state(state: dict) -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _append_log(entry: dict) -> None:
    OPS_OUT.mkdir(parents=True, exist_ok=True)
    with open(UPDATE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ----------------------------------------------------------------------------
# Open-Meteo fetching
# ----------------------------------------------------------------------------

def _fetch_json(url: str, retries: int = 3, backoff: float = 5.0) -> dict:
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


def _parse_daily(payload: dict) -> dict:
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
    url = (
        f"{ARCHIVE_URL}?latitude={LAT}&longitude={LON}"
        f"&start_date={start}&end_date={end}"
        f"&daily={WEATHER_VARS}&timezone={urllib.parse.quote(TIMEZONE)}"
    )
    return _parse_daily(_fetch_json(url))


def fetch_forecast_blend(past_days: int, forecast_days: int) -> dict:
    """One call returning recent actual days plus the forecast horizon."""
    url = (
        f"{FORECAST_URL}?latitude={LAT}&longitude={LON}"
        f"&daily={WEATHER_VARS}&past_days={past_days}&forecast_days={forecast_days}"
        f"&timezone={urllib.parse.quote(TIMEZONE)}"
    )
    return _parse_daily(_fetch_json(url))


def update_weather_store(store_path: Path, target_date: date, max_backfill: int) -> dict:
    """Merge newly observed days (through target_date) into the weather store.

    Prefers ERA5 archive values (consistent with the thesis dataset); days the
    archive has not published yet are filled from forecast-API actuals. Days
    with no value anywhere are stored as nulls and interpolated at build time.
    """
    with open(store_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    daily = payload["daily"]
    times = list(daily["time"])
    last = datetime.strptime(times[-1], "%Y-%m-%d").date()

    report = {"store_last": last.isoformat(), "added": [], "fallback_days": []}
    gap_start, gap_end = last + timedelta(days=1), target_date
    if gap_start > gap_end:
        print(f"  Weather store already up to date (through {target_date.isoformat()}).")
        return report

    gap_start = max(gap_start, gap_end - timedelta(days=max_backfill))
    dates_needed = [
        (gap_start + timedelta(days=i)).isoformat()
        for i in range((gap_end - gap_start).days + 1)
    ]

    archive = {}
    try:
        archive = fetch_archive_range(dates_needed[0], dates_needed[-1])
        print(f"  ERA5 archive: {len(archive)} day(s) returned for the gap")
    except Exception as e:
        print(f"  [!] ERA5 archive fetch failed ({e}); using forecast actuals only")

    need_blend = not archive or any(
        any(v is None for v in vals) for vals in archive.values()
    )
    blend = {}
    if need_blend:
        try:
            past_days = min(len(dates_needed) + 7, 92)
            blend = fetch_forecast_blend(past_days=past_days, forecast_days=1)
        except Exception as e:
            print(f"  [!] Forecast-API blend fetch failed ({e})")

    n_null = 0
    for ds in dates_needed:
        a = archive.get(ds)
        if a is not None and all(v is not None for v in a):
            vals = a
        else:
            b = blend.get(ds)
            if b is not None and all(v is not None for v in b):
                vals = b
                report["fallback_days"].append(ds)
            else:
                vals = [None, None, None]
                n_null += 1
        times.append(ds)
        for var, v in zip(
            ("temperature_2m_mean", "relative_humidity_2m_mean", "rain_sum"), vals
        ):
            daily[var].append(v)
        report["added"].append(ds)

    daily["time"] = times
    payload["daily"] = daily
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    print(
        f"  Weather store updated: {len(report['added'])} day(s) added "
        f"({len(report['fallback_days'])} from forecast actuals, "
        f"{n_null} stored as null for interpolation)"
    )
    return report


# ----------------------------------------------------------------------------
# bills (monthly anchoring)
# ----------------------------------------------------------------------------

def resolve_workbook(args, state: dict) -> Path | None:
    if args.xlsx:
        return Path(args.xlsx)
    remembered = state.get("workbook_path")
    if remembered and Path(remembered).exists():
        return Path(remembered)
    for cand in (
        ROOT.parent / WORKBOOK_NAME,
        ROOT / WORKBOOK_NAME,
        ROOT / "data" / "external" / WORKBOOK_NAME,
    ):
        if cand.exists():
            return cand
    return None


def process_bills(args, state: dict) -> bool:
    """Re-run the ISELCO preprocessing pipeline when the workbook changed.

    Returns True if the monthly aggregates were reprocessed this run.
    """
    _print_header("STEP 1: MONTHLY BILL ANCHORING (ISELCO workbook)")

    if args.no_bills:
        print("  Skipped (--no-bills).")
        return False

    workbook = resolve_workbook(args, state)
    if workbook is None:
        print(
            "  [!] Billing workbook not found. Pass --xlsx <path> once; it will\n"
            "      be remembered in models/ops/state.json. Continuing with the\n"
            "      existing data/processed/campus_month_aggregate.csv."
        )
        return False
    if not workbook.exists():
        print(f"  [!] Workbook not found at {workbook}; continuing with existing data.")
        return False

    state["workbook_path"] = str(workbook)
    fingerprint = _file_md5(workbook)
    if (
        state.get("workbook_md5") == fingerprint
        and MONTHLY_CSV.exists()
        and not args.force_bills
    ):
        print("  Workbook unchanged since last run; skipping reprocessing.")
        return False

    print(f"  Workbook changed (or first run): {workbook}")
    print("  Re-running preprocessing pipeline...")
    artifacts = run_pipeline(workbook, ROOT / "data" / "processed")

    out_dir = ROOT / "data" / "processed"
    artifacts.clean_account_month.to_csv(out_dir / "clean_account_month.csv", index=False)
    artifacts.campus_month_aggregate.to_csv(MONTHLY_CSV, index=False)
    artifacts.feature_table_monthly.to_csv(out_dir / "feature_table_monthly.csv", index=False)
    (ROOT / "docs" / "data_quality_report.md").write_text(
        _render_report(artifacts.stats, out_dir), encoding="utf-8"
    )
    state["workbook_md5"] = fingerprint
    print("  Monthly aggregates refreshed (clean_account_month / campus_month_aggregate).")
    return True


def anchored_signature() -> tuple[str, list[str]]:
    """Stable signature of the currently anchored monthly bills."""
    monthly = pd.read_csv(MONTHLY_CSV, parse_dates=["period"])
    monthly = monthly.dropna(subset=["total_kwh_clean"])
    monthly = monthly[monthly["active_meter_count"] > 0]
    monthly = monthly.sort_values("period")
    parts, months = [], []
    for row in monthly.itertuples():
        parts.append(f"{row.period.strftime('%Y-%m')}|{int(row.active_meter_count)}|{round(float(row.total_kwh_clean), 3)}")
        months.append(row.period.strftime("%Y-%m"))
    sig = hashlib.md5(";".join(parts).encode("utf-8")).hexdigest()
    return sig, months


# ----------------------------------------------------------------------------
# dataset rebuild (anchored canonical + provisional ops extension)
# ----------------------------------------------------------------------------

def rebuild_datasets(today: date) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Rebuild the anchored canonical dataset and the ops dataset.

    Returns (anchored, ops, info).
    """
    _print_header("STEP 3: DATASET REBUILD (anchored + provisional)")

    monthly = load_monthly(MONTHLY_CSV)
    monthly = monthly[monthly["period"] <= pd.Timestamp(today)]
    weather = load_weather(WEATHER_STORE)

    first = monthly["period"].min().to_pydatetime().replace(day=1, hour=0, minute=0, second=0)
    last = (monthly["period"].max() + pd.offsets.MonthEnd(0)).to_pydatetime()
    yesterday = today - timedelta(days=1)
    anchor_end = min(last.date(), yesterday)
    if last.date() > yesterday:
        print(
            f"  [!] Latest billed month ends {last.date()} but data runs to "
            f"{yesterday}; anchoring through {anchor_end} only. The remaining "
            "days of that month will be included on later runs."
        )

    w_anchored = weather[
        (weather.index >= pd.Timestamp(first)) & (weather.index <= pd.Timestamp(anchor_end))
    ]
    calendar = build_calendar(pd.Series(w_anchored.index))
    daily = w_anchored.join(calendar)
    missing_cal = daily["HasClasses"].isna().sum()
    if missing_cal:
        raise ValueError(f"Calendar gaps for {missing_cal} days")

    params = fit_monthly_shape(monthly, daily)
    print("  Shape-model parameters refit on anchored months:")
    for k in ("base_load", "mu_class", "mu_noclass", "gamma", "r2_monthly"):
        print(f"    {k}: {params[k]:.4f}")

    daily = disaggregate(monthly, daily, params)

    monthly["MonthKey"] = list(zip(monthly["year"], monthly["month"]))
    shape_sums = daily.groupby("MonthKey")["DailyShape"].sum()
    m_adj = dict(zip(monthly["MonthKey"], monthly["monthly_total_adj"]))
    m_billed = dict(zip(monthly["MonthKey"], monthly["monthly_total_billed"]))
    recent_keys = [k for k in sorted(shape_sums.index) if k in m_adj][
        -RECENT_MONTHS_FOR_SCALE:
    ]
    scale_adj = float(np.median([m_adj[k] / shape_sums[k] for k in recent_keys]))
    scale_billed = float(np.median([m_billed[k] / shape_sums[k] for k in recent_keys]))

    anchored = assemble(daily, monthly)

    # --- provisional (unanchored) days beyond the last billed month ----------
    prov_dates = pd.date_range(
        pd.Timestamp(anchor_end) + pd.Timedelta(days=1), pd.Timestamp(yesterday), freq="D"
    )
    prov = pd.DataFrame(index=prov_dates, columns=anchored.columns)
    if len(prov_dates) > 0:
        cal_p = build_calendar(pd.Series(prov_dates))
        wx_p = weather.reindex(prov_dates)
        for col in ("Temperature", "Humidity", "Rainfall"):
            raw = wx_p[col]
            prov[f"IsImputed{col}"] = raw.isna().astype(int).to_numpy()
            prov[col] = raw.ffill().bfill().to_numpy()

        prov["DayOfWeek"] = cal_p["DayOfWeek"].to_numpy()
        prov["IsWeekend"] = cal_p["IsWeekend"].to_numpy()
        prov["IsHoliday"] = cal_p["IsHoliday"].to_numpy()
        prov["HasClasses"] = cal_p["HasClasses"].to_numpy()

        b, mu_c, mu_n = params["base_load"], params["mu_class"], params["mu_noclass"]
        gamma = params["gamma"]
        month_mean_t = weather.groupby([weather.index.year, weather.index.month])[
            "Temperature"
        ].mean()
        month_days = weather.groupby([weather.index.year, weather.index.month])[
            "Temperature"
        ].size()

        shapes = []
        for ts in prov_dates:
            key = (ts.year, ts.month)
            cls = int(cal_p.loc[ts, "HasClasses"])
            t = prov.loc[ts, "Temperature"]
            s = (
                b / month_days[key]
                + mu_c * cls
                + mu_n * (1 - cls)
                + gamma * (float(t) - float(month_mean_t[key]))
            )
            shapes.append(max(float(s), 1e-3))
        prov["DailyShape"] = shapes
        prov["Consumption"] = [s * scale_adj for s in shapes]
        prov["ConsumptionBilled"] = [s * scale_billed for s in shapes]
        prov["ActiveMeterCount"] = np.nan
        prov["CoverageRatio"] = np.nan
        prov["MonthlyTotalBilled"] = np.nan
        prov["MonthlyTotalAdj"] = np.nan
        prov["SourceConsumption"] = PROVISIONAL_SOURCE
        prov["SourceWeather"] = SOURCE_WEATHER
        prov["SourceSchedule"] = SOURCE_SCHEDULE
        prov["IsDisaggregated"] = 0

    ops = pd.concat([anchored, prov])
    ops.index.name = "Date"

    anchored.index.name = "Date"
    anchored.to_csv(CANONICAL_CSV, index=True)
    ops.to_csv(OPS_CSV, index=True)
    write_qa_report(anchored, params, monthly, QA_REPORT)

    info = {
        "anchored_days": int(len(anchored)),
        "provisional_days": int(len(prov_dates)),
        "anchored_through": str(anchored.index.max().date()),
        "ops_through": str(ops.index.max().date()),
        "scale_adj": scale_adj,
        "scale_billed": scale_billed,
    }
    print(
        f"  Anchored days: {info['anchored_days']} (through {info['anchored_through']})"
    )
    print(
        f"  Provisional days: {info['provisional_days']} (through {info['ops_through']})"
    )
    print(f"  Wrote {CANONICAL_CSV.name} (anchored only) and {OPS_CSV.name} (ops series)")
    return anchored, ops, info


# ----------------------------------------------------------------------------
# training
# ----------------------------------------------------------------------------

def _arrays_from(df: pd.DataFrame) -> dict:
    return {
        "consumption": df["Consumption"].to_numpy(float),
        "temperature": df["Temperature"].to_numpy(float),
        "humidity": df["Humidity"].to_numpy(float),
        "rainfall": df["Rainfall"].to_numpy(float),
        "has_classes": df["HasClasses"].to_numpy(int),
        "day_of_week": df["DayOfWeek"].to_numpy(int),
        "is_weekend": df["IsWeekend"].to_numpy(int),
    }


def train_ops_model(ops: pd.DataFrame, epochs: int) -> tuple[DailyEnergyPredictor, dict]:
    np.random.seed(42)
    if HAS_TF:
        import tensorflow as tf

        tf.random.set_seed(42)

    anchored = ops[ops["IsDisaggregated"] == 1]
    arr = _arrays_from(anchored)
    dates = anchored.index.strftime("%Y-%m-%d").tolist()

    model = DailyEnergyPredictor(sequence_length=7)
    model.train(
        consumption=arr["consumption"],
        temperature=arr["temperature"],
        humidity=arr["humidity"],
        rainfall=arr["rainfall"],
        has_classes=arr["has_classes"],
        day_of_week=arr["day_of_week"],
        is_weekend=arr["is_weekend"],
        dates=dates,
        epochs=epochs,
        validation_split=0.2,
    )
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_DIR)
    return model, model.validation_metrics


# ----------------------------------------------------------------------------
# forecast
# ----------------------------------------------------------------------------

def generate_forecast(
    model: DailyEnergyPredictor, ops: pd.DataFrame, n_days: int
) -> dict:
    _print_header(f"STEP 5: {n_days}-DAY FORECAST")

    past_rows = ops.tail(30)
    past = _arrays_from(past_rows)
    fc_start = ops.index.max() + pd.Timedelta(days=1)
    fc_dates = [fc_start + pd.Timedelta(days=i) for i in range(n_days)]

    # Future weather: live Open-Meteo forecast, persistence fallback.
    weather_source = "open_meteo_forecast"
    blend = {}
    try:
        blend = fetch_forecast_blend(past_days=7, forecast_days=max(n_days, 7) + 1)
    except Exception as e:
        print(f"  [!] Weather forecast fetch failed ({e}); using persistence")
        weather_source = "persistence_fallback"

    recent = ops.tail(7)
    t_mean, h_mean, r_mean = (
        float(recent["Temperature"].mean()),
        float(recent["Humidity"].mean()),
        float(recent["Rainfall"].mean()),
    )
    temps, hums, rains = [], [], []
    for d in fc_dates:
        vals = blend.get(d.strftime("%Y-%m-%d"))
        if vals is not None and all(v is not None for v in vals):
            temps.append(float(vals[0]))
            hums.append(float(vals[1]))
            rains.append(float(vals[2]))
        else:
            temps.append(t_mean)
            hums.append(h_mean)
            rains.append(r_mean)

    future_schedule = {
        "has_classes": np.array([has_classes_on(d.date()) for d in fc_dates]),
        "day_of_week": np.array([d.weekday() for d in fc_dates]),
        "is_weekend": np.array([int(d.weekday() >= 5) for d in fc_dates]),
    }
    future_weather = {
        "temperature": np.array(temps),
        "humidity": np.array(hums),
        "rainfall": np.array(rains),
    }

    result = model.predict_next_n_days(past, future_weather, future_schedule, n_days=n_days)
    preds = np.asarray(result["predictions"], dtype=float)
    lower = np.asarray(result["lower"], dtype=float)
    upper = np.asarray(result["upper"], dtype=float)
    costs = preds * COST_PER_KWH

    print(f"  Forecast window: {fc_dates[0].date()} .. {fc_dates[-1].date()}")
    print(f"  Weather source:  {weather_source}")
    print(
        f"  {'Date':<12}{'Pred kWh':>10}{'CI95 low':>10}{'CI95 high':>10}"
        f"{'Cost PHP':>12}{'Classes':>9}"
    )
    for i, d in enumerate(fc_dates):
        print(
            f"  {str(d.date()):<12}{preds[i]:>10,.1f}{lower[i]:>10,.1f}"
            f"{upper[i]:>10,.1f}{costs[i]:>12,.1f}"
            f"{'yes' if future_schedule['has_classes'][i] else 'no':>9}"
        )
    print(
        f"\n  Totals: {preds.sum():,.0f} kWh | PHP {costs.sum():,.0f} | "
        f"avg/day {preds.mean():,.0f} kWh"
    )

    peak = result.get("peak_analysis", {})
    flags = [bool(f) for f in result.get("anomaly_flags", [])]
    if any(flags):
        print(f"  [!] Anomaly flags on forecast days: {[str(fc_dates[i].date()) for i, f in enumerate(flags) if f]}")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "forecast_start": str(fc_dates[0].date()),
        "forecast_days": int(n_days),
        "weather_source": weather_source,
        "cost_per_kwh": COST_PER_KWH,
        "data_through": str(ops.index.max().date()),
        "anchored_days": int((ops["IsDisaggregated"] == 1).sum()),
        "provisional_days": int((ops["IsDisaggregated"] == 0).sum()),
        "dates": [str(d.date()) for d in fc_dates],
        "predictions_kwh": [float(v) for v in preds],
        "lower95_kwh": [float(v) for v in lower],
        "upper95_kwh": [float(v) for v in upper],
        "cost_php": [float(v) for v in costs],
        "has_classes": [int(v) for v in future_schedule["has_classes"]],
        "temperature": [float(v) for v in temps],
        "anomaly_flags": flags,
        "peak_analysis": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in peak.items()},
        "total_consumption_kwh": float(preds.sum()),
        "total_cost_php": float(costs.sum()),
    }

    OPS_OUT.mkdir(parents=True, exist_ok=True)
    (OPS_OUT / "latest_forecast.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    fc_df = pd.DataFrame(
        {
            "Date": payload["dates"],
            "PredictedConsumption": np.round(preds, 1),
            "Lower95": np.round(lower, 1),
            "Upper95": np.round(upper, 1),
            "CostPHP": np.round(costs, 2),
            "HasClasses": payload["has_classes"],
            "Temperature": np.round(temps, 1),
        }
    )
    csv_path = OPS_OUT / f"forecast_{fc_dates[0].date():%Y%m%d}.csv"
    fc_df.to_csv(csv_path, index=False)
    print(f"\n  Saved {OPS_OUT / 'latest_forecast.json'}")
    print(f"  Saved {csv_path}")
    return payload


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--xlsx", type=Path, default=None,
        help="Path to the ISELCO billing workbook (remembered after first use)",
    )
    parser.add_argument(
        "--retrain", choices=["auto", "always", "never"], default="auto",
        help="auto: retrain only when anchored bills changed (default)",
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--forecast-days", type=int, default=7)
    parser.add_argument("--no-forecast", action="store_true")
    parser.add_argument("--no-bills", action="store_true")
    parser.add_argument("--force-bills", action="store_true",
                        help="Reprocess the workbook even if unchanged")
    parser.add_argument("--max-backfill", type=int, default=400,
                        help="Max weather days to backfill in one run")
    parser.add_argument("--as-of", type=str, default=None,
                        help="Override run date (YYYY-MM-DD; testing/backfill)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not HAS_TF:
        sys.exit(
            "[FATAL] TensorFlow is required for the operational model. "
            "Install requirements first: python -m pip install -r requirements.txt"
        )

    today = (
        datetime.strptime(args.as_of, "%Y-%m-%d").date()
        if args.as_of
        else date.today()
    )
    print("=" * 70)
    print("EnergyAI Daily Update (continuous learning)")
    print(f"Run date: {today.isoformat()} | retrain: {args.retrain}")
    print("=" * 70)

    state = _load_state()
    run_log = {"ts": datetime.now().isoformat(timespec="seconds"), "as_of": str(today)}

    # Step 1: bills -----------------------------------------------------------
    bills_reprocessed = process_bills(args, state)

    # Step 2: weather ----------------------------------------------------------
    _print_header("STEP 2: WEATHER UPDATE (Open-Meteo, Echague Isabela)")
    try:
        wx_report = update_weather_store(WEATHER_STORE, today - timedelta(days=1), args.max_backfill)
        run_log["weather_days_added"] = len(wx_report["added"])
        run_log["weather_fallback_days"] = len(wx_report["fallback_days"])
    except Exception as e:
        print(f"  [!] Weather update failed ({e}); continuing with existing store")
        run_log["weather_days_added"] = 0

    # Step 3: datasets ---------------------------------------------------------
    anchored, ops, info = rebuild_datasets(today)
    run_log["anchored_days"] = info["anchored_days"]
    run_log["provisional_days"] = info["provisional_days"]

    # Step 4: retrain ----------------------------------------------------------
    _print_header("STEP 4: MODEL RETRAIN DECISION")
    sig, months = anchored_signature()
    model_exists = (MODEL_DIR / "daily_meta.joblib").exists()
    retrain = args.retrain == "always" or (
        args.retrain == "auto"
        and (sig != state.get("anchored_signature") or not model_exists)
    )

    model, retrained = None, False
    if retrain:
        reason = (
            "operational model missing" if not model_exists
            else "anchored bills changed" if sig != state.get("anchored_signature")
            else "--retrain always"
        )
        print(f"  Retraining ({reason}) on {info['anchored_days']} anchored days...")
        model, metrics = train_ops_model(ops, args.epochs)
        state["last_trained_at"] = datetime.now().isoformat(timespec="seconds")
        state["last_train_metrics"] = metrics
        retrained = True
        print(f"  Validation metrics: {metrics}")
    else:
        print(
            "  No retraining this run ("
            + ("retrain=never" if args.retrain == "never" else "anchored bills unchanged")
            + ")."
        )
    run_log["retrained"] = retrained
    state["anchored_signature"] = sig
    state["anchored_months"] = months
    state["last_run"] = run_log["ts"]

    # Step 5: forecast ---------------------------------------------------------
    forecast_payload = None
    if args.no_forecast:
        print("\nForecast skipped (--no-forecast).")
    else:
        if model is None:
            if not model_exists:
                print(
                    "\n[!] No trained operational model and retrain=never; "
                    "skipping forecast."
                )
            else:
                print("\n  Loading operational model from disk...")
                model = DailyEnergyPredictor(sequence_length=7)
                model.load(MODEL_DIR)
        if model is not None:
            forecast_payload = generate_forecast(model, ops, args.forecast_days)
            state["last_forecast_at"] = run_log["ts"]
            run_log["forecast_total_kwh"] = forecast_payload["total_consumption_kwh"]
            run_log["forecast_total_cost_php"] = forecast_payload["total_cost_php"]

    _save_state(state)
    _append_log(run_log)

    print("\n" + "=" * 70)
    print("RUN COMPLETE")
    print("=" * 70)
    print(f"  Anchored days: {info['anchored_days']} (bills through {months[-1] if months else 'n/a'})")
    print(f"  Provisional days: {info['provisional_days']}")
    print(f"  Retrained this run: {'yes' if retrained else 'no'}")
    if forecast_payload:
        print(
            f"  Forecast: {forecast_payload['forecast_start']} +"
            f"{forecast_payload['forecast_days']}d | "
            f"{forecast_payload['total_consumption_kwh']:,.0f} kWh | "
            f"PHP {forecast_payload['total_cost_php']:,.0f}"
        )


if __name__ == "__main__":
    main()
