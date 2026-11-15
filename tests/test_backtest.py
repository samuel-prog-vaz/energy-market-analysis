import numpy as np
import pandas as pd
import pytest

from omie.backtest import BENCHMARK, MODELS, metrics, monthly_splits, run_backtest
from omie.features import build_features, to_panel


def synthetic_features(days=150, seed=0):
    """Features from a noisy daily + weekly price pattern, starting 2024-01-01."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    rows = []
    for dt in dates:
        for h in range(24):
            price = 60 + 20 * np.sin(2 * np.pi * h / 24) - 10 * (dt.weekday() >= 5)
            rows.append((dt.date(), h, price + rng.normal(0, 3)))
    hourly = pd.DataFrame(rows, columns=["date", "hour", "price_pt"])
    return build_features(to_panel(hourly))


def test_training_always_ends_before_test_month():
    dates = synthetic_features()["date"]
    splits = list(monthly_splits(dates, "2024-03"))
    assert [s.strftime("%Y-%m") for s, _, _ in splits] == ["2024-03", "2024-04", "2024-05"]
    for start, train, test in splits:
        assert dates[train].max() < start <= dates[test].min()
        assert not (train & test).any()
        assert dates[test].dt.to_period("M").nunique() == 1


def test_backtest_output_and_naive_forecasts():
    feats = synthetic_features()
    fc = run_backtest(feats, test_start="2024-03", verbose=False)
    assert list(fc.columns) == ["date", "hour", "actual", *MODELS]
    assert fc["date"].min() == pd.Timestamp("2024-03-01")
    assert len(fc) == len(feats[feats["date"] >= "2024-03-01"])
    merged = fc.merge(feats, on=["date", "hour"])
    assert (merged["naive_24h"] == merged["lag_1d"]).all()
    assert (merged["naive_168h"] == merged["lag_7d"]).all()
    assert fc[MODELS].notna().all().all()


def test_models_beat_naive_on_a_learnable_pattern():
    """On a clean daily/weekly pattern with noise, the trained models should win."""
    fc = run_backtest(synthetic_features(), test_start="2024-03", verbose=False)
    rel = metrics(fc)["rel_MAE"].iloc[0]
    assert rel["ridge"] < 1 and rel["lgbm"] < 1


def test_metrics():
    fc = pd.DataFrame(
        {
            "actual": [10.0, 20.0],
            "naive_24h": [12.0, 16.0],  # errors 2, 4 -> MAE 3
            "naive_168h": [10.0, 20.0],  # MAE 0
            "ridge": [13.0, 23.0],  # MAE 3
            "lgbm": [11.0, 21.0],  # MAE 1
        }
    )
    m = metrics(fc).iloc[0]
    assert m["MAE"]["naive_24h"] == 3
    assert m["RMSE"]["naive_24h"] == pytest.approx(np.sqrt((4 + 16) / 2))
    assert m["rel_MAE"][BENCHMARK] == 1
    assert m["rel_MAE"]["lgbm"] == pytest.approx(1 / 3)
