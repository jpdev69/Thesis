"""Build the canonical daily multivariate dataset for thesis training.

Transforms monthly ISELCO billing aggregates into daily consumption values
via Denton-style proportional benchmarking (monthly totals preserved exactly),
joins daily weather from the Open-Meteo ERA5 archive for Echague, Isabela,
and attaches a proxy academic calendar (class days, holidays, breaks).

Inputs:
1) data/processed/campus_month_aggregate.csv
2) data/external/echague_weather_daily.json

Outputs:
1) data/daily_canonical_dataset.csv
2) docs/daily_data_quality_report.md

Method:
- Daily activity shape s_d = b/D + mu_c*class_day + mu_n*no_class_day
  + gamma*(T_d - monthly mean T), where parameters are estimated from the
  monthly data itself via non-negative least squares.
- Daily consumption = monthly total * s_d / sum(s_d within month), so each
  month's billed total is exactly preserved (benchmarking property).
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls

from src.models.daily_prediction_model import is_philippine_holiday

HOLY_WEEK_NOC = [
    "2024-03-28", "2024-03-29", "2024-03-30", "2024-03-31",
    "2025-04-17", "2025-04-18", "2025-04-19", "2025-04-20",
    "2026-04-02", "2026-04-03", "2026-04-04", "2026-04-05",
]

ANNUAL_NOC_RANGES = [
    ("12-24", "01-02"),
    ("10-27", "11-02"),
    ("04-01", "05-31"),
]

SOURCE_CONSUMPTION = "monthly_bill_disaggregated"
SOURCE_WEATHER = "open_meteo_era5_echague"
SOURCE_SCHEDULE = "proxy_academic_calendar"

USE_COVERAGE_ADJUSTED = True
REFERENCE_METERS = 42


def _iter_annual_ranges(d: date, ranges) -> bool:
    for start_md, end_md in ranges:
        start = date(d.year, int(start_md[:2]), int(start_md[3:]))
        end = date(d.year, int(end_md[:2]), int(end_md[3:]))
        if start <= end:
            if start <= d <= end:
                return True
        else:
            if d >= start or d <= end:
                return True
    return False


def _in_holy_week(d: date) -> bool:
    return d.isoformat() in HOLY_WEEK_NOC


def has_classes_on(d: date) -> int:
    if d.weekday() >= 5:
        return 0
    if is_philippine_holiday(d):
        return 0
    if _in_holy_week(d):
        return 0
    if _iter_annual_ranges(d, ANNUAL_NOC_RANGES):
        return 0
    return 1


def load_monthly(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["period"])
    df = df.dropna(subset=["total_kwh_clean"]).copy()
    df["monthly_total_billed"] = df["total_kwh_clean"].astype(float)
    df["coverage_ratio"] = df["coverage_ratio"].astype(float).clip(lower=0.05)
    df["monthly_total_adj"] = (
        df["monthly_total_billed"] * (REFERENCE_METERS / df["active_meter_count"])
    )
    df["year"] = df["period"].dt.year
    df["month"] = df["period"].dt.month
    return df


def load_weather(path: Path) -> pd.DataFrame:
    with open(path, "r") as f:
        payload = json.load(f)
    daily = payload["daily"]
    df = pd.DataFrame({
        "Date": pd.to_datetime(daily["time"]),
        "Temperature": daily["temperature_2m_mean"],
        "Humidity": daily["relative_humidity_2m_mean"],
        "Rainfall": daily["rain_sum"],
    })
    for col in ["Temperature", "Humidity", "Rainfall"]:
        df[f"IsImputed{col}"] = df[col].isna().astype(int)
        df[col] = df[col].interpolate(limit_direction="both")
    df = df.set_index("Date")
    return df


def build_calendar(dates: pd.Series) -> pd.DataFrame:
    rows = []
    for ts in dates:
        d = ts.date()
        rows.append({
            "Date": ts,
            "DayOfWeek": d.weekday(),
            "IsWeekend": int(d.weekday() >= 5),
            "IsHoliday": int(is_philippine_holiday(d)),
            "HasClasses": has_classes_on(d),
        })
    return pd.DataFrame(rows).set_index("Date")


def fit_monthly_shape(monthly: pd.DataFrame, daily: pd.DataFrame) -> dict:
    cal = daily.groupby([daily.index.year, daily.index.month]).agg(
        days=("HasClasses", "size"),
        class_days=("HasClasses", "sum"),
        mean_temp=("Temperature", "mean"),
    )
    cal.index = cal.index.set_names(["year", "month"])
    merged = monthly.set_index(["year", "month"]).join(cal)
    merged["nonclass_days"] = merged["days"] - merged["class_days"]
    target_col = "monthly_total_adj" if USE_COVERAGE_ADJUSTED else "monthly_total_billed"
    y = merged[target_col].values

    temp_center = float(daily["Temperature"].mean())
    temp_dev = (merged["mean_temp"].values - temp_center) * merged["days"].values

    X = np.column_stack([
        np.ones(len(merged)),
        merged["days"].values,
        merged["nonclass_days"].values,
        temp_dev,
    ])
    coefs, _ = nnls(X, y)
    b, mu_c, class_reduction, gamma = coefs
    mu_n = max(mu_c - class_reduction, 0.0)

    resid = y - X @ coefs
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "base_load": float(b),
        "mu_class": float(mu_c),
        "mu_noclass": float(mu_n),
        "gamma": float(gamma),
        "temp_center": temp_center,
        "r2_monthly": 1 - ss_res / ss_tot,
        "n_months": len(merged),
        "target": target_col,
    }


def disaggregate(monthly: pd.DataFrame, daily: pd.DataFrame, params: dict) -> pd.DataFrame:
    daily = daily.copy()
    daily["MonthKey"] = list(zip(daily.index.year, daily.index.month))
    month_temp = daily.groupby("MonthKey")["Temperature"].mean()
    month_days = daily.groupby("MonthKey")["Temperature"].size()

    monthly = monthly.copy()
    monthly["MonthKey"] = list(zip(monthly["year"], monthly["month"]))
    m_billed = dict(zip(monthly["MonthKey"], monthly["monthly_total_billed"]))
    m_adj = dict(zip(monthly["MonthKey"], monthly["monthly_total_adj"]))

    b, mu_c, mu_n = params["base_load"], params["mu_class"], params["mu_noclass"]
    gamma = params["gamma"]

    shapes = np.zeros(len(daily))
    for i, key in enumerate(daily["MonthKey"]):
        t_bar = month_temp[key]
        d_count = month_days[key]
        class_flag = daily["HasClasses"].iloc[i]
        shapes[i] = (
            b / d_count
            + mu_c * class_flag
            + mu_n * (1 - class_flag)
            + gamma * (daily["Temperature"].iloc[i] - t_bar)
        )
    shapes = np.clip(shapes, 1e-3, None)
    daily["DailyShape"] = shapes

    shape_sums = daily.groupby("MonthKey")["DailyShape"].sum()
    consumption = []
    consumption_billed = []
    for i, key in enumerate(daily["MonthKey"]):
        anchor_adj = m_adj[key] / shape_sums[key]
        anchor_billed = m_billed[key] / shape_sums[key]
        consumption.append(daily["DailyShape"].iloc[i] * anchor_adj)
        consumption_billed.append(daily["DailyShape"].iloc[i] * anchor_billed)
    daily["Consumption"] = consumption
    daily["ConsumptionBilled"] = consumption_billed
    return daily


def assemble(daily: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    monthly = monthly.copy()
    monthly["MonthKey"] = list(zip(monthly["year"], monthly["month"]))
    lookup = monthly.set_index("MonthKey")[
        ["active_meter_count", "coverage_ratio",
         "monthly_total_billed", "monthly_total_adj"]
    ]
    out = daily.copy()
    out["ActiveMeterCount"] = lookup["active_meter_count"].reindex(out["MonthKey"]).values
    out["CoverageRatio"] = lookup["coverage_ratio"].reindex(out["MonthKey"]).values
    out["MonthlyTotalBilled"] = lookup["monthly_total_billed"].reindex(out["MonthKey"]).values
    out["MonthlyTotalAdj"] = lookup["monthly_total_adj"].reindex(out["MonthKey"]).values
    out["SourceConsumption"] = SOURCE_CONSUMPTION
    out["SourceWeather"] = SOURCE_WEATHER
    out["SourceSchedule"] = SOURCE_SCHEDULE
    out["IsDisaggregated"] = 1
    out = out.drop(columns=["MonthKey"])
    return out


def _iqr_outliers(series: pd.Series) -> int:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    return int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())


def write_qa_report(out: pd.DataFrame, params: dict, monthly: pd.DataFrame, path: Path):
    n = len(out)
    class_days = out[out["HasClasses"] == 1]["Consumption"]
    noclass_days = out[out["HasClasses"] == 0]["Consumption"]
    weekday = out[out["IsWeekend"] == 0]["Consumption"]
    weekend = out[out["IsWeekend"] == 1]["Consumption"]

    month_key = out.index.to_period("M")
    within_ratios = []
    for _, g in out.groupby(month_key):
        c = g[g["HasClasses"] == 1]["Consumption"]
        n_ = g[g["HasClasses"] == 0]["Consumption"]
        if len(c) > 0 and len(n_) > 0:
            within_ratios.append(c.mean() / n_.mean())

    recon_err = float(
        (out.groupby(month_key)["ConsumptionBilled"].sum()
         - monthly.set_index(monthly["period"].dt.to_period("M"))["monthly_total_billed"]
         .reindex(out.groupby(month_key)["ConsumptionBilled"].sum().index)).abs().max()
    )
    lines = [
        "# Daily Canonical Dataset Quality Report",
        "",
        "## Dataset Identity",
        "",
        f"- Date range: {out.index.min().date()} to {out.index.max().date()}",
        f"- Total daily rows: {n}",
        "- Consumption target: "
        + ("coverage-adjusted disaggregated totals" if USE_COVERAGE_ADJUSTED else "billed totals"),
        "- Weather source: Open-Meteo ERA5 archive, Echague, Isabela (16.71N, 121.68E)",
        "- Schedule source: proxy academic calendar (see limitations)",
        "",
        "## Disaggregation Method",
        "",
        "Monthly ISELCO billed totals are distributed across days using a",
        "Denton-style proportional benchmarking scheme. The daily shape is:",
        "",
        "    s_d = b/D + mu_c*[class day] + mu_n*[no-class day] + gamma*(T_d - T_bar_month)",
        "",
        "Parameters estimated jointly from the monthly data via non-negative",
        "least squares with an operational ordering constraint",
        "(class-day intensity >= no-class-day intensity), so the summer-heat /",
        "summer-break collinearity is not absorbed by the schedule term.",
        f"Fit on {params['n_months']} months; monthly totals preserved exactly.",
        "",
        "Estimated parameters:",
        f"- Base load b: {params['base_load']:.2f} kWh/month-unit",
        f"- Class-day intensity mu_c: {params['mu_class']:.2f} kWh",
        f"- No-class-day intensity mu_n: {params['mu_noclass']:.2f} kWh",
        f"- Temperature sensitivity gamma: {params['gamma']:.2f} kWh per deg C per day",
        f"- Monthly fit R2 (constrained shape model): {params['r2_monthly']:.4f}",
        "",
        "## Completeness",
        "",
        f"- Missing Consumption: {int(out['Consumption'].isna().sum())}",
        f"- Missing Temperature: {int(out['Temperature'].isna().sum())}",
        f"- Missing Humidity: {int(out['Humidity'].isna().sum())}",
        f"- Missing Rainfall: {int(out['Rainfall'].isna().sum())}",
        f"- Imputed weather values (interpolated): "
        f"{int(out['IsImputedTemperature'].sum() + out['IsImputedHumidity'].sum() + out['IsImputedRainfall'].sum())}",
        f"- Duplicate dates: {int(out.index.duplicated().sum())}",
        "",
        "## Distribution and Outliers (IQR method)",
        "",
        f"- Consumption IQR outliers: {_iqr_outliers(out['Consumption'])}",
        f"- Temperature IQR outliers: {_iqr_outliers(out['Temperature'])}",
        f"- Humidity IQR outliers: {_iqr_outliers(out['Humidity'])}",
        f"- Rainfall IQR outliers: {_iqr_outliers(out['Rainfall'])}",
        "- Note: humidity/rainfall outliers are expected; both are",
        "  right/upper-skewed climate variables (monsoon and typhoon events).",
        "",
        "## Operational Splits",
        "",
        f"- Class-day mean consumption (aggregate): {class_days.mean():.1f} kWh "
        f"({len(class_days)} days)",
        f"- No-class-day mean consumption (aggregate): {noclass_days.mean():.1f} kWh "
        f"({len(noclass_days)} days)",
        f"- Within-month class/no-class mean ratio (average): "
        f"{np.mean(within_ratios):.3f}",
        "  (aggregate ratio is masked by hot summer no-class months;",
        "  the within-month ratio reflects the schedule shape effect)",
        f"- Weekday mean: {weekday.mean():.1f} kWh ({len(weekday)} days)",
        f"- Weekend mean: {weekend.mean():.1f} kWh ({len(weekend)} days)",
        "",
        "## Benchmarking Verification",
        "",
        f"- Max monthly reconstruction error (billed): {recon_err:.6f} kWh",
        f"- Meter coverage range: {out['ActiveMeterCount'].min():.0f} to "
        f"{out['ActiveMeterCount'].max():.0f} of {REFERENCE_METERS} reference meters",
        "",
        "## Declared Limitations",
        "",
        "1. Daily consumption values are ESTIMATES reconstructed from monthly",
        "   bills, not metered daily readings. Daily variance is model-imposed",
        "   (schedule + temperature shape); true daily variance is unobserved.",
        "2. Schedule is a proxy calendar (weekends, PH holidays, Holy Week,",
        "   Christmas/semestral/summer breaks). The registrar's official",
        "   calendar should replace it when available.",
        "3. Coverage adjustment scales monthly totals by "
        f"{REFERENCE_METERS}/active meters to stabilize meter-count shifts;",
        "   raw billed totals are retained in ConsumptionBilled.",
        "4. Months with unusually low reported totals (e.g., 2025-01) remain",
        "   visible in the daily series and are flagged by outlier counts.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monthly", type=Path, default=Path("data/processed/campus_month_aggregate.csv"))
    parser.add_argument("--weather", type=Path, default=Path("data/external/echague_weather_daily.json"))
    parser.add_argument("--output", type=Path, default=Path("data/daily_canonical_dataset.csv"))
    parser.add_argument("--report", type=Path, default=Path("docs/daily_data_quality_report.md"))
    args = parser.parse_args()

    monthly = load_monthly(args.monthly)
    weather = load_weather(args.weather)

    first = monthly["period"].min().to_pydatetime().replace(day=1, hour=0, minute=0, second=0)
    last = (monthly["period"].max() + pd.offsets.MonthEnd(0)).to_pydatetime()
    weather = weather[(weather.index >= first) & (weather.index <= last)]

    calendar = build_calendar(pd.Series(weather.index))
    daily = weather.join(calendar)
    missing_cal = daily["HasClasses"].isna().sum()
    if missing_cal:
        raise ValueError(f"Calendar gaps for {missing_cal} days")

    params = fit_monthly_shape(monthly, daily)
    print("Fitted monthly shape parameters:")
    for k, v in params.items():
        print(f"  {k}: {v}")

    daily = disaggregate(monthly, daily, params)
    out = assemble(daily, monthly)

    out.index.name = "Date"
    out.to_csv(args.output, index=True)
    print(f"Wrote {len(out)} daily rows to {args.output}")

    write_qa_report(out, params, monthly, args.report)
    print(f"Wrote QA report to {args.report}")


if __name__ == "__main__":
    main()
