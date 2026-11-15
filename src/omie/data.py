"""Load the processed OMIE datasets for analysis and modelling."""

from __future__ import annotations

import pandas as pd

from omie.config import DATA_PROCESSED

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_hourly() -> pd.DataFrame:
    """Hourly PT/ES prices indexed by Madrid local time, with calendar columns added.

    Columns: price_pt, price_es (EUR/MWh), date, year, month, hour,
    weekday (0 = Monday), weekday_name, is_weekend.

    The index is local time because daily patterns follow the clock. On the autumn
    DST day the 02:00 hour appears twice (with different UTC offsets), which is
    correct and harmless for grouping by hour.
    """
    path = DATA_PROCESSED / "omie_prices_hourly.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `python -m omie.clean` first.")
    df = pd.read_parquet(path).set_index("datetime_local").drop(columns="datetime_utc")

    idx = df.index
    df["date"] = idx.date
    df["year"] = idx.year
    df["month"] = idx.month
    df["hour"] = idx.hour
    df["weekday"] = idx.day_of_week
    df["weekday_name"] = pd.Categorical(
        [WEEKDAY_NAMES[d] for d in idx.day_of_week], categories=WEEKDAY_NAMES, ordered=True
    )
    df["is_weekend"] = df["weekday"] >= 5
    return df
