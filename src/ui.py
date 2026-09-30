"""Reusable presentation helpers for TrustLayer's Measured Field interface."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

ACCENT_TEAL = "#5E8C85"
ACCENT_STONE = "#74766F"
STATUS_COLORS = {
    "passed_count": "#527A63",
    "warning_count": "#9B7042",
    "failed_count": "#A65359",
}
STATUS_PATTERNS = {
    "passed_count": "",
    "warning_count": "/",
    "failed_count": "x",
}


def _status_tone(status: str) -> str:
    normalized = status.lower()
    if normalized in {"healthy", "passed"}:
        return "healthy"
    if normalized in {"failed", "error"}:
        return "failed"
    return "warning"


def render_sidebar_brand() -> None:
    """Render the compact wordmark used in the navigation rail."""

    st.html(
        """
        <div class="tl-sidebar-brand">
          <strong>TrustLayer</strong>
          <span>Data reliability copilot</span>
        </div>
        """
    )


def render_sidebar_snapshot(latest: dict[str, Any], timestamp: str) -> None:
    """Render one restrained latest-run reference in the sidebar."""

    status = str(latest.get("status", "unknown"))
    tone = _status_tone(status)
    st.html(
        f"""
        <div class="tl-sidebar-snapshot">
          <span class="tl-meta-label">Latest run</span>
          <strong class="tl-status tl-status--{tone}">
            <i aria-hidden="true"></i>{html.escape(status.title())}
          </strong>
          <time>{html.escape(timestamp)}</time>
        </div>
        """
    )


def render_page_header(latest: dict[str, Any], timestamp: str) -> None:
    """Render a compact page header with useful run metadata."""

    status = str(latest.get("status", "unknown"))
    tone = _status_tone(status)
    mode = str(latest.get("mode", "healthy")).replace("_", " ").title()

    with st.container(key="tl-page-header"):
        st.title("TrustLayer", anchor=False)
        st.html(
            """
            <p class="tl-page-summary">
              Inspect the latest TTC data snapshot, its quality checks, and any
              issues that need review.
            </p>
            """
        )
        st.html(
            f"""
            <div class="tl-header-meta" role="list" aria-label="Latest run details">
              <div role="listitem">
                <span>Status</span>
                <strong class="tl-status tl-status--{tone}">
                  <i aria-hidden="true"></i>{html.escape(status.title())}
                </strong>
              </div>
              <div role="listitem">
                <span>Last run</span><strong>{html.escape(timestamp)}</strong>
              </div>
              <div role="listitem">
                <span>Mode</span><strong>{html.escape(mode)}</strong>
              </div>
            </div>
            """
        )


def section_heading(title: str, description: str) -> None:
    """Render the signature ruled heading for a major page section."""

    st.html(
        f"""
        <div class="tl-section-heading">
          <div>
            <h2>{html.escape(title)}</h2>
            <p>{html.escape(description)}</p>
          </div>
        </div>
        """
    )


def card_heading(title: str, description: str) -> None:
    """Render a compact heading for a bounded content panel."""

    st.html(
        f"""
        <div class="tl-panel-heading">
          <h3>{html.escape(title)}</h3>
          <p>{html.escape(description)}</p>
        </div>
        """
    )


def takeaway(text: str) -> None:
    """Add a plain-language chart readout."""

    st.html(f'<p class="tl-readout"><strong>Readout</strong><span>{html.escape(text)}</span></p>')


def incident_heading(title: str, severity: str, check_name: str) -> None:
    """Render an incident title with text and a redundant severity marker."""

    tone = "failed" if severity == "high" else "warning"
    st.html(
        f"""
        <div class="tl-incident-heading">
          <div>
            <h3>{html.escape(title)}</h3>
            <p>{html.escape(check_name.replace("_", " ").title())}</p>
          </div>
          <span class="tl-status tl-status--{tone}">
            <i aria-hidden="true"></i>{html.escape(severity.title())} severity
          </span>
        </div>
        """
    )


def style_figure(figure: Any, *, height: int, legend: bool = False) -> Any:
    """Apply compact, native-theme-friendly Plotly layout defaults."""

    figure.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 12, "b": 8},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        transition={"duration": 0},
        showlegend=legend,
    )
    figure.update_xaxes(zeroline=False, automargin=True)
    figure.update_yaxes(zeroline=False, automargin=True)
    if legend:
        figure.update_layout(
            legend={
                "orientation": "h",
                "y": 1.14,
                "x": 0,
                "title": None,
            }
        )
    return figure
