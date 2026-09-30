"""Offline, deterministic incident explanations behind a provider interface."""

from __future__ import annotations

from typing import Protocol

from src.models import IncidentExplanation, QualityResult


class ExplanationProvider(Protocol):
    """Interface that a future provider can implement without changing the pipeline."""

    def explain(self, result: QualityResult) -> IncidentExplanation: ...


PLAYBOOK: dict[str, dict[str, str]] = {
    "required_columns": {
        "why": "Downstream transforms and reporting may be incomplete or misleading.",
        "causes": "A publisher schema change, renamed headers, or a malformed source export.",
        "action": "Compare the source schema with the expected contract before accepting the run.",
    },
    "minimum_row_count": {
        "why": "A partial extract can understate incident volume and distort trends.",
        "causes": "An incomplete download, accidental filter, truncated file, or source outage.",
        "action": "Re-fetch the source and confirm its row count before replacing downstream data.",
    },
    "primary_identifier_uniqueness": {
        "why": "Duplicate identifiers can double-count delay incidents and break joins.",
        "causes": "Repeated input rows, an unstable key, or records appended more than once.",
        "action": (
            "Inspect duplicate keys, confirm their business fields, and fix the load boundary."
        ),
    },
    "critical_field_missingness": {
        "why": "Missing dates, locations, codes, or delay values weaken operational reporting.",
        "causes": "Source-system omissions, column drift, parsing errors, or incomplete entry.",
        "action": (
            "Profile missing rows by field and source period, then validate the upstream export."
        ),
    },
    "valid_numeric_ranges": {
        "why": "Extreme values can inflate delay totals and make prioritization unreliable.",
        "causes": "Unit changes, sentinel values, typing mistakes, or numeric parsing problems.",
        "action": "Quarantine out-of-range records and verify units with the source owner.",
    },
    "allowed_day_values": {
        "why": "Unexpected categories fragment weekday analysis and filters.",
        "causes": "Free-text entry, localization, spelling changes, or a shifted column.",
        "action": "Review new labels and update the contract only if they are legitimate.",
    },
    "date_parsing_validity": {
        "why": "Unparsed dates disappear from time-series analysis and freshness monitoring.",
        "causes": "A date-format change, invalid source values, or mixed locale conventions.",
        "action": (
            "Inspect failing raw dates and add a tested parser for any legitimate new format."
        ),
    },
    "data_freshness": {
        "why": "Stale data can hide recent service issues and mislead operational decisions.",
        "causes": "A delayed publisher update, failed download, old cache, or upstream outage.",
        "action": (
            "Check the official resource timestamp and retry ingestion before publishing metrics."
        ),
    },
    "duplicate_row_detection": {
        "why": "Repeated records can overstate incident counts and total delay minutes.",
        "causes": "Overlapping files, append retries, source duplication, or an incorrect join.",
        "action": "Trace duplicates to their source file and correct the append or join logic.",
    },
    "row_count_change": {
        "why": "A sudden volume drop may indicate missing periods or a partial source extract.",
        "causes": "Truncation, upstream filters, late publication, or a changed resource boundary.",
        "action": "Compare date coverage and source file size with the latest healthy run.",
    },
    "delay_distribution_anomaly": {
        "why": "A sharp shift can distort service-reliability trends and alert thresholds.",
        "causes": "Real disruption, extreme source values, a unit change, or altered sampling.",
        "action": "Inspect the largest delays and compare the same period in the source data.",
    },
}


class DeterministicExplanationProvider:
    """Template-based explanations that are reproducible and require no network call."""

    def explain(self, result: QualityResult) -> IncidentExplanation:
        guidance = PLAYBOOK.get(
            result.check_name,
            {
                "why": "The observed data no longer meets its documented quality contract.",
                "causes": "A source change, ingestion issue, or unexpected operational event.",
                "action": "Inspect the affected records and validate the source before publishing.",
            },
        )
        severity = "high" if result.status == "failed" else "medium"
        title = result.check_name.replace("_", " ").title()
        summary = (
            f"{severity.title()} severity: {title} is {result.status}. "
            f"{result.observed_value}; expected {result.expected_threshold}."
        )
        return IncidentExplanation(
            check_name=result.check_name,
            severity=severity,
            title=title,
            what_changed=result.explanation,
            why_it_matters=guidance["why"],
            likely_causes=guidance["causes"],
            recommended_action=guidance["action"],
            summary=summary,
        )


def explain_incidents(
    results: list[QualityResult], provider: ExplanationProvider | None = None
) -> list[IncidentExplanation]:
    """Explain warnings and failures only; passing checks do not create incidents."""

    active_provider = provider or DeterministicExplanationProvider()
    return [active_provider.explain(result) for result in results if result.status != "passed"]
