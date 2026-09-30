"""DuckDB schema, atomic persistence, and read helpers for the dashboard."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.models import IncidentExplanation, PipelineSummary, QualityResult

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    execution_status VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    mode VARCHAR NOT NULL,
    source_kind VARCHAR NOT NULL,
    source_name VARCHAR NOT NULL,
    source_url VARCHAR,
    row_count BIGINT NOT NULL,
    health_score DOUBLE NOT NULL,
    passed_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    mean_delay DOUBLE,
    notice VARCHAR,
    summary_json VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_results (
    run_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    observed_value VARCHAR NOT NULL,
    expected_threshold VARCHAR NOT NULL,
    explanation VARCHAR NOT NULL,
    run_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (run_id, check_name)
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_key VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    what_changed VARCHAR NOT NULL,
    why_it_matters VARCHAR NOT NULL,
    likely_causes VARCHAR NOT NULL,
    recommended_action VARCHAR NOT NULL,
    summary VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS subway_delays_clean (
    run_id VARCHAR NOT NULL,
    incident_id VARCHAR NOT NULL,
    service_date DATE,
    event_timestamp TIMESTAMP,
    day VARCHAR,
    station VARCHAR,
    code VARCHAR,
    min_delay DOUBLE,
    min_gap DOUBLE,
    bound VARCHAR,
    line VARCHAR,
    vehicle VARCHAR,
    source_name VARCHAR NOT NULL,
    source_row_number BIGINT NOT NULL,
    raw_date VARCHAR,
    date_parse_valid BOOLEAN NOT NULL,
    ingested_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quality_run ON quality_results(run_id);
CREATE INDEX IF NOT EXISTS idx_incidents_run ON incidents(run_id);
CREATE INDEX IF NOT EXISTS idx_clean_run ON subway_delays_clean(run_id);
"""


