from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.pipeline import run_pipeline


def test_streamlit_app_smoke(tmp_path, healthy_ingest, fixed_now, monkeypatch):
    database = tmp_path / "dashboard.duckdb"
    run_pipeline(db_path=database, ingest_result=healthy_ingest, now=fixed_now)
    monkeypatch.setenv("TRUSTLAYER_DB_PATH", str(database))

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert not app.exception
    assert len(app.metric) >= 6
    assert any("Health score" in metric.label for metric in app.metric)
    assert [title.value for title in app.title] == ["TrustLayer"]
    assert app.sidebar.radio[0].options == [
        "Overview",
        "Quality Results",
        "Incidents",
        "Data Explorer",
    ]

    for page in ["Quality Results", "Incidents", "Data Explorer", "Overview"]:
        app.sidebar.radio[0].set_value(page)
        app.run()
        assert not app.exception


def test_streamlit_app_initializes_missing_database(
    tmp_path, healthy_ingest, fixed_now, monkeypatch
):
    database = tmp_path / "first-start.duckdb"
    pipeline_runner = run_pipeline

    def initialize_test_database(*, db_path, **_kwargs):
        return pipeline_runner(
            db_path=db_path,
            ingest_result=healthy_ingest,
            now=fixed_now,
        )

    monkeypatch.setenv("TRUSTLAYER_DB_PATH", str(database))
    monkeypatch.setattr("src.pipeline.run_pipeline", initialize_test_database)

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert database.exists()
    assert not app.exception
    assert any("Health score" in metric.label for metric in app.metric)
