# Iberian Electricity Price Analysis (OMIE)

> How do Iberian day-ahead electricity prices behave, and can a simple model beat a naive forecast?

**Status:** 🚧 Work in progress (target: January 2027)

## TL;DR
_One-paragraph summary and headline result go here once the analysis is done._

## Data
- **Source:** [OMIE](https://www.omie.es/) day-ahead market, hourly marginal prices for Portugal (PT) and Spain (ES)
- **Period:** _TBD_
- **Note:** since 1 Oct 2025 the day-ahead market clears in 15-minute periods; _how this is handled: TBD_

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
