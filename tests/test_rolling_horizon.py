"""Unit tests for Receding-Horizon Model Predictive Control simulation."""

from pathlib import Path

import pandas as pd

from src.optimization.rolling_horizon import run_rolling_horizon_simulation


def test_rolling_horizon_smoke():
    """Verify rolling horizon simulation runs on test slice without violation."""
    preds_path = Path("data/processed/test_predictions.parquet")
    data_path = Path("data/processed/gridflex_hourly.parquet")
    if not preds_path.exists() or not data_path.exists():
        return

    df = pd.read_parquet(data_path)
    test_preds = pd.read_parquet(preds_path).iloc[:48]  # First 48 hours of test set

    sim_df, metrics = run_rolling_horizon_simulation(
        df=df,
        test_preds_df=test_preds,
        capacity_kwh=2000.0,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        mode="forecast",
    )

    assert len(sim_df) == 48
    assert metrics["max_balance_error_kw"] < 1e-5

    # Check SOC within limits
    assert (sim_df["soc"] >= 0.10 - 1e-6).all()
    assert (sim_df["soc"] <= 0.90 + 1e-6).all()

    # Check power ratings
    assert (sim_df["battery_charge_kw"] <= 500.0 + 1e-6).all()
    assert (sim_df["battery_discharge_kw"] <= 500.0 + 1e-6).all()
    assert (sim_df["grid_import_kw"] >= -1e-6).all()
    assert (sim_df["curtailment_kw"] >= -1e-6).all()


def test_rolling_horizon_oracle_mode():
    """Verify oracle mode runs cleanly."""
    preds_path = Path("data/processed/test_predictions.parquet")
    data_path = Path("data/processed/gridflex_hourly.parquet")
    if not preds_path.exists() or not data_path.exists():
        return

    df = pd.read_parquet(data_path)
    test_preds = pd.read_parquet(preds_path).iloc[:24]

    sim_df, metrics = run_rolling_horizon_simulation(
        df=df,
        test_preds_df=test_preds,
        capacity_kwh=2000.0,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        mode="oracle",
    )

    assert len(sim_df) == 24
    assert metrics["mode"] == "oracle"
    assert metrics["max_balance_error_kw"] < 1e-5
