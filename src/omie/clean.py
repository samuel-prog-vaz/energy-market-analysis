"""Parse, clean and validate OMIE day-ahead prices, and build the processed datasets.

Raw file format (one file per delivery day)::

    MARGINALPDBC;
    2024;03;31;1;3.2;3.2;        <- year;month;day;period;price_PT;price_ES;
    ...
    *

Periods count from 1 at local midnight (Spanish time, Europe/Madrid, which is how
the Iberian market defines its day; Portuguese clocks are one hour behind). There
are 24 hourly periods (23/25 on DST change days) until 30 Sep 2025, then 96
quarter-hour periods (92/100) from 1 Oct 2025, when the European day-ahead market
moved to a 15-minute resolution.

Outputs (in data/processed/):
    omie_prices_native.parquet   one row per market period, as published
    omie_prices_hourly.parquet   hourly series; quarter-hours averaged to hours

Usage:
    python -m omie.clean
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

from omie.config import DATA_PROCESSED, ROOT
from omie.download import RAW_DIR

MARKET_TZ = "Europe/Madrid"
PRICE_FLOOR, PRICE_CAP = -500.0, 5000.0  # wider than any harmonised SDAC limit used so far
_FILE_RE = re.compile(r"marginalpdbc_(\d{8})\.(\d+)$")


# --------------------------------------------------------------------------- parsing
def parse_text(text: str) -> pd.DataFrame:
    """Parse the contents of one marginalpdbc file into date/period/price rows."""
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.strip().split(";")]
        if len(parts) < 6 or not parts[0].isdigit():  # header, '*' footer, blank lines
            continue
        y, m, d, period, pt, es = parts[:6]
        rows.append((f"{y}-{m}-{d}", int(period), float(pt), float(es)))
    df = pd.DataFrame(rows, columns=["date", "period", "price_pt", "price_es"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _iter_raw_files(raw_dir: Path):
    """Yield (filename, text) for every raw daily file, inside zips or loose."""
    for zpath in sorted(raw_dir.glob("*.zip")):
        with zipfile.ZipFile(zpath) as z:
            for name in z.namelist():
                yield name, z.read(name).decode("latin-1")
    for path in sorted((raw_dir / "daily").glob("marginalpdbc_*")):
        yield path.name, path.read_text(encoding="latin-1")


def load_raw(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Read all raw files. If a day has several versions (.1, .2, ...) keep the latest."""
    latest: dict[str, tuple[int, str]] = {}
    for name, text in _iter_raw_files(raw_dir):
        m = _FILE_RE.search(name)
        if not m:
            continue
        day, version = m.group(1), int(m.group(2))
        if day not in latest or version > latest[day][0]:
            latest[day] = (version, text)
    if not latest:
        raise FileNotFoundError(f"No raw files in {raw_dir}. Run `python -m omie.download`.")
    frames = [parse_text(text) for _, (_, text) in sorted(latest.items())]
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- timestamps
def add_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Turn (date, period) into a UTC start time, handling DST and 15-minute periods.

    Working in UTC avoids the duplicated/missing local hours on DST change days.
    """
    df = df.copy()
    n_periods = df.groupby("date")["period"].transform("max")
    midnight = pd.to_datetime(df["date"]).dt.tz_localize(MARKET_TZ)
    next_midnight = (pd.to_datetime(df["date"]) + pd.Timedelta(days=1)).dt.tz_localize(MARKET_TZ)
    day_hours = (next_midnight - midnight) / pd.Timedelta(hours=1)  # 23, 24 or 25

    df["resolution_min"] = (60 * day_hours / n_periods).round().astype(int)
    df["datetime_utc"] = midnight.dt.tz_convert("UTC") + pd.to_timedelta(
        (df["period"] - 1) * df["resolution_min"], unit="min"
    )
    df["datetime_local"] = df["datetime_utc"].dt.tz_convert(MARKET_TZ)
    return df


def to_hourly(native: pd.DataFrame) -> pd.DataFrame:
    """Average quarter-hour prices to hourly (hourly periods pass through unchanged)."""
    hourly = (
        native.assign(datetime_utc=native["datetime_utc"].dt.floor("h"))
        .groupby("datetime_utc", as_index=False)[["price_pt", "price_es"]]
        .mean()
    )
    hourly["datetime_local"] = hourly["datetime_utc"].dt.tz_convert(MARKET_TZ)
    return hourly[["datetime_utc", "datetime_local", "price_pt", "price_es"]]


# --------------------------------------------------------------------------- validation
def validate(native: pd.DataFrame, hourly: pd.DataFrame) -> list[str]:
    """Return a list of data problems (empty list = all checks passed)."""
    issues = []

    bad_res = native.loc[~native["resolution_min"].isin([15, 60]), "date"].unique()
    if len(bad_res):
        issues.append(f"{len(bad_res)} days with an unexpected number of periods: {bad_res[:5]}")

    dup = native["datetime_utc"].duplicated().sum()
    if dup:
        issues.append(f"{dup} duplicated timestamps")

    expected = pd.date_range(hourly["datetime_utc"].min(), hourly["datetime_utc"].max(), freq="h")
    missing = expected.difference(hourly["datetime_utc"])
    if len(missing):
        issues.append(f"{len(missing)} missing hours, first: {missing[0]}")

    for col in ("price_pt", "price_es"):
        n_nan = native[col].isna().sum()
        if n_nan:
            issues.append(f"{n_nan} missing values in {col}")
        out = native[(native[col] < PRICE_FLOOR) | (native[col] > PRICE_CAP)]
        if len(out):
            issues.append(f"{len(out)} values of {col} outside [{PRICE_FLOOR}, {PRICE_CAP}]")
    return issues


def quality_report(native: pd.DataFrame, hourly: pd.DataFrame, issues: list[str]) -> str:
    """Short markdown summary of the dataset, saved next to the figures."""
    h = hourly.set_index("datetime_local")
    yearly = h[["price_pt", "price_es"]].groupby(h.index.year).agg(["mean", "min", "max"])
    yearly.columns = [f"{c}_{s}" for c, s in yearly.columns]
    spread = (h["price_pt"] != h["price_es"]).groupby(h.index.year).mean().mul(100)
    yearly["hours_pt_ne_es_pct"] = spread
    neg = (h["price_es"] < 0).groupby(h.index.year).sum()
    yearly["hours_negative_es"] = neg

    n_hourly = (native["resolution_min"] == 60).sum()
    n_quarter = (native["resolution_min"] == 15).sum()
    lines = [
        "# OMIE day-ahead prices: data quality report",
        "",
        "Generated by `python -m omie.clean`.",
        "",
        f"- Period: {h.index.min():%Y-%m-%d} to {h.index.max():%Y-%m-%d} (market time)",
        f"- Native rows: {len(native):,} | hourly rows: {len(hourly):,}",
        f"- Hourly periods: {n_hourly:,} | 15-minute periods: {n_quarter:,}",
        f"- Checks: {'all passed' if not issues else str(len(issues)) + ' issue(s)'}",
        *[f"  - {i}" for i in issues],
        "",
        "## Yearly summary (EUR/MWh, hourly series)",
        "",
        yearly.round(2).to_markdown(),
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- pipeline
def build(raw_dir: Path = RAW_DIR, out_dir: Path = DATA_PROCESSED) -> list[str]:
    native = add_timestamps(load_raw(raw_dir)).sort_values("datetime_utc").reset_index(drop=True)
    native = native[
        [
            "datetime_utc",
            "datetime_local",
            "date",
            "period",
            "resolution_min",
            "price_pt",
            "price_es",
        ]
    ]
    hourly = to_hourly(native)
    issues = validate(native, hourly)

    out_dir.mkdir(parents=True, exist_ok=True)
    native.to_parquet(out_dir / "omie_prices_native.parquet", index=False)
    hourly.to_parquet(out_dir / "omie_prices_hourly.parquet", index=False)
    report = ROOT / "reports" / "data_quality.md"
    report.write_text(quality_report(native, hourly, issues), encoding="utf-8")

    print(f"native: {len(native):,} rows | hourly: {len(hourly):,} rows -> {out_dir}")
    print("checks passed" if not issues else "ISSUES:\n  " + "\n  ".join(issues))
    print(f"report: {report}")
    return issues


if __name__ == "__main__":
    build()
