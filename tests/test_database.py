from __future__ import annotations

from src.database import (
    connection,
    get_clean_data,
    get_incidents,
    get_latest_run,
    get_quality_results,
    latest_healthy_baseline,
)
from src.pipeline import run_pipeline


def test_database_persists_run_results_and_clean_snapshot(tmp_path, healthy_ingest, fixed_now):
    database = tmp_path / "trustlayer.duckdb"
    summary = run_pipeline(
        db_path=database,
        ingest_result=healthy_ingest,
        now=fixed_now,
    )

    latest = get_latest_run(database)
    quality = get_quality_results(database, summary.run_id)
    clean = get_clean_data(database)

    assert latest is not None
    assert latest["run_id"] == summary.run_id
    assert len(quality) == 11
    assert len(clean) == 80
    assert get_incidents(database, summary.run_id).empty


def test_simulated_run_keeps_history_and_is_excluded_from_baseline(
    tmp_path, healthy_ingest, fixed_now
):
    database = tmp_path / "trustlayer.duckdb"
    healthy = run_pipeline(db_path=database, ingest_result=healthy_ingest, now=fixed_now)
    broken = run_pipeline(
        db_path=database,
        ingest_result=healthy_ingest,
        now=fixed_now.replace(minute=1),
        simulate=True,
    )

    baseline = latest_healthy_baseline(database)
    with connection(database, read_only=True) as db:
        run_count = db.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]

    assert run_count == 2
    assert baseline is not None and baseline["run_id"] == healthy.run_id
    assert broken.failed_count >= 8
    assert not get_incidents(database, broken.run_id).empty
