"""Unit tests for Baseline A (Grid-Only) and Baseline B (Rule-Based Battery)."""

import pandas as pd

from src.battery.rule_based import (
    run_grid_only_baseline,
    run_rule_based_battery_baseline,
)


def test_grid_only_baseline_deterministic():
    """Verify Grid-Only baseline strictly obeys energy balance and definitions."""
    dates = pd.date_range("2024-01-01", periods=10, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "load_kw": [100.0, 100.0, 100.0, 100.0, 100.0, 50.0, 50.0, 50.0, 50.0, 50.0],
            "solar_kw": [0.0, 20.0, 100.0, 150.0, 200.0, 0.0, 50.0, 80.0, 100.0, 0.0],
            "price_eur_kwh": [0.10] * 10,
        },
        index=dates,
    )

    res, metrics = run_grid_only_baseline(df)

    assert metrics["max_balance_error_kw"] < 1e-6
    # When solar is 0, grid import = 100
    assert res.loc[dates[0], "grid_import_kw"] == 100.0
    assert res.loc[dates[0], "curtailment_kw"] == 0.0

    # When solar is 200 and load is 100, grid import = 0, curtailment = 100
    assert res.loc[dates[4], "grid_import_kw"] == 0.0
    assert res.loc[dates[4], "curtailment_kw"] == 100.0


def test_rule_based_battery_boundary_conditions():
    """Verify Rule-Based Battery respects SOC limits, charge/discharge power limits, and energy balance."""
    dates = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    # Alternating heavy surplus and heavy deficit
    df = pd.DataFrame(
        {
            "load_kw": [100.0, 100.0, 100.0, 500.0, 500.0, 500.0],
            "solar_kw": [600.0, 600.0, 600.0, 0.0, 0.0, 0.0],
            "price_eur_kwh": [0.05, 0.05, 0.05, 0.20, 0.20, 0.20],
        },
        index=dates,
    )

    capacity = 1000.0
    max_charge = 200.0
    max_discharge = 200.0
    min_soc = 0.20
    max_soc = 0.80

    res, metrics = run_rule_based_battery_baseline(
        df,
        capacity_kwh=capacity,
        max_charge_kw=max_charge,
        max_discharge_kw=max_discharge,
        min_soc=min_soc,
        max_soc=max_soc,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
        initial_soc=0.50,
    )

    # 1. Energy balance
    assert metrics["max_balance_error_kw"] < 1e-6

    # 2. SOC bounds
    assert (res["soc"] >= min_soc - 1e-6).all()
    assert (res["soc"] <= max_soc + 1e-6).all()

    # 3. Power bounds
    assert (res["battery_charge_kw"] <= max_charge + 1e-6).all()
    assert (res["battery_discharge_kw"] <= max_discharge + 1e-6).all()

    # 4. Simultaneous charge and discharge never occurs
    assert ((res["battery_charge_kw"] > 0) & (res["battery_discharge_kw"] > 0)).sum() == 0
