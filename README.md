# Iberian Electricity Price Analysis (OMIE)

> How do Iberian day-ahead electricity prices behave, and can a simple model beat a naive forecast?

**Status:** 🚧 Work in progress. Data pipeline and exploration done; forecasting next
(target: January 2027).

## Why it matters

Electricity prices in Portugal and Spain are set daily, hour by hour, in the OMIE day-ahead market.
The fast growth of solar power is changing how these prices behave: cheaper middays, more
expensive evenings, and the first negative prices. Understanding and forecasting these patterns
matters for anyone who buys, sells, stores or trades electricity.

## Method

1. **Data:** nearly 9 years of hourly OMIE day-ahead prices for Portugal and Spain (2018–2026),
   downloaded automatically, cleaned and validated (DST days, the October 2025 switch to
   15-minute periods, gaps, outliers).
2. **Exploration:** long-term trends, volatility, daily and weekly patterns, negative prices,
   Portugal–Spain price differences, autocorrelation.
3. **Forecasting** *(next)*: naive baselines (same hour yesterday / last week), then linear
   regression and gradient boosting (LightGBM), validated walk-forward with no look-ahead bias.
4. **Optional:** simulated battery arbitrage backtest.

## Results so far

![Price relative to the daily average, by hour and year](reports/figures/daily_profile_relative.png)

- **Solar has reshaped the day.** Until 2021 the cheapest hours were at night. Since 2022 they are
  in the early afternoon; in 2026 the 14:00 hour is about 61 EUR/MWh below the daily average and
  the 21:00 hour about 59 EUR/MWh above it.
- **Prices swing much more within the day.** The average daily range went from 30 % of the average
  price in 2018 to about 150 % in 2025–2026.
- **Negative prices appeared in April 2024** and are increasing: 613 hours in Portugal in 2026 so
  far, almost all at midday in spring.
- **Portugal and Spain split more often**: different prices in 14 % of hours in 2026, against 5 %
  in 2018, mostly at midday.
- **Benchmark to beat:** a naive "same hour yesterday" forecast is off by about 20 EUR/MWh on
  average since 2023 (5 EUR/MWh in 2018–2020).

Full findings, charts and tables: **[docs/analysis.md](docs/analysis.md)**.
Forecasting results will be added here in the next phase.

## Limitations

- The dataset contains only prices. Drivers such as solar output, gas prices and interconnection
  limits are inferred from price patterns (timing, season, PT–ES splits), not measured. The 2026
  price climb in particular cannot be explained from prices alone.
- During the Iberian gas price cap (June 2022 – December 2023), part of the cost of gas generation
  was charged to consumers outside the day-ahead price.
- Day-ahead market only; intraday and balancing markets are not covered.

## Next steps

- Forecasting models and walk-forward evaluation against the naive baselines.
- Optional: battery arbitrage backtest using the growing daily price range.
- Possible extension: gas prices (MIBGAS) or generation data (ENTSO-E) to explain price drivers.

## Quickstart

```bash
git clone https://github.com/samuel-prog-vaz/energy-market-analysis.git
cd energy-market-analysis
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
pip install -e .
python -m omie.download           # fetch OMIE price files
python -m omie.clean              # build the clean dataset
```

Then open [notebooks/01_exploration.ipynb](notebooks/01_exploration.ipynb).
Architecture, design decisions, testing and dependencies:
**[docs/technical.md](docs/technical.md)**.

## Stack

Python 3.12 · pandas · matplotlib/seaborn · statsmodels · scikit-learn · LightGBM · Jupyter ·
pytest · ruff
