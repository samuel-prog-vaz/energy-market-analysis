import pandas as pd
import pytest

from omie.clean import add_timestamps, parse_text, to_hourly, validate


def make_file(day: str, n_periods: int, price=lambda p: float(p)) -> str:
    """Build a synthetic marginalpdbc file: header, one line per period, '*' footer."""
    y, m, d = day.split("-")
    lines = ["MARGINALPDBC;"]
    lines += [f"{y};{m};{d};{p};{price(p)};{price(p)};" for p in range(1, n_periods + 1)]
    lines.append("*")
    return "\r\n".join(lines)


def native_for(*files: str) -> pd.DataFrame:
    return add_timestamps(pd.concat([parse_text(f) for f in files], ignore_index=True))


def test_parse_skips_header_and_footer():
    df = parse_text(make_file("2024-01-15", 24))
    assert len(df) == 24
    assert list(df.columns) == ["date", "period", "price_pt", "price_es"]
    assert df["price_es"].iloc[-1] == 24.0


def test_parse_handles_negative_and_decimal_prices():
    df = parse_text("MARGINALPDBC;\n2024;04;14;13;-0.01;-1.5;\n*\n")
    assert df["price_pt"].iloc[0] == -0.01
    assert df["price_es"].iloc[0] == -1.5


@pytest.mark.parametrize(
    "day, n, first_utc, last_utc",
    [
        # normal winter day: local midnight CET = 23:00 UTC the day before
        ("2024-01-15", 24, "2024-01-14 23:00", "2024-01-15 22:00"),
        # spring DST: 23 hours, clocks jump 02:00 -> 03:00
        ("2024-03-31", 23, "2024-03-30 23:00", "2024-03-31 21:00"),
        # autumn DST: 25 hours, 02:00-03:00 happens twice
        ("2024-10-27", 25, "2024-10-26 22:00", "2024-10-27 22:00"),
        # 15-minute periods from 1 Oct 2025
        ("2025-10-01", 96, "2025-09-30 22:00", "2025-10-01 21:45"),
        # 15-minute periods on an autumn DST day: 100 quarter-hours
        ("2025-10-26", 100, "2025-10-25 22:00", "2025-10-26 22:45"),
    ],
)
def test_timestamps_handle_dst_and_resolution(day, n, first_utc, last_utc):
    df = native_for(make_file(day, n))
    assert df["datetime_utc"].iloc[0] == pd.Timestamp(first_utc, tz="UTC")
    assert df["datetime_utc"].iloc[-1] == pd.Timestamp(last_utc, tz="UTC")
    assert df["datetime_utc"].is_unique
    step = df["datetime_utc"].diff().dropna().unique()
    assert len(step) == 1  # evenly spaced in UTC, even across the clock change


def test_resolution_column():
    df = native_for(make_file("2025-09-30", 24), make_file("2025-10-01", 96))
    assert set(df.loc[df["date"].astype(str) == "2025-09-30", "resolution_min"]) == {60}
    assert set(df.loc[df["date"].astype(str) == "2025-10-01", "resolution_min"]) == {15}


def test_to_hourly_averages_quarters():
    df = native_for(make_file("2025-10-01", 96))  # prices 1..96
    hourly = to_hourly(df)
    assert len(hourly) == 24
    assert hourly["price_es"].iloc[0] == pytest.approx((1 + 2 + 3 + 4) / 4)


def test_hourly_series_is_continuous_across_resolution_change():
    df = native_for(make_file("2025-09-30", 24), make_file("2025-10-01", 96))
    hourly = to_hourly(df)
    assert len(hourly) == 48
    assert validate(df, hourly) == []


def test_validate_flags_missing_hour_and_bad_price():
    text = make_file("2024-01-15", 24, price=lambda p: 9999.0 if p == 5 else 50.0)
    df = native_for(text)
    df = df[df["period"] != 10]  # drop one hour
    issues = validate(df, to_hourly(df))
    assert any("missing hours" in i for i in issues)
    assert any("outside" in i for i in issues)
