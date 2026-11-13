"""Download OMIE day-ahead marginal price files (``marginalpdbc``).

OMIE publishes one file per delivery day (``marginalpdbc_YYYYMMDD.N``, usually
version N=1) and, for
completed years, a yearly zip with all daily files. This module grabs the yearly
zip when it exists and falls back to daily files otherwise (e.g. the current
year). Files already on disk are skipped, so re-running only fetches what is new.

Usage:
    python -m omie.download                    # 2018 up to tomorrow
    python -m omie.download --start-year 2021
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
import zipfile
from pathlib import Path

import requests
import truststore

from omie.config import DATA_RAW

# OMIE's server does not send its full certificate chain, which certifi (requests'
# default CA bundle) cannot complete. truststore verifies against the operating
# system's certificate store instead, which can. Verification stays on.
truststore.inject_into_ssl()

BASE_URL = "https://www.omie.es/es/file-download"
PARENT = "marginalpdbc"
RAW_DIR = DATA_RAW / PARENT
DEFAULT_START_YEAR = 2018
MAX_VERSION = 5  # highest daily file version to try (.1, .2, ...)

_session = requests.Session()
_session.headers["User-Agent"] = "omie-analysis/0.1 (research project)"


def _url(filename: str) -> str:
    return f"{BASE_URL}?parents={PARENT}&filename={filename}"


def _get(filename: str, retries: int = 3) -> bytes | None:
    """Return the file content, or None if OMIE does not have it (404)."""
    for attempt in range(1, retries + 1):
        try:
            r = _session.get(_url(filename), timeout=30)
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
    return None


def download_year_zip(year: int, force: bool = False) -> Path | None:
    """Download the yearly archive. Returns its path, or None if it does not exist."""
    path = RAW_DIR / f"{PARENT}_{year}.zip"
    if path.exists() and not force:
        return path
    content = _get(path.name)
    if content is None or not content.startswith(b"PK"):  # not a zip -> not published
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    zipfile.ZipFile(path).testzip()  # fail early on a corrupt archive
    return path


def download_day(day: dt.date, force: bool = False) -> Path | None:
    """Download one daily file. Returns its path, or None if not published yet.

    Most days are published as version ``.1``, but some exist only as ``.2`` or
    ``.3`` (e.g. 2023-05-28, 2025-10-30, 2025-11-27), so versions are tried in order
    and the first one found is kept.
    """
    daily_dir = RAW_DIR / "daily"
    existing = sorted(daily_dir.glob(f"{PARENT}_{day:%Y%m%d}.*"))
    if existing and not force:
        return existing[-1]
    for version in range(1, MAX_VERSION + 1):
        path = daily_dir / f"{PARENT}_{day:%Y%m%d}.{version}"
        content = _get(path.name)
        time.sleep(0.2)  # be polite to OMIE's server
        if content is not None and content.startswith(b"MARGINALPDBC"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            return path
    return None


def download_range(start_year: int = DEFAULT_START_YEAR, end: dt.date | None = None) -> None:
    """Fetch everything from 1 Jan ``start_year`` to ``end`` (default: tomorrow)."""
    end = end or dt.date.today() + dt.timedelta(days=1)  # day-ahead: tomorrow may exist
    for year in range(start_year, end.year + 1):
        if download_year_zip(year):
            print(f"{year}: yearly archive")
            continue
        first, last = dt.date(year, 1, 1), min(dt.date(year, 12, 31), end)
        days = [first + dt.timedelta(d) for d in range((last - first).days + 1)]
        missing = [d for d in days if download_day(d) is None]
        print(f"{year}: {len(days) - len(missing)} daily files", end="")
        if missing:
            print(f" ({len(missing)} not available, first: {missing[0]})", end="")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    args = parser.parse_args()
    download_range(args.start_year)


if __name__ == "__main__":
    main()
