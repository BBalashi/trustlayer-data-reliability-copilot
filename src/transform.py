"""Schema normalization and deterministic transformation of TTC delay records."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime

import pandas as pd

from src.config import EXPECTED_SOURCE_COLUMNS

ALIASES = {
    "report_date": "date",
    "incident_date": "date",
    "min_delay": "min_delay",
    "min_gap": "min_gap",
    "direction": "bound",
    "location": "station",
    "incident": "code",
    "route": "line",
}


def normalize_column_name(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return ALIASES.get(normalized, normalized)


def _clean_text(series: pd.Series, *, title: bool = False, upper: bool = False) -> pd.Series:
    cleaned = series.astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA})
    if title:
        cleaned = cleaned.str.title()
    if upper:
        cleaned = cleaned.str.upper()
    return cleaned


def _identifier(row: pd.Series) -> str:
    # Source position is part of the surrogate key because the public data has no native ID.
    values = [
        row.get("raw_date"),
        row.get("event_timestamp"),
        row.get("station"),
        row.get("code"),
        row.get("line"),
        row.get("vehicle"),
        row.get("source_row_number"),
    ]
    canonical = "|".join("" if pd.isna(value) else str(value) for value in values)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def transform_delays(
    raw: pd.DataFrame,
    *,
    run_id: str,
    source_name: str,
    ingested_at: datetime,
) -> pd.DataFrame:
    """Normalize a raw TTC frame into the analytics schema without hiding bad values."""

    if raw.empty:
        raise ValueError("Cannot transform an empty dataset.")

    frame = raw.copy()
    frame.columns = [normalize_column_name(column) for column in frame.columns]
    frame = frame.loc[:, ~frame.columns.duplicated(keep="first")]

    # Missing columns are materialized so the quality layer can report them explicitly.
    for column in EXPECTED_SOURCE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    frame = frame.loc[:, list(EXPECTED_SOURCE_COLUMNS)].copy()
    frame["source_row_number"] = range(1, len(frame) + 1)
    frame["raw_date"] = frame["date"].astype("string")
    frame["service_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["date_parse_valid"] = frame["service_date"].notna()

    time_text = frame["time"].astype("string").fillna("00:00").str.strip()
    date_text = frame["service_date"].dt.strftime("%Y-%m-%d").astype("string")
    frame["event_timestamp"] = pd.to_datetime(
        date_text.str.cat(time_text, sep=" "), errors="coerce"
    )

    frame["day"] = _clean_text(frame["day"], title=True)
    frame["station"] = _clean_text(frame["station"], upper=True)
    frame["code"] = _clean_text(frame["code"], upper=True)
    frame["bound"] = _clean_text(frame["bound"], upper=True)
    frame["line"] = _clean_text(frame["line"], upper=True)
    frame["vehicle"] = _clean_text(frame["vehicle"])
    frame["min_delay"] = pd.to_numeric(frame["min_delay"], errors="coerce")
    frame["min_gap"] = pd.to_numeric(frame["min_gap"], errors="coerce")

    frame["run_id"] = run_id
    frame["source_name"] = source_name
    frame["ingested_at"] = ingested_at
    frame["incident_id"] = frame.apply(_identifier, axis=1)

    columns = [
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
    ]
    return frame.loc[:, columns].reset_index(drop=True)


def simulate_failures(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a separate, intentionally damaged copy for the incident demo."""

    if frame.empty:
        raise ValueError("Cannot simulate failures on an empty dataset.")

    broken = frame.copy(deep=True)
    # A material source drop drives the count-change check while retaining a usable UI preview.
    keep_rows = max(10, int(len(broken) * 0.30))
    broken = broken.head(keep_rows).copy()

    null_count = max(2, int(len(broken) * 0.30))
    invalid_count = max(2, int(len(broken) * 0.12))
    bad_day_count = max(2, int(len(broken) * 0.08))
    bad_date_count = max(2, int(len(broken) * 0.08))

    broken.loc[broken.index[:null_count], "station"] = pd.NA
    broken.loc[broken.index[:invalid_count], "min_delay"] = 9_999.0
    broken.loc[broken.index[:bad_day_count], "day"] = "Funday"
    broken.loc[broken.index[:bad_date_count], "raw_date"] = "not-a-date"
    broken.loc[broken.index[:bad_date_count], "service_date"] = pd.NaT
    broken.loc[broken.index[:bad_date_count], "event_timestamp"] = pd.NaT
    broken.loc[broken.index[:bad_date_count], "date_parse_valid"] = False

    valid_dates = broken["service_date"].notna()
    broken.loc[valid_dates, "service_date"] = broken.loc[
        valid_dates, "service_date"
    ] - pd.to_timedelta(730, unit="D")
    broken.loc[valid_dates, "event_timestamp"] = broken.loc[
        valid_dates, "event_timestamp"
    ] - pd.to_timedelta(730, unit="D")

    duplicate_count = max(2, int(len(broken) * 0.10))
    duplicates = broken.tail(duplicate_count).copy(deep=True)
    broken = pd.concat([broken, duplicates], ignore_index=True)
    return broken.reset_index(drop=True)
