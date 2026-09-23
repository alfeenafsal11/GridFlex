"""Unit test for artifact validation."""

from src.evaluation.validate_artifacts import (
    validate_canonical_results,
    validate_dashboard_code,
    validate_error_analysis,
    validate_figure_files,
)


def test_artifact_validation_all():
    """Verify that all canonical artifacts pass validation."""
    res = validate_canonical_results()
    assert "core_systems" in res

    err = validate_error_analysis()
    assert "forecast" in err

    validate_figure_files()
    validate_dashboard_code()
