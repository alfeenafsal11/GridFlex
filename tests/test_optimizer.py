"""Unit tests for constrained Linear Programming optimizer."""

import numpy as np

from src.optimization.optimizer import BatteryLPOptimizer


def test_optimizer_feasibility_and_constraints():
    """Verify LP solver finds a feasible, energy-conserving schedule obeying bounds."""
    H = 24
    np.random.seed(42)
    load = np.random.uniform(1000, 2500, H)
    solar = np.random.uniform(0, 3000, H)
    price = np.random.uniform(0.02, 0.15, H)

    opt = BatteryLPOptimizer(
        capacity_kwh=5000.0,
        max_charge_kw=1250.0,
        max_discharge_kw=1250.0,
        min_soc=0.10,
        max_soc=0.90,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
    )

    res = opt.optimize(load_kw=load, solar_kw=solar, price_eur_kwh=price, initial_soc=0.50)

    assert res.success, f"Optimizer failed: {res.status_message}"
    assert res.max_balance_error_kw < 1e-5

    # Bounds
    assert (res.soc >= 0.10 - 1e-6).all()
    assert (res.soc <= 0.90 + 1e-6).all()
    assert (res.charge_kw >= -1e-6).all()
    assert (res.charge_kw <= 1250.0 + 1e-6).all()
    assert (res.discharge_kw >= -1e-6).all()
    assert (res.discharge_kw <= 1250.0 + 1e-6).all()
    assert (res.grid_import_kw >= -1e-6).all()
    assert (res.curtailment_kw >= -1e-6).all()

    # Peak grid import check
    assert res.peak_grid_kw >= float(np.max(res.grid_import_kw)) - 1e-6


def test_optimizer_price_arbitrage_behavior():
    """Verify optimizer charges during cheap hours and discharges during expensive hours."""
    H = 6
    # Constant load, zero solar
    load = np.array([500.0] * H)
    solar = np.array([0.0] * H)
    # Hours 0-2: cheap price (0.01 €/kWh); Hours 3-5: expensive price (0.50 €/kWh)
    price = np.array([0.01, 0.01, 0.01, 0.50, 0.50, 0.50])

    opt = BatteryLPOptimizer(
        capacity_kwh=2000.0,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
        alpha=1.0,
        beta=0.0,  # Focus on economic cost
        gamma=2.0,
        delta=0.001,
    )

    res = opt.optimize(load_kw=load, solar_kw=solar, price_eur_kwh=price, initial_soc=0.10)
    assert res.success

    # Battery should charge during cheap hours (0, 1, 2)
    assert res.charge_kw[:3].sum() > 0.0
    # Battery should discharge during expensive hours (3, 4, 5)
    assert res.discharge_kw[3:].sum() > 0.0