@contextmanager
def connection(path: Path | str, *, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    database = duckdb.connect(str(path), read_only=read_only)
    try:
        yield database
    finally:
        database.close()


def initialize_database(path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as database:
        database.execute(SCHEMA_SQL)


def latest_healthy_baseline(
    path: Path | str, *, source_name: str | None = None
) -> dict[str, Any] | None:
    """Use production-quality runs only, so a failure demo never contaminates baselines."""

    if not Path(path).exists():
        return None
    query = """
            SELECT run_id, row_count, mean_delay, completed_at
            FROM pipeline_runs
            WHERE execution_status = 'completed'
              AND status = 'healthy'
              AND mode = 'healthy'
    """
    parameters: list[Any] = []
    if source_name is not None:
        query += " AND source_name = ?"
        parameters.append(source_name)
    query += """
            ORDER BY completed_at DESC
            LIMIT 1
    """
    with connection(path, read_only=True) as database:
        row = database.execute(query, parameters).fetchone()
    if row is None:
        return None
    return {
        "run_id": row[0],
        "row_count": row[1],
        "mean_delay": row[2],
        "completed_at": row[3],
    }


def persist_run(
    path: Path | str,
    *,
    summary: PipelineSummary,
    frame: pd.DataFrame,
    results: list[QualityResult],
    incidents: list[IncidentExplanation],
) -> None:
    """Replace the latest clean snapshot and append audit records in one transaction."""

    initialize_database(path)
    mean_delay = float(pd.to_numeric(frame["min_delay"], errors="coerce").mean())
    if pd.isna(mean_delay):
        mean_delay = 0.0

    with connection(path) as database:
        database.execute("BEGIN TRANSACTION")
        try:
            database.execute(
                """
                INSERT INTO pipeline_runs VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    summary.run_id,
                    summary.started_at,
                    summary.completed_at,
                    "completed",
                    summary.status,
                    summary.mode,
                    summary.source_kind,
                    summary.source_name,
                    summary.source_url,
                    summary.row_count,
                    summary.health_score,
                    summary.passed_count,
                    summary.warning_count,
                    summary.failed_count,
                    mean_delay,
                    summary.notice,
                    json.dumps(summary.to_dict(), default=str),
                ],
            )

            database.executemany(
                """
                INSERT INTO quality_results VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        summary.run_id,
                        result.check_name,
                        result.status,
                        result.observed_value,
                        result.expected_threshold,
                        result.explanation,
                        result.run_timestamp,
                    )
                    for result in results
                ],
            )

            if incidents:
                database.executemany(
                    """
                    INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            f"{summary.run_id}:{incident.check_name}",
                            summary.run_id,
                            incident.check_name,
                            incident.severity,
                            incident.title,
                            incident.what_changed,
                            incident.why_it_matters,
                            incident.likely_causes,
                            incident.recommended_action,
                            incident.summary,
                            summary.completed_at,
                        )
                        for incident in incidents
                    ],
                )

            database.execute("DELETE FROM subway_delays_clean")
            database.register("clean_frame", frame)
            database.execute(
                """
                INSERT INTO subway_delays_clean
                SELECT
                    run_id,
                    incident_id,
                    CAST(service_date AS DATE),
                    CAST(event_timestamp AS TIMESTAMP),
                    day,
                    station,
                    code,
                    CAST(min_delay AS DOUBLE),
                    CAST(min_gap AS DOUBLE),
                    bound,
                    line,
                    vehicle,
                    source_name,
                    CAST(source_row_number AS BIGINT),
                    raw_date,
                    CAST(date_parse_valid AS BOOLEAN),
                    CAST(ingested_at AS TIMESTAMP)
                FROM clean_frame
                """
            )
            database.unregister("clean_frame")
            database.execute("COMMIT")
        except Exception:
            database.execute("ROLLBACK")
            raise


def _query_frame(path: Path | str, query: str, parameters: list[Any] | None = None) -> pd.DataFrame:
    with connection(path, read_only=True) as database:
        return database.execute(query, parameters or []).fetchdf()


def get_latest_run(path: Path | str) -> dict[str, Any] | None:
    frame = _query_frame(
        path,
        "SELECT * FROM pipeline_runs ORDER BY completed_at DESC LIMIT 1",
    )
    return None if frame.empty else frame.iloc[0].to_dict()


def get_last_healthy_run(path: Path | str) -> dict[str, Any] | None:
    frame = _query_frame(
        path,
        """
        SELECT * FROM pipeline_runs
        WHERE execution_status = 'completed' AND status = 'healthy'
        ORDER BY completed_at DESC LIMIT 1
        """,
    )
    return None if frame.empty else frame.iloc[0].to_dict()


def get_run_history(path: Path | str, *, limit: int = 50) -> pd.DataFrame:
    return _query_frame(
        path,
        """
        SELECT run_id, completed_at, status, mode, source_kind, row_count,
               health_score, passed_count, warning_count, failed_count
        FROM pipeline_runs ORDER BY completed_at DESC LIMIT ?
        """,
        [limit],
    )


def get_quality_results(path: Path | str, run_id: str) -> pd.DataFrame:
    return _query_frame(
        path,
        """
        SELECT check_name, status, observed_value, expected_threshold,
               explanation, run_timestamp
        FROM quality_results
        WHERE run_id = ?
        ORDER BY CASE status WHEN 'failed' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                 check_name
        """,
        [run_id],
    )


def get_incidents(path: Path | str, run_id: str) -> pd.DataFrame:
    return _query_frame(
        path,
        """
        SELECT check_name, severity, title, what_changed, why_it_matters,
               likely_causes, recommended_action, summary, created_at
        FROM incidents
        WHERE run_id = ?
        ORDER BY CASE severity WHEN 'high' THEN 1 ELSE 2 END, check_name
        """,
        [run_id],
    )


def get_clean_data(path: Path | str) -> pd.DataFrame:
    return _query_frame(
        path,
        """
        SELECT incident_id, service_date, event_timestamp, day, station, code,
               min_delay, min_gap, bound, line, vehicle, source_name
        FROM subway_delays_clean
        ORDER BY service_date DESC NULLS LAST, event_timestamp DESC NULLS LAST
        """,
    )
