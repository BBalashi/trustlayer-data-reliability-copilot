from __future__ import annotations

from src.explain import DeterministicExplanationProvider, explain_incidents
from src.models import QualityResult


def test_deterministic_explanation_contains_all_business_fields(fixed_now):
    result = QualityResult(
        check_name="data_freshness",
        status="failed",
        observed_value="730 days old",
        expected_threshold="failure > 180 days",
        explanation="The newest service record is 730 days old.",
        run_timestamp=fixed_now,
    )
    provider = DeterministicExplanationProvider()

    first = provider.explain(result)
    second = provider.explain(result)

    assert first == second
    assert first.severity == "high"
    assert all(
        [
            first.what_changed,
            first.why_it_matters,
            first.likely_causes,
            first.recommended_action,
        ]
    )


def test_only_nonpassing_checks_become_incidents(fixed_now):
    passed = QualityResult("one", "passed", "ok", "ok", "fine", fixed_now)
    warning = QualityResult("two", "warning", "near", "ok", "review", fixed_now)

    incidents = explain_incidents([passed, warning])

    assert len(incidents) == 1
    assert incidents[0].severity == "medium"
