"""Unit tests for feature engineering and temporal leakage verification."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.features.engineer import (
    build_direct_multi_horizon_targets,
    extract_calendar_features,
)
from src.features.leakage_check import run_perturbation_leakage_audit


def test_calendar_features():
    """Verify trigonometric properties and calendar bounds."""
    dates = pd.date_range("2024-01-01 00:00", periods=24, freq="1h", tz="UTC")
    cal = extract_calendar_features(dates)

    # Unit circle check: sin^2 + cos^2 == 1
    hour_circ = cal["hour_sin"] ** 2 + cal["hour_cos"] ** 2
    assert np.allclose(hour_circ, 1.0, atol=1e-6)

    dow_circ = cal["dow_sin"] ** 2 + cal["dow_cos"] ** 2
    assert np.allclose(dow_circ, 1.0, atol=1e-6)

    # Weekend flag
    assert set(cal["is_weekend"].unique()).issubset({0, 1})


def test_direct_multi_horizon_targets():
    """Verify targets strictly shift by -h steps."""
    dates = pd.date_range("2024-01-01", periods=50, freq="1h", tz="UTC")
    series = pd.Series(range(50), index=dates, name="test_series")

    targets = build_direct_multi_horizon_targets(series, horizons=24)
    assert targets.shape == (50, 24)

    # At t=0, target_h1 should be 1, target_h24 should be 24
    assert targets.iloc[0]["target_h1"] == 1.0
    assert targets.iloc[0]["target_h24"] == 24.0


def test_leakage_audit_on_processed_data():
    """Run perturbation leakage test on processed dataset."""
    data_path = Path("data/processed/gridflex_hourly.parquet")
    if not data_path.exists():
        return

    df = pd.read_parquet(data_path)
    audit = run_perturbation_leakage_audit(df, test_indices=[500, 2000, 5000])

    assert audit["violations"] == 0
    assert len(audit["details"]) == 3
    for detail in audit["details"]:
        assert detail["future_invariance_max_diff"] == 0.0
        assert detail["past_sensitivity_diff"] > 0.0
        assert detail["status"] == "PASSED"
