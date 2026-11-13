# Iberian Electricity Price Analysis (OMIE)

> How do Iberian day-ahead electricity prices behave, and can a simple model beat a naive forecast?

**Status:** 🚧 Work in progress (target: January 2027)

## TL;DR
_One-paragraph summary and headline result go here once the analysis is done._

## Data
- **Source:** [OMIE](https://www.omie.es/) day-ahead market, marginal price files (`marginalpdbc`) for Portugal (PT) and Spain (ES), in EUR/MWh
- **Period:** 1 Jan 2018 to the latest published day
- **Time handling:** the market day runs in Spanish time (Europe/Madrid). Each period is converted to a UTC start time, so DST days (23 or 25 hours) form a continuous series with no duplicated or missing hours. `datetime_local` is kept for analysing daily patterns.
- **15-minute switch:** since 1 Oct 2025 the day-ahead market clears in 15-minute periods. Two datasets are built:
  - `omie_prices_native.parquet`: every period as published (hourly, then 15-minute)
  - `omie_prices_hourly.parquet`: one continuous hourly series, with quarter-hours averaged to hours. Modelling uses this one.
- **Validation:** checks for the expected number of periods per day, duplicates, missing hours, missing values and out-of-range prices. The results and a yearly summary are in [reports/data_quality.md](reports/data_quality.md).

```bash
python -m omie.download   # fetch raw files into data/raw/ (re-run to update; existing files are skipped)
python -m omie.clean      # build data/processed/*.parquet and the quality report
```

## Method
1. Data download, cleaning and validation (DST, gaps, outliers)
2. Exploratory analysis: daily/seasonal patterns, price spikes, PT–ES spread, link to renewables and gas
3. Forecasting
   - Naive baselines (same hour previous day / previous week)
   - Linear regression and gradient boosting (LightGBM)
   - Walk-forward validation, no look-ahead bias
4. _(Optional)_ Simulated battery arbitrage backtest

## Results
_TBD_

## Limitations
_TBD_

## Next steps
_TBD_

## Reproduce

```bash
git clone <repo-url>
cd energy-market-analysis
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
pip install -e .
pytest
```

## Project structure

```
data/
  raw/          # downloaded OMIE files (not committed)
  processed/    # cleaned datasets (not committed)
notebooks/      # exploration and modelling notebooks
reports/figures/# exported charts for the README
src/omie/       # reusable code (download, cleaning, features, models)
tests/          # unit tests
```

## Stack
Python 3.12 · pandas · scikit-learn · LightGBM · statsmodels · matplotlib/seaborn · Jupyter
