"""Unit tests for error analysis diagnostic functions."""

import numpy as np
import pandas as pd

from src.evaluation.error_analysis import (
    analyze_battery_dynamics,
    analyze_forecast_residuals,
    analyze_oracle_performance_gap,
)


def test_analyze_forecast_residuals():
    """Verify statistical properties calculation for forecast residuals."""
    times = pd.date_range("2024-01-01", periods=48, freq="h")
    df = pd.DataFrame(
        {
            "pred_load_h1": np.full(48, 105.0),
            "actual_load_h1": np.full(48, 100.0),
            "pred_solar_h1": np.full(48, 50.0),
            "actual_solar_h1": np.full(48, 50.0),
        },
        index=times,
    )
    res = analyze_forecast_residuals(df)
    assert "load_residual_stats" in res
    assert "solar_residual_stats" in res
    assert res["load_residual_stats"]["mean"] == 5.0
    assert res["solar_residual_stats"]["mean"] == 0.0
    assert len(res["diurnal_load_mae"]) == 24
    assert len(res["worst_load_days"]) <= 5


def test_analyze_battery_dynamics():
    """Verify battery dynamics and SOC saturation calculation."""
    times = pd.date_range("2024-01-01", periods=10, freq="h")
    sim_c = pd.DataFrame(
        {
            "soc": [0.10, 0.10, 0.50, 0.50, 0.90, 0.90, 0.50, 0.50, 0.10, 0.90],
        },
        index=times,
    )
    sim_d = sim_c.copy()
    res = analyze_battery_dynamics(sim_c, sim_d, min_soc=0.10, max_soc=0.90, tol=0.01)

    c_dyn = res["system_c_forecast"]
    assert c_dyn["depleted_hours"] == 3
    assert c_dyn["saturated_hours"] == 3
    assert c_dyn["intermediate_hours"] == 4
    assert c_dyn["depleted_pct"] == 30.0
    assert c_dyn["saturated_pct"] == 30.0


def test_analyze_oracle_performance_gap():
    """Verify oracle gap attribution diagnostics."""
    times = pd.date_range("2024-01-01", periods=5, freq="h")
    sim_c = pd.DataFrame(
        {
            "grid_import_kw": [100.0, 200.0, 300.0, 400.0, 500.0],
            "price": [0.10, 0.15, 0.20, 0.25, 0.30],
            "cost_eur": [10.0, 30.0, 60.0, 100.0, 150.0],
            "soc": [0.5, 0.5, 0.5, 0.5, 0.5],
        },
        index=times,
    )
    sim_d = pd.DataFrame(
        {
            "grid_import_kw": [100.0, 180.0, 280.0, 380.0, 480.0],
            "price": [0.10, 0.15, 0.20, 0.25, 0.30],
            "cost_eur": [10.0, 27.0, 56.0, 95.0, 144.0],
            "soc": [0.5, 0.5, 0.5, 0.5, 0.5],
        },
        index=times,
    )
    preds = pd.DataFrame(
        {
            "pred_load_h1": [100.0, 200.0, 300.0, 400.0, 500.0],
            "actual_load_h1": [100.0, 190.0, 290.0, 390.0, 490.0],
            "pred_solar_h1": [0.0, 0.0, 0.0, 0.0, 0.0],
            "actual_solar_h1": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=times,
    )
    res = analyze_oracle_performance_gap(sim_c, sim_d, preds)
    assert res["system_c_peak_kw"] == 500.0
    assert res["system_d_peak_kw"] == 480.0
    assert res["total_cost_gap_eur"] == (350.0 - 332.0)
