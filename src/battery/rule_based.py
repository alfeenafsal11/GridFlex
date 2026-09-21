"""Deterministic baseline controllers: Grid-Only (Baseline A) and Rule-Based Battery (Baseline B)."""

from typing import Any

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("battery.rule_based")


def run_grid_only_baseline(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Simulate Baseline A: Grid-only system without battery storage."""
    res = pd.DataFrame(index=df.index)
    res["load_kw"] = df["load_kw"].values
    res["solar_kw"] = df["solar_kw"].values
    price_kwh = df["price_eur_kwh"].values if "price_eur_kwh" in df.columns else np.zeros(len(df))
    res["price_eur_kwh"] = price_kwh

    # Direct consumption meets load up to solar generation
    res["direct_solar_kw"] = np.minimum(res["load_kw"], res["solar_kw"])
    res["battery_charge_kw"] = 0.0
    res["battery_discharge_kw"] = 0.0
    res["soc"] = 0.0

    # Grid import supplies residual deficit
    res["grid_import_kw"] = np.maximum(0.0, res["load_kw"] - res["solar_kw"])

    # Surplus renewable is curtailed
    res["curtailment_kw"] = np.maximum(0.0, res["solar_kw"] - res["load_kw"])

    # Validate exact energy balance
    balance_error = np.abs(
        res["load_kw"] - (res["solar_kw"] + res["grid_import_kw"] - res["curtailment_kw"])
    )
    if (balance_error > 1e-5).any():
        max_err = balance_error.max()
        raise ValueError(f"Grid-only energy balance violation! Max error: {max_err:.6e} kW")

    # Metrics
    total_grid_kwh = float(res["grid_import_kw"].sum())
    total_curt_kwh = float(res["curtailment_kw"].sum())
    total_solar_kwh = float(res["solar_kw"].sum())
    total_load_kwh = float(res["load_kw"].sum())
    peak_grid_kw = float(res["grid_import_kw"].max())
    total_cost_eur = float((res["grid_import_kw"] * res["price_eur_kwh"]).sum())
    renewable_utilisation = 1.0 - (total_curt_kwh / total_solar_kwh if total_solar_kwh > 0 else 0.0)

    metrics = {
        "system": "Grid-Only (Baseline A)",
        "total_demand_kwh": total_load_kwh,
        "total_solar_kwh": total_solar_kwh,
        "total_grid_import_kwh": total_grid_kwh,
        "peak_grid_import_kw": peak_grid_kw,
        "total_curtailment_kwh": total_curt_kwh,
        "renewable_utilisation": renewable_utilisation,
        "total_cost_eur": total_cost_eur,
        "battery_throughput_kwh": 0.0,
        "max_balance_error_kw": float(balance_error.max()),
    }

    return res, metrics


def run_rule_based_battery_baseline(
    df: pd.DataFrame,
    capacity_kwh: float = 5000.0,
    max_charge_kw: float = 1250.0,
    max_discharge_kw: float = 1250.0,
    min_soc: float = 0.10,
    max_soc: float = 0.90,
    charge_efficiency: float = 0.95,
    discharge_efficiency: float = 0.95,
    initial_soc: float = 0.50,
    dt_hours: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Simulate Baseline B: Greedy heuristic rule-based battery controller."""
    n = len(df)
    load = df["load_kw"].to_numpy()
    solar = df["solar_kw"].to_numpy()
    price = df["price_eur_kwh"].to_numpy() if "price_eur_kwh" in df.columns else np.zeros(n)

    soc_arr = np.zeros(n)
    charge_kw = np.zeros(n)
    discharge_kw = np.zeros(n)
    grid_import_kw = np.zeros(n)
    curtailment_kw = np.zeros(n)

    current_soc = initial_soc

    for t in range(n):
        soc_arr[t] = current_soc
        p_load = load[t]
        p_solar = solar[t]

        if p_solar >= p_load:
            # Surplus condition: charge battery with excess solar
            surplus = p_solar - p_load
            # Max power battery can absorb without exceeding max_soc
            energy_room_kwh = (max_soc - current_soc) * capacity_kwh
            max_p_charge_energy = energy_room_kwh / (charge_efficiency * dt_hours)
            p_charge = min(surplus, max_charge_kw, max(0.0, max_p_charge_energy))

            charge_kw[t] = p_charge
            discharge_kw[t] = 0.0
            curtailment_kw[t] = surplus - p_charge
            grid_import_kw[t] = 0.0

            # Update SOC
            delta_soc = (p_charge * dt_hours * charge_efficiency) / capacity_kwh
            current_soc = min(max_soc, current_soc + delta_soc)

        else:
            # Deficit condition: discharge battery to supply unmet load
            deficit = p_load - p_solar
            # Max power battery can deliver without dropping below min_soc
            energy_avail_kwh = (current_soc - min_soc) * capacity_kwh
            max_p_discharge_energy = (energy_avail_kwh * discharge_efficiency) / dt_hours
            p_discharge = min(deficit, max_discharge_kw, max(0.0, max_p_discharge_energy))

            charge_kw[t] = 0.0
            discharge_kw[t] = p_discharge
            curtailment_kw[t] = 0.0
            grid_import_kw[t] = deficit - p_discharge

            # Update SOC
            delta_soc = (p_discharge * dt_hours) / (discharge_efficiency * capacity_kwh)
            current_soc = max(min_soc, current_soc - delta_soc)

    res = pd.DataFrame(index=df.index)
    res["load_kw"] = load
    res["solar_kw"] = solar
    res["price_eur_kwh"] = price
    res["soc"] = soc_arr
    res["battery_charge_kw"] = charge_kw
    res["battery_discharge_kw"] = discharge_kw
    res["grid_import_kw"] = grid_import_kw
    res["curtailment_kw"] = curtailment_kw

    # Energy balance check:
    # load = solar + grid_import + discharge - charge - curtailment
    balance = solar + grid_import_kw + discharge_kw - charge_kw - curtailment_kw
    balance_error = np.abs(load - balance)
    if (balance_error > 1e-5).any():
        max_err = balance_error.max()
        raise ValueError(f"Rule-based battery energy balance violation! Max error: {max_err:.6e} kW")

    # Metrics
    total_grid_kwh = float(grid_import_kw.sum() * dt_hours)
    total_curt_kwh = float(curtailment_kw.sum() * dt_hours)
    total_solar_kwh = float(solar.sum() * dt_hours)
    total_load_kwh = float(load.sum() * dt_hours)
    peak_grid_kw = float(grid_import_kw.max())
    total_cost_eur = float((grid_import_kw * price).sum() * dt_hours)
    renewable_utilisation = 1.0 - (total_curt_kwh / total_solar_kwh if total_solar_kwh > 0 else 0.0)
    throughput_kwh = float((charge_kw + discharge_kw).sum() * dt_hours)

    metrics = {
        "system": "Rule-Based Battery (Baseline B)",
        "total_demand_kwh": total_load_kwh,
        "total_solar_kwh": total_solar_kwh,
        "total_grid_import_kwh": total_grid_kwh,
        "peak_grid_import_kw": peak_grid_kw,
        "total_curtailment_kwh": total_curt_kwh,
        "renewable_utilisation": renewable_utilisation,
        "total_cost_eur": total_cost_eur,
        "battery_throughput_kwh": throughput_kwh,
        "mean_soc": float(soc_arr.mean()),
        "min_soc": float(soc_arr.min()),
        "max_soc": float(soc_arr.max()),
        "max_balance_error_kw": float(balance_error.max()),
    }

    return res, metrics
