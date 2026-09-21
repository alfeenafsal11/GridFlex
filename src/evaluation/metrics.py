"""Standardized energy systems evaluation metrics and comparative gap formulas."""

from typing import Any

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("evaluation.metrics")


def compute_system_metrics(
    df_sim: pd.DataFrame,
    system_name: str,
    dt_hours: float = 1.0,
) -> dict[str, Any]:
    """Compute primary system performance metrics from a simulation result DataFrame."""
    load = df_sim["load_kw"].to_numpy()
    solar = df_sim["solar_kw"].to_numpy()
    grid = df_sim["grid_import_kw"].to_numpy()
    curt = df_sim["curtailment_kw"].to_numpy()
    c_act = df_sim["battery_charge_kw"].to_numpy()
    d_act = df_sim["battery_discharge_kw"].to_numpy()
    soc = df_sim["soc"].to_numpy()
    price = df_sim["price_eur_kwh"].to_numpy()

    # Total energies (kWh)
    total_demand_kwh = float(np.sum(load) * dt_hours)
    total_solar_kwh = float(np.sum(solar) * dt_hours)
    total_grid_kwh = float(np.sum(grid) * dt_hours)
    total_curt_kwh = float(np.sum(curt) * dt_hours)
    throughput_kwh = float(np.sum(c_act + d_act) * dt_hours)

    # Peak grid import (kW)
    peak_grid_kw = float(np.max(grid))

    # Total cost (EUR)
    total_cost_eur = float(np.sum(grid * price) * dt_hours)

    # Renewable utilisation [0, 1]
    if total_solar_kwh > 0:
        renewable_utilisation = 1.0 - (total_curt_kwh / total_solar_kwh)
    else:
        renewable_utilisation = 1.0

    # Physical Balance and Constraints Check
    # Balance: load = solar + grid + discharge - charge - curtailment
    balance_error = np.abs(load - (solar + grid + d_act - c_act - curt))
    max_balance_err = float(np.max(balance_error))
    constraint_violations = int(np.sum(balance_error > 1e-5))

    return {
        "system": system_name,
        "total_demand_kwh": total_demand_kwh,
        "total_solar_kwh": total_solar_kwh,
        "total_grid_kwh": total_grid_kwh,
        "peak_grid_kw": peak_grid_kw,
        "total_curt_kwh": total_curt_kwh,
        "renewable_utilisation_pct": renewable_utilisation * 100.0,
        "total_cost_eur": total_cost_eur,
        "battery_throughput_kwh": throughput_kwh,
        "soc_mean": float(np.mean(soc)),
        "soc_min": float(np.min(soc)),
        "soc_max": float(np.max(soc)),
        "max_balance_error_kw": max_balance_err,
        "constraint_violations": constraint_violations,
    }


def compute_derived_comparative_metrics(
    baseline_metrics: dict[str, Any],
    eval_metrics: dict[str, Any],
) -> dict[str, float]:
    """Compute relative percentage improvements against a baseline system."""
    base_grid = baseline_metrics["total_grid_kwh"]
    eval_grid = eval_metrics["total_grid_kwh"]
    grid_reduction_pct = ((base_grid - eval_grid) / base_grid) * 100.0 if base_grid > 0 else 0.0

    base_peak = baseline_metrics["peak_grid_kw"]
    eval_peak = eval_metrics["peak_grid_kw"]
    peak_reduction_pct = ((base_peak - eval_peak) / base_peak) * 100.0 if base_peak > 0 else 0.0

    base_cost = baseline_metrics["total_cost_eur"]
    eval_cost = eval_metrics["total_cost_eur"]
    cost_savings_pct = ((base_cost - eval_cost) / base_cost) * 100.0 if base_cost > 0 else 0.0

    utilisation_diff_pp = eval_metrics["renewable_utilisation_pct"] - baseline_metrics["renewable_utilisation_pct"]

    return {
        "grid_reduction_pct": float(grid_reduction_pct),
        "peak_reduction_pct": float(peak_reduction_pct),
        "cost_savings_pct": float(cost_savings_pct),
        "utilisation_gain_pp": float(utilisation_diff_pp),
    }


def compute_oracle_gap(
    forecast_metrics: dict[str, Any],
    oracle_metrics: dict[str, Any],
) -> dict[str, float]:
    """Compute gap between deployable forecast-informed optimization and theoretical oracle upper bound."""
    # Cost gap: how much more cost does forecast-informed incur above oracle
    c_cost = forecast_metrics["total_cost_eur"]
    o_cost = oracle_metrics["total_cost_eur"]
    cost_gap_pct = ((c_cost - o_cost) / o_cost) * 100.0 if o_cost > 0 else 0.0

    # Grid import gap
    c_grid = forecast_metrics["total_grid_kwh"]
    o_grid = oracle_metrics["total_grid_kwh"]
    grid_gap_pct = ((c_grid - o_grid) / o_grid) * 100.0 if o_grid > 0 else 0.0

    # Peak gap
    c_peak = forecast_metrics["peak_grid_kw"]
    o_peak = oracle_metrics["peak_grid_kw"]
    peak_gap_kw = c_peak - o_peak

    return {
        "cost_gap_pct": float(cost_gap_pct),
        "grid_gap_pct": float(grid_gap_pct),
        "peak_gap_kw": float(peak_gap_kw),
    }
