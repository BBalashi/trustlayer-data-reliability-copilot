"""Application configuration and documented data-quality thresholds."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_DIR = DATA_DIR / "sample"
DEFAULT_DB_PATH = DATA_DIR / "trustlayer.duckdb"
CACHE_SAMPLE_PATH = CACHE_DIR / "ttc_subway_delays_sample.csv"
CACHE_METADATA_PATH = CACHE_DIR / "ttc_subway_delays_sample.json"
FALLBACK_SAMPLE_PATH = SAMPLE_DIR / "ttc_subway_delays_fallback.csv"

DATASET_NAME = "TTC Subway Delay Data"
DATASET_PAGE_URL = "https://open.toronto.ca/dataset/ttc-subway-delay-data/"
DATASET_PACKAGE_ID = "ttc-subway-delay-data"
DATASET_API_URL = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
    f"package_show?id={DATASET_PACKAGE_ID}"
)
LICENSE_NAME = "Open Government Licence – Toronto"
LICENSE_URL = "https://open.toronto.ca/open-data-licence/"
ATTRIBUTION = "Contains information licensed under the Open Government Licence – Toronto."

# Keep the demo quick and repository-friendly while retaining enough records for useful charts.
MAX_SAMPLE_ROWS = 5_000
MIN_ROW_COUNT = 50
CRITICAL_MISSING_WARNING_PCT = 1.0
CRITICAL_MISSING_FAILURE_PCT = 5.0
DUPLICATE_WARNING_PCT = 0.5
DUPLICATE_FAILURE_PCT = 2.0
MIN_DELAY_MIN = 0.0
MIN_DELAY_MAX = 500.0
MIN_GAP_MIN = 0.0
MIN_GAP_MAX = 600.0
FRESHNESS_WARNING_DAYS = 45
FRESHNESS_FAILURE_DAYS = 75
ROW_COUNT_WARNING_DROP_PCT = 20.0
ROW_COUNT_FAILURE_DROP_PCT = 40.0
DISTRIBUTION_WARNING_CHANGE_PCT = 50.0
DISTRIBUTION_FAILURE_CHANGE_PCT = 100.0

EXPECTED_SOURCE_COLUMNS = (
    "date",
    "time",
    "day",
    "station",
    "code",
    "min_delay",
    "min_gap",
    "bound",
    "line",
    "vehicle",
)

CLEAN_COLUMNS = (
    "run_id",
    "incident_id",
    "service_date",
    "event_timestamp",
    "day",
    "station",
    "code",
    "min_delay",
    "min_gap",
    "bound",
    "line",
    "vehicle",
    "source_name",
    "source_row_number",
    "raw_date",
    "date_parse_valid",
    "ingested_at",
)

ALLOWED_DAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}


def database_path() -> Path:
    """Return the configured database path, allowing isolated test/demo databases."""

    override = os.getenv("TRUSTLAYER_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


def ensure_data_directories() -> None:
    """Create runtime data directories without touching bundled source data."""

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    database_path().parent.mkdir(parents=True, exist_ok=True)
