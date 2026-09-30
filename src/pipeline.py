"""Command-line orchestration for TrustLayer's local data reliability pipeline."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.config import database_path, ensure_data_directories
from src.database import initialize_database, latest_healthy_baseline, persist_run
from src.explain import explain_incidents
from src.ingest import IngestResult, fetch_dataset
from src.models import PipelineSummary
from src.quality import health_score, run_quality_checks
from src.transform import normalize_column_name, simulate_failures, transform_delays


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def run_pipeline(
    *,
    db_path: Path | str | None = None,
    simulate: bool = False,
    force_refresh: bool = False,
    offline: bool = False,
    now: datetime | None = None,
    ingest_result: IngestResult | None = None,
) -> PipelineSummary:
    """Run ingestion through persistence and return a verified execution summary."""

    ensure_data_directories()
    target_db = Path(db_path) if db_path is not None else database_path()
    target_db.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(target_db)

    started_at = now or _utc_now()
    run_id = f"run_{started_at:%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}"
    ingested = ingest_result or fetch_dataset(
        force_refresh=force_refresh,
        offline=offline,
    )
    source_columns = {normalize_column_name(column) for column in ingested.frame.columns}
    frame = transform_delays(
        ingested.frame,
        run_id=run_id,
        source_name=ingested.source_name,
        ingested_at=ingested.retrieved_at,
    )

    baseline = latest_healthy_baseline(target_db, source_name=ingested.source_name)
    if simulate:
        frame = simulate_failures(frame)

    results = run_quality_checks(
        frame,
        timestamp=started_at,
        source_columns=source_columns,
        baseline=baseline,
    )
    incidents = explain_incidents(results)
    passed_count = sum(result.status == "passed" for result in results)
    warning_count = sum(result.status == "warning" for result in results)
    failed_count = sum(result.status == "failed" for result in results)
    status = "failed" if failed_count else "warning" if warning_count else "healthy"
    completed_at = _utc_now() if now is None else now

    summary = PipelineSummary(
        run_id=run_id,
        status=status,
        mode="simulated_failure" if simulate else "healthy",
        source_kind=ingested.source_kind,
        source_name=ingested.source_name,
        source_url=ingested.source_url,
        row_count=len(frame),
        health_score=health_score(results),
        passed_count=passed_count,
        warning_count=warning_count,
        failed_count=failed_count,
        started_at=started_at,
        completed_at=completed_at,
        notice=ingested.notice,
    )
    persist_run(
        target_db,
        summary=summary,
        frame=frame,
        results=results,
        incidents=incidents,
    )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest TTC delay data, evaluate quality, and persist the run in DuckDB."
    )
    parser.add_argument(
        "--simulate-failures",
        action="store_true",
        help="Damage an in-memory copy to demonstrate incidents; the cache stays untouched.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-query Toronto Open Data instead of using an existing local cache.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the local cache or bundled fallback without making a network request.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Optional DuckDB path, primarily useful for isolated verification runs.",
    )
    return parser


def _print_summary(summary: PipelineSummary) -> None:
    print("TrustLayer pipeline completed")
    print(f"  Run ID:       {summary.run_id}")
    print(f"  Mode:         {summary.mode}")
    print(f"  Source:       {summary.source_kind} | {summary.source_name}")
    print(f"  Records:      {summary.row_count:,}")
    print(f"  Health:       {summary.health_score:.1f}/100 ({summary.status})")
    print(
        "  Checks:       "
        f"{summary.passed_count} passed | "
        f"{summary.warning_count} warning | "
        f"{summary.failed_count} failed"
    )
    if summary.notice:
        print(f"  Note:         {summary.notice}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = run_pipeline(
            db_path=args.db_path,
            simulate=args.simulate_failures,
            force_refresh=args.force_refresh,
            offline=args.offline,
        )
    except Exception as exc:
        print(f"TrustLayer pipeline failed: {exc}", file=sys.stderr)
        return 1
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
