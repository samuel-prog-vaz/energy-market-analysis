import numpy as np
import pandas as pd
import pytest

from omie.features import FEATURES, build_features, to_panel


def synthetic_hourly(start="2024-01-01", days=30, price=lambda d, h: 100 * d + h):
    """Hourly table like load_hourly(): price = 100 * day_number + hour (easy to check)."""
    dates = pd.date_range(start, periods=days, freq="D")
    rows = [(dt.date(), h, float(price(i, h))) for i, dt in enumerate(dates) for h in range(24)]
    return pd.DataFrame(rows, columns=["date", "hour", "price_pt"])


def features_for(hourly):
    return build_features(to_panel(hourly)).set_index(["date", "hour"])


def test_lags_point_to_the_right_days():
    f = features_for(synthetic_hourly())
    row = f.loc[(pd.Timestamp("2024-01-15"), 10)]  # day number 14
    assert row["price"] == 1410
    assert row["lag_1d"] == 1310
    assert row["lag_2d"] == 1210
    assert row["lag_7d"] == 710
    assert row["mean_7d_same_hour"] == pytest.approx(np.mean([100 * d + 10 for d in range(7, 14)]))
    assert row["prev_day_mean"] == pytest.approx(1300 + 11.5)
    assert row["prev_day_min"] == 1300
    assert row["prev_day_max"] == 1323


def test_first_week_dropped_and_no_missing_features():
    f = features_for(synthetic_hourly(days=30))
    assert f.index.get_level_values("date").min() == pd.Timestamp("2024-01-08")
    assert len(f) == (30 - 7) * 24
    assert f[[c for c in FEATURES if c != "hour"]].notna().all().all()


def test_no_look_ahead():
    """Changing prices on day D and later must not change any feature of day D."""
    base = synthetic_hourly()
    corrupted = base.copy()
    cutoff = pd.Timestamp("2024-01-20").date()
    corrupted.loc[corrupted["date"] >= cutoff, "price_pt"] = 99999.0

    day = pd.Timestamp("2024-01-20")
    cols = [c for c in FEATURES if c != "hour"]
    a = features_for(base).loc[day, cols]
    b = features_for(corrupted).loc[day, cols]
    pd.testing.assert_frame_equal(a, b)
    # sanity check: the target itself did change
    assert (features_for(corrupted).loc[day, "price"] == 99999.0).all()


def test_spring_dst_missing_hour_is_interpolated():
    hourly = synthetic_hourly(start="2024-03-25", days=10)
    hourly = hourly[
        ~((hourly["date"] == pd.Timestamp("2024-03-31").date()) & (hourly["hour"] == 2))
    ]
    panel = to_panel(hourly)
    day = panel.loc["2024-03-31"]
    assert day[2] == pytest.approx((day[1] + day[3]) / 2)
    assert panel.notna().all().all()


def test_autumn_dst_duplicate_hour_is_averaged():
    hourly = synthetic_hourly(start="2024-10-20", days=10)
    extra = pd.DataFrame([[pd.Timestamp("2024-10-27").date(), 2, 0.0]], columns=hourly.columns)
    panel = to_panel(pd.concat([hourly, extra]))
    original = 100 * 7 + 2  # day number 7 = 2024-10-27
    assert panel.loc["2024-10-27", 2] == pytest.approx(original / 2)


def test_calendar_and_holidays():
    f = features_for(synthetic_hourly(start="2024-04-01", days=200)).reset_index()
    day = f[f["date"] == "2024-04-25"].iloc[0]  # Thursday, Portuguese Freedom Day
    assert (day["weekday"], day["is_weekend"]) == (3, 0)
    assert (day["is_holiday_pt"], day["is_holiday_es"]) == (1, 0)
    day = f[f["date"] == "2024-10-12"].iloc[0]  # Saturday, Spanish National Day
    assert (day["is_weekend"], day["is_holiday_pt"], day["is_holiday_es"]) == (1, 0, 1)
