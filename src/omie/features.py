"""Build model inputs for day-ahead forecasting, without look-ahead.

Forecasting setup: on day D-1, before the market closes at noon, forecast the 24
hourly prices of day D. At that moment all prices up to the end of D-1 are known
(they were published on D-2), and nothing from day D. Every feature below uses
only days D-1 and earlier, plus the calendar, which is known in advance.

Data layout: prices are first arranged as a *panel*, one row per day and one column
per local hour (0-23). This is the usual layout in electricity price forecasting
because the 24 prices of a day are set together in one auction. DST days are
squeezed into 24 columns: on the 23-hour spring day the missing 02:00 hour is
interpolated from 01:00 and 03:00; on the 25-hour autumn day the two 02:00 hours are
averaged. That affects 2 days a year.
"""

from __future__ import annotations

import holidays
import pandas as pd

HOURS = list(range(24))
FEATURES = [
    "lag_1d",  # same hour, day D-1
    "lag_2d",  # same hour, day D-2
    "lag_7d",  # same hour, day D-7
    "mean_7d_same_hour",  # average of the same hour over D-1 ... D-7
    "prev_day_mean",  # average of all 24 hours of D-1
    "prev_day_min",
    "prev_day_max",
    "hour",
    "weekday",  # 0 = Monday
    "month",
    "is_weekend",
    "is_holiday_pt",
    "is_holiday_es",
]
CATEGORICAL = ["hour", "weekday", "month"]


def to_panel(hourly: pd.DataFrame, price_col: str = "price_pt") -> pd.DataFrame:
    """Daily panel: index = date, columns = hour 0-23 (local time), values = price.

    ``hourly`` is the output of ``omie.data.load_hourly()`` (needs ``date``, ``hour``).
    """
    panel = hourly.pivot_table(index="date", columns="hour", values=price_col, aggfunc="mean")
    panel = panel.reindex(columns=HOURS)
    panel = panel.interpolate(axis=1, limit_area="inside")  # spring DST: missing 02:00
    panel.index = pd.DatetimeIndex(panel.index, name="date")
    full_days = pd.date_range(panel.index.min(), panel.index.max(), freq="D", name="date")
    return panel.reindex(full_days)


def build_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Long table, one row per (date, hour), with the features and the target ``price``.

    Rows whose lagged inputs are not available yet (the first 7 days) are dropped.
    """
    lag1, lag2, lag7 = panel.shift(1), panel.shift(2), panel.shift(7)
    mean_7d = sum(panel.shift(k) for k in range(1, 8)) / 7

    def long(frame: pd.DataFrame, name: str) -> pd.Series:
        return frame.stack(future_stack=True).rename(name)

    df = pd.concat(
        [
            long(panel, "price"),
            long(lag1, "lag_1d"),
            long(lag2, "lag_2d"),
            long(lag7, "lag_7d"),
            long(mean_7d, "mean_7d_same_hour"),
        ],
        axis=1,
    )
    df.index = df.index.set_names(["date", "hour"])
    df = df.reset_index()

    prev = pd.DataFrame(
        {
            "prev_day_mean": lag1.mean(axis=1),
            "prev_day_min": lag1.min(axis=1),
            "prev_day_max": lag1.max(axis=1),
        }
    )
    df = df.join(prev, on="date")

    years = range(df["date"].dt.year.min(), df["date"].dt.year.max() + 1)
    hol_pt = holidays.country_holidays("PT", years=years)
    hol_es = holidays.country_holidays("ES", years=years)
    df["weekday"] = df["date"].dt.day_of_week
    df["month"] = df["date"].dt.month
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    df["is_holiday_pt"] = df["date"].dt.date.map(lambda d: d in hol_pt).astype(int)
    df["is_holiday_es"] = df["date"].dt.date.map(lambda d: d in hol_es).astype(int)

    df = df.dropna(subset=FEATURES).reset_index(drop=True)
    return df[["date", "hour", "price", *[f for f in FEATURES if f != "hour"]]]
