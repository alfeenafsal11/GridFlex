"""Unit tests for system metrics and derived comparative calculations."""

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    compute_derived_comparative_metrics,
    compute_oracle_gap,
    compute_system_metrics,
)


def test_system_metrics_calculation():
    """Verify primary metric formulas."""
    df_sim = pd.DataFrame(
        {
            "load_kw": [100.0, 100.0],
            "solar_kw": [50.0, 150.0],
            "grid_import_kw": [50.0, 0.0],
            "curtailment_kw": [0.0, 50.0],
            "battery_charge_kw": [0.0, 0.0],
            "battery_discharge_kw": [0.0, 0.0],
            "soc": [0.5, 0.5],
            "price_eur_kwh": [0.10, 0.10],
        }
    )

    m = compute_system_metrics(df_sim, system_name="TestSystem")
    assert m["total_demand_kwh"] == 200.0
    assert m["total_solar_kwh"] == 200.0
    assert m["total_grid_kwh"] == 50.0
    assert m["peak_grid_kw"] == 50.0
    assert m["total_curt_kwh"] == 50.0
    # Utilisation = (200 - 50) / 200 = 75.0%
    assert m["renewable_utilisation_pct"] == 75.0
    assert m["total_cost_eur"] == 5.0
    assert m["max_balance_error_kw"] < 1e-6
    assert m["constraint_violations"] == 0


def test_derived_comparative_metrics():
    """Verify relative reduction and gap calculations."""
    base = {
        "total_grid_kwh": 1000.0,
        "peak_grid_kw": 200.0,
        "total_cost_eur": 100.0,
        "renewable_utilisation_pct": 70.0,
    }
    eval_m = {
        "total_grid_kwh": 800.0,
        "peak_grid_kw": 150.0,
        "total_cost_eur": 80.0,
        "renewable_utilisation_pct": 85.0,
    }

    derived = compute_derived_comparative_metrics(base, eval_m)
    assert derived["grid_reduction_pct"] == 20.0
    assert derived["peak_reduction_pct"] == 25.0
    assert derived["cost_savings_pct"] == 20.0
    assert derived["utilisation_gain_pp"] == 15.0

    oracle = {
        "total_grid_kwh": 700.0,
        "peak_grid_kw": 120.0,
        "total_cost_eur": 70.0,
    }
    gap = compute_oracle_gap(eval_m, oracle)
    # Cost gap: (80 - 70) / 70 = 14.2857%
    assert np.isclose(gap["cost_gap_pct"], 10.0 / 70.0 * 100)
    assert gap["peak_gap_kw"] == 30.0
