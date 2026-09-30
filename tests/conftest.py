from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.ingest import IngestResult
from src.transform import transform_delays


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 9, 30, 12, 0, 0)


@pytest.fixture
def healthy_raw() -> pd.DataFrame:
    stations = [
        "BLOOR STATION",
        "UNION STATION",
        "KENNEDY STATION",
        "ST GEORGE STATION",
        "FINCH STATION",
    ]
    codes = ["MUSAN", "SUDP", "PUO", "MUIR", "TUSC"]
    lines = ["YU", "BD", "YU", "BD", "YU"]
    rows = []
    for index in range(80):
        date = pd.Timestamp("2026-09-01") + pd.to_timedelta(index // 4, unit="D")
        rows.append(
            {
                "Date": date.strftime("%Y-%m-%d"),
                "Time": f"{6 + (index % 16):02d}:{(index * 7) % 60:02d}",
                "Day": date.day_name(),
                "Station": stations[index % len(stations)],
                "Code": codes[index % len(codes)],
                "Min Delay": 2 + (index % 14),
                "Min Gap": 4 + (index % 18),
                "Bound": ["N", "S", "E", "W"][index % 4],
                "Line": lines[index % len(lines)],
                "Vehicle": str(5000 + index),
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def healthy_clean(healthy_raw: pd.DataFrame, fixed_now: datetime) -> pd.DataFrame:
    return transform_delays(
        healthy_raw,
        run_id="run_test_healthy",
        source_name="fixture.csv",
        ingested_at=fixed_now,
    )


@pytest.fixture
def healthy_ingest(healthy_raw: pd.DataFrame, fixed_now: datetime) -> IngestResult:
    return IngestResult(
        frame=healthy_raw,
        source_kind="fallback",
        source_url="https://example.invalid/fixture.csv",
        source_name="fixture.csv",
        retrieved_at=fixed_now,
        notice="Deterministic test fixture.",
    )
