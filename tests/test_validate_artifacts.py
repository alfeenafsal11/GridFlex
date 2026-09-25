"""Unit test for artifact validation."""

from src.evaluation.validate_artifacts import (
    validate_canonical_results,
    validate_dashboard_code,
    validate_error_analysis,
    validate_figure_files,
    validate_forecast_metrics,
)


def test_artifact_validation_all():
    """Verify that all canonical artifacts pass validation."""
    res = validate_canonical_results()
    assert "core_systems" in res

    err = validate_error_analysis()
    assert "forecast" in err
    assert "system_b_rule_based" in err["battery"]

    f_met = validate_forecast_metrics()
    assert "per_horizon" in f_met

    validate_figure_files()
    validate_dashboard_code()
