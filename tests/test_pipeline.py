from __future__ import annotations

import hashlib

from src.database import get_latest_run, get_run_history
from src.pipeline import run_pipeline


def test_healthy_failure_restore_workflow(tmp_path, healthy_ingest, fixed_now):
    database = tmp_path / "trustlayer.duckdb"

    first = run_pipeline(db_path=database, ingest_result=healthy_ingest, now=fixed_now)
    broken = run_pipeline(
        db_path=database,
        ingest_result=healthy_ingest,
        now=fixed_now.replace(minute=1),
        simulate=True,
    )
    restored = run_pipeline(
        db_path=database,
        ingest_result=healthy_ingest,
        now=fixed_now.replace(minute=2),
    )

    assert first.status == "healthy"
    assert broken.status == "failed"
    assert restored.status == "healthy"
    assert len(get_run_history(database)) == 3
    assert get_latest_run(database)["run_id"] == restored.run_id


def test_simulation_does_not_mutate_ingested_frame(tmp_path, healthy_ingest, fixed_now):
    before = hashlib.sha256(healthy_ingest.frame.to_csv(index=False).encode("utf-8")).hexdigest()

    run_pipeline(
        db_path=tmp_path / "trustlayer.duckdb",
        ingest_result=healthy_ingest,
        now=fixed_now,
        simulate=True,
    )
    after = hashlib.sha256(healthy_ingest.frame.to_csv(index=False).encode("utf-8")).hexdigest()

    assert before == after
