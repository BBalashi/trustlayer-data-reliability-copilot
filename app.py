"""Streamlit dashboard for TrustLayer: Data Reliability Copilot."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config import ATTRIBUTION, DATASET_PAGE_URL, LICENSE_URL, database_path
from src.database import (
    get_clean_data,
    get_incidents,
    get_last_healthy_run,
    get_latest_run,
    get_quality_results,
    get_run_history,
)
from src.ui import (
    ACCENT_STONE,
    ACCENT_TEAL,
    STATUS_COLORS,
    STATUS_PATTERNS,
    card_heading,
    incident_heading,
    render_page_header,
    render_sidebar_brand,
    render_sidebar_snapshot,
    section_heading,
    style_figure,
    takeaway,
)

st.set_page_config(
    page_title="TrustLayer · Data Reliability Copilot",
    page_icon=":material/fact_check:",
    layout="wide",
    initial_sidebar_state="expanded",
)

ASSET_DIR = Path(__file__).resolve().parent / "assets"
st.html(ASSET_DIR / "trustlayer.css")

CHART_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}


def _fingerprint(path: Path) -> str:
    if not path.exists():
        return "missing"
    stats = path.stat()
    return f"{stats.st_mtime_ns}:{stats.st_size}"


@st.cache_data(ttl=30, show_spinner=False)
def _load_core(db_file: str, fingerprint: str):  # noqa: ARG001
    return (
        get_latest_run(db_file),
        get_last_healthy_run(db_file),
        get_run_history(db_file),
        get_clean_data(db_file),
    )


@st.cache_data(ttl=30, show_spinner=False)
def _load_quality(db_file: str, fingerprint: str, run_id: str):  # noqa: ARG001
    return get_quality_results(db_file, run_id)


@st.cache_data(ttl=30, show_spinner=False)
def _load_incidents(db_file: str, fingerprint: str, run_id: str):  # noqa: ARG001
    return get_incidents(db_file, run_id)


def _format_timestamp(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M UTC")


def _run_selector(history: pd.DataFrame, *, key: str) -> str:
    options = history["run_id"].astype(str).tolist()
    labels = {
        str(row.run_id): (
            f"{_format_timestamp(row.completed_at)} · "
            f"{str(row.mode).replace('_', ' ')} · {str(row.status).title()}"
        )
        for row in history.itertuples()
    }
    return st.selectbox(
        "Run",
        options,
        format_func=lambda run_id: labels.get(run_id, run_id),
        key=key,
    )


def _metric_row(latest: dict[str, object]) -> None:
    """Render one primary score with quieter supporting measures."""

    failed = int(latest.get("failed_count", 0))
    warnings = int(latest.get("warning_count", 0))
    passed = int(latest.get("passed_count", 0))
    total_checks = passed + warnings + failed

    with st.container(key="tl-metric-layout"):
        primary, supporting = st.columns([1.05, 1.95], gap="large")
        with primary:
            with st.container(key="tl-metric-primary"):
                st.metric(
                    "Health score (0–100)",
                    f"{float(latest.get('health_score', 0)):.1f}",
                    help="Weighted result of the latest data-quality checks.",
                )
        with supporting:
            with st.container(key="tl-metrics-secondary"):
                details = st.columns(2, gap="medium")
                details[0].metric(
                    "Records in snapshot",
                    f"{int(latest.get('row_count', 0)):,}",
                    help="Clean records available in the latest snapshot.",
                )
                details[1].metric(
                    "Checks evaluated",
                    total_checks,
                    help="Quality rules evaluated in the latest run.",
                )

    with st.container(key="tl-check-summary"):
        checks = st.columns(3, gap="medium")
        checks[0].metric("Passed", passed)
        checks[1].metric("Warnings", warnings)
        checks[2].metric("Failed", failed)


def _run_alert(latest: dict[str, object]) -> None:
    failed = int(latest.get("failed_count", 0))
    warnings = int(latest.get("warning_count", 0))
    if failed:
        st.error(
            f"This run has {failed} failed check{'s' if failed != 1 else ''}. "
            "Open Incidents to review impact and next actions.",
            icon=":material/error:",
        )
    elif warnings:
        warning_word = "warnings need" if warnings != 1 else "warning needs"
        st.warning(
            f"No checks failed, but {warnings} {warning_word} review.",
            icon=":material/warning:",
        )
    else:
        st.success(
            "All quality checks passed. No active incidents were detected.",
            icon=":material/check_circle:",
        )


def _daily_incidents(clean: pd.DataFrame) -> pd.DataFrame:
    return (
        clean.dropna(subset=["service_date"])
        .groupby("service_date", as_index=False)
        .agg(incidents=("incident_id", "count"), delay_minutes=("min_delay", "sum"))
        .sort_values("service_date")
    )


def _render_volume_panel(clean: pd.DataFrame) -> None:
    with st.container(border=True, key="tl-panel-volume"):
        card_heading(
            "Delay incidents over time",
            "Daily incident count in the current snapshot.",
        )
        daily = _daily_incidents(clean)
        if daily.empty:
            st.info("No valid dates are available for the time-series chart.")
            return

        figure = px.area(
            daily,
            x="service_date",
            y="incidents",
            markers=True,
            labels={"service_date": "Service date", "incidents": "Delay incidents"},
            color_discrete_sequence=[ACCENT_TEAL],
        )
        figure.update_traces(
            line={"width": 2},
            fillcolor="rgba(94, 140, 133, 0.14)",
            hovertemplate="%{x|%b %d, %Y}<br>%{y:,} incidents<extra></extra>",
        )
        style_figure(figure, height=350)
        st.plotly_chart(
            figure,
            width="stretch",
            theme="streamlit",
            config=CHART_CONFIG,
        )

        busiest = daily.loc[daily["incidents"].idxmax()]
        busiest_date = pd.Timestamp(busiest["service_date"]).strftime("%b %d, %Y")
        takeaway(
            f"The busiest day was {busiest_date}, with "
            f"{int(busiest['incidents']):,} recorded delay incidents."
        )
        with st.expander("View chart data"):
            st.dataframe(daily, width="stretch", hide_index=True)


def _render_run_details(latest: dict[str, object], last_healthy: dict[str, object] | None) -> None:
    with st.container(key="tl-run-details"):
        card_heading(
            "Run details",
            "Source and last known healthy state.",
        )
        healthy_at = (
            _format_timestamp(last_healthy.get("completed_at"))
            if last_healthy
            else "Not yet established"
        )
        source_kind = str(latest.get("source_kind", "")).title()
        source_name = str(latest.get("source_name", ""))

        st.caption("Last healthy run")
        st.write(healthy_at)
        st.caption("Mode")
        st.write(str(latest.get("mode", "")).replace("_", " ").title())
        st.caption("Source")
        st.write(f"{source_kind} · {source_name}")


def _render_lines_panel(clean: pd.DataFrame) -> None:
    with st.container(border=True, key="tl-panel-lines"):
        card_heading(
            "Most affected lines",
            "Lines ranked by delay-incident count.",
        )
        by_line = (
            clean.dropna(subset=["line"])
            .groupby("line", as_index=False)["incident_id"]
            .count()
            .rename(columns={"incident_id": "incidents"})
            .nlargest(6, "incidents")
        )
        if by_line.empty:
            st.caption("No populated line values are available.")
            return

        chart = px.bar(
            by_line,
            x="incidents",
            y="line",
            orientation="h",
            labels={"incidents": "Incidents", "line": "Line"},
            color_discrete_sequence=[ACCENT_STONE],
            text="incidents",
        )
        chart.update_traces(
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x:,} incidents<extra></extra>",
        )
        chart.update_yaxes(categoryorder="total ascending", title=None)
        chart.update_xaxes(title=None)
        style_figure(chart, height=245)
        st.plotly_chart(
            chart,
            width="stretch",
            theme="streamlit",
            config=CHART_CONFIG,
        )
        leader = by_line.iloc[0]
        takeaway(
            f"{leader['line']} has the most incidents in this snapshot ({leader['incidents']:,})."
        )
        with st.expander("View chart data"):
            st.dataframe(by_line, width="stretch", hide_index=True)


def render_overview(
    latest: dict[str, object],
    last_healthy: dict[str, object] | None,
    clean: pd.DataFrame,
) -> None:
    section_heading(
        "Overview",
        "Latest data health, check outcomes, and delay volume.",
    )
    _metric_row(latest)
    _run_alert(latest)

    left, right = st.columns([1.9, 1], gap="large")
    with left:
        _render_volume_panel(clean)
    with right:
        _render_run_details(latest, last_healthy)
        _render_lines_panel(clean)


def _render_quality_trend(history: pd.DataFrame) -> None:
    with st.container(border=True, key="tl-panel-quality-trend"):
        card_heading(
            "Quality history",
            "Passed, warning, and failed checks for every completed run.",
        )
        chart_data = history.sort_values("completed_at")
        trend = px.bar(
            chart_data,
            x="completed_at",
            y=["passed_count", "warning_count", "failed_count"],
            color_discrete_map=STATUS_COLORS,
            labels={"value": "Checks", "completed_at": "Run time", "variable": "Status"},
        )
        names = {
            "passed_count": "Passed",
            "warning_count": "Warning",
            "failed_count": "Failed",
        }
        for trace in trend.data:
            source_name = str(trace.name)
            trace.update(
                name=names.get(source_name, source_name),
                marker_pattern_shape=STATUS_PATTERNS.get(source_name, ""),
                texttemplate="%{y}",
                textposition="inside",
                hovertemplate=(
                    f"{names.get(source_name, source_name)}: %{{y}}"
                    "<br>%{x|%b %d, %Y %H:%M}<extra></extra>"
                ),
            )
        trend.update_layout(barmode="stack")
        style_figure(trend, height=300, legend=True)
        st.plotly_chart(
            trend,
            width="stretch",
            theme="streamlit",
            config=CHART_CONFIG,
        )

        latest = chart_data.iloc[-1]
        takeaway(
            "The latest run recorded "
            f"{int(latest['passed_count'])} passed, "
            f"{int(latest['warning_count'])} warning, and "
            f"{int(latest['failed_count'])} failed checks."
        )
        with st.expander("View chart data"):
            st.dataframe(
                chart_data[["completed_at", "passed_count", "warning_count", "failed_count"]],
                width="stretch",
                hide_index=True,
            )


def render_quality(history: pd.DataFrame, db_file: str, fingerprint: str) -> None:
    section_heading(
        "Quality results",
        "Inspect observed values, thresholds, and outcomes for each completed run.",
    )

    with st.container(border=True, key="tl-panel-quality-filters"):
        card_heading(
            "Filters",
            "Choose a run, status, or check name.",
        )
        selected_run = _run_selector(history, key="quality_run")
        control_a, control_b = st.columns([1, 2], gap="medium")
        with control_a:
            statuses = st.multiselect(
                "Status",
                ["passed", "warning", "failed"],
                default=["passed", "warning", "failed"],
                format_func=str.title,
            )
        with control_b:
            search = st.text_input(
                "Find a check",
                placeholder="e.g. freshness or duplicate",
            )

    quality = _load_quality(db_file, fingerprint, selected_run)
    _render_quality_trend(history)

    with st.container(border=True, key="tl-panel-quality-table"):
        card_heading(
            "Check evidence",
            "Observed values are shown beside their acceptance criteria.",
        )
        filtered = quality[quality["status"].isin(statuses)].copy()
        if search:
            filtered = filtered[filtered["check_name"].str.contains(search, case=False, na=False)]
        if filtered.empty:
            st.info("No checks match the current filters.")
            return

        labels = {"passed": "✓ Passed", "warning": "! Warning", "failed": "× Failed"}
        filtered["status"] = filtered["status"].map(labels)
        filtered["check_name"] = filtered["check_name"].str.replace("_", " ").str.title()
        filtered = filtered.rename(
            columns={
                "status": "Status",
                "check_name": "Check",
                "observed_value": "Observed",
                "expected_threshold": "Expected",
                "explanation": "Explanation",
                "run_timestamp": "Evaluated at",
            }
        )
        st.dataframe(
            filtered,
            width="stretch",
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(width="small"),
                "Check": st.column_config.TextColumn(width="medium"),
                "Observed": st.column_config.TextColumn(width="medium"),
                "Expected": st.column_config.TextColumn(width="large"),
                "Explanation": st.column_config.TextColumn(width="large"),
                "Evaluated at": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
            },
        )


def render_incidents(history: pd.DataFrame, db_file: str, fingerprint: str) -> None:
    section_heading(
        "Incidents",
        "Review checks that need attention and the recommended next step.",
    )

    with st.container(border=True, key="tl-panel-incident-filters"):
        card_heading(
            "Filters",
            "Choose a run and one or more severity levels.",
        )
        selected_run = _run_selector(history, key="incident_run")
        severity = st.multiselect(
            "Severity",
            ["high", "medium"],
            default=["high", "medium"],
            format_func=str.title,
        )

    incidents = _load_incidents(db_file, fingerprint, selected_run)
    if incidents.empty:
        st.success(
            "No active quality incidents for this run. All checks passed.",
            icon=":material/check_circle:",
        )
        return

    incidents = incidents[incidents["severity"].isin(severity)]
    if incidents.empty:
        st.info("No incidents match the selected severity filter.")
        return

    high_count = int((incidents["severity"] == "high").sum())
    medium_count = int((incidents["severity"] == "medium").sum())
    with st.container(key="tl-incident-summary"):
        summary = st.columns(3, gap="medium")
        summary[0].metric("Visible incidents", len(incidents))
        summary[1].metric("High severity", high_count)
        summary[2].metric("Medium severity", medium_count)

    for index, incident in enumerate(incidents.itertuples(), start=1):
        key = f"tl-panel-incident-{incident.severity}-{index}"
        with st.container(border=True, key=key):
            incident_heading(incident.title, incident.severity, incident.check_name)
            st.write(incident.summary)
            one, two = st.columns(2, gap="large")
            with one:
                st.markdown("**What changed**")
                st.write(incident.what_changed)
                st.markdown("**Likely causes**")
                st.write(incident.likely_causes)
            with two:
                st.markdown("**Why it may matter**")
                st.write(incident.why_it_matters)
                st.markdown("**Recommended action**")
                st.write(incident.recommended_action)


def render_explorer(clean: pd.DataFrame) -> None:
    section_heading(
        "Data explorer",
        "Filter the cleaned snapshot and inspect the records behind the quality results.",
    )
    filtered = clean.copy()

    with st.container(border=True, key="tl-panel-explorer-filters"):
        card_heading(
            "Filters",
            "The data preview is capped at 500 rows; summary metrics use the full result.",
        )
        filter_a, filter_b, filter_c = st.columns(3, gap="medium")
        valid_dates = pd.to_datetime(clean["service_date"], errors="coerce").dropna()
        with filter_a:
            if valid_dates.empty:
                st.caption("Date filter unavailable")
            else:
                selected_dates = st.date_input(
                    "Service date range",
                    value=(valid_dates.min().date(), valid_dates.max().date()),
                    min_value=valid_dates.min().date(),
                    max_value=valid_dates.max().date(),
                )
                if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                    start, end = selected_dates
                    dates = pd.to_datetime(filtered["service_date"], errors="coerce")
                    filtered = filtered[dates.between(pd.Timestamp(start), pd.Timestamp(end))]
        with filter_b:
            lines = sorted(str(value) for value in clean["line"].dropna().unique())
            selected_lines = st.multiselect("Line", lines, default=[])
            if selected_lines:
                filtered = filtered[filtered["line"].isin(selected_lines)]
        with filter_c:
            stations = sorted(str(value) for value in clean["station"].dropna().unique())
            selected_stations = st.multiselect("Station", stations, default=[])
            if selected_stations:
                filtered = filtered[filtered["station"].isin(selected_stations)]

        delay_values = pd.to_numeric(clean["min_delay"], errors="coerce").dropna()
        if not delay_values.empty:
            floor = float(delay_values.min())
            ceiling = float(delay_values.max())
            if floor < ceiling:
                selected_delay = st.slider(
                    "Delay minutes",
                    min_value=floor,
                    max_value=ceiling,
                    value=(floor, ceiling),
                )
                delay = pd.to_numeric(filtered["min_delay"], errors="coerce")
                filtered = filtered[delay.between(*selected_delay)]

    with st.container(key="tl-explorer-summary"):
        metrics = st.columns(4, gap="medium")
        metrics[0].metric("Filtered records", f"{len(filtered):,}")
        metrics[1].metric(
            "Stations",
            f"{filtered['station'].nunique(dropna=True):,}",
        )
        metrics[2].metric(
            "Mean delay",
            f"{filtered['min_delay'].mean():.1f} min" if not filtered.empty else "—",
        )
        metrics[3].metric(
            "Total delay",
            f"{filtered['min_delay'].sum():,.0f} min" if not filtered.empty else "—",
        )

    with st.container(border=True, key="tl-panel-explorer-table"):
        card_heading(
            "Clean records",
            f"Showing {min(len(filtered), 500):,} of {len(filtered):,} matching rows.",
        )
        if filtered.empty:
            st.info("No records match the current filters.")
            return
        st.dataframe(
            filtered.head(500),
            width="stretch",
            hide_index=True,
            column_config={
                "service_date": st.column_config.DateColumn("Service date"),
                "event_timestamp": st.column_config.DatetimeColumn("Event time"),
                "min_delay": st.column_config.NumberColumn("Delay (min)", format="%.0f"),
                "min_gap": st.column_config.NumberColumn("Gap (min)", format="%.0f"),
            },
        )
        with st.expander("Summary statistics"):
            st.dataframe(
                filtered[["min_delay", "min_gap"]].describe().round(2),
                width="stretch",
            )


def _render_sidebar(latest: dict[str, object] | None) -> str:
    with st.sidebar:
        render_sidebar_brand()
        st.divider()
        st.caption("Pages")
        page = st.radio(
            "Navigate",
            ["Overview", "Quality Results", "Incidents", "Data Explorer"],
            label_visibility="collapsed",
        )

        if latest is not None:
            st.divider()
            render_sidebar_snapshot(
                latest,
                _format_timestamp(latest.get("completed_at")),
            )

        st.divider()
        if st.button(
            "Refresh data",
            icon=":material/refresh:",
            width="stretch",
        ):
            st.cache_data.clear()
            st.rerun()
        st.markdown(f"[TTC source dataset]({DATASET_PAGE_URL})")
        st.markdown(f"[Open Government Licence]({LICENSE_URL})")
        st.caption(ATTRIBUTION)
        st.caption("Theme: open ⋮ and choose System, Light, or Dark.")
    return page


db_path = database_path()
db_fingerprint = _fingerprint(db_path)
latest_run: dict[str, object] | None = None
healthy_run: dict[str, object] | None = None
run_history = pd.DataFrame()
cleaned = pd.DataFrame()
load_error: Exception | None = None

if db_path.exists():
    try:
        latest_run, healthy_run, run_history, cleaned = _load_core(str(db_path), db_fingerprint)
    except Exception as exc:  # pragma: no cover - displayed as a user-facing recovery state
        load_error = exc

page = _render_sidebar(latest_run)

if not db_path.exists():
    render_page_header(
        {"status": "unknown", "mode": "setup", "health_score": 0, "row_count": 0},
        "Not run yet",
    )
    section_heading(
        "Setup",
        "The interface is ready, but the local pipeline database has not been created yet.",
    )
    with st.container(border=True, key="tl-panel-setup"):
        card_heading("Run the healthy pipeline", "Execute this command from the project root.")
        st.code("python -m src.pipeline", language="powershell")
    st.stop()

if load_error is not None:
    st.error(f"The dashboard could not read the local DuckDB database: {load_error}")
    st.code("python -m src.pipeline", language="powershell")
    st.stop()

if latest_run is None or run_history.empty:
    st.info("The database exists but has no completed runs. Run `python -m src.pipeline`.")
    st.stop()

render_page_header(latest_run, _format_timestamp(latest_run.get("completed_at")))

if page == "Overview":
    render_overview(latest_run, healthy_run, cleaned)
elif page == "Quality Results":
    render_quality(run_history, str(db_path), db_fingerprint)
elif page == "Incidents":
    render_incidents(run_history, str(db_path), db_fingerprint)
else:
    render_explorer(cleaned)
