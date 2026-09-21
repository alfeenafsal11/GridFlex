"""Receding-horizon Model Predictive Control (MPC) simulation loop for battery dispatch."""

from typing import Any, Literal

import numpy as np
import pandas as pd

from src.battery.simulator import BatterySimulator
from src.optimization.optimizer import BatteryLPOptimizer
from src.utils.logger import get_logger

logger = get_logger("optimization.rolling_horizon")


def run_rolling_horizon_simulation(
    df: pd.DataFrame,
    test_preds_df: pd.DataFrame,
    capacity_kwh: float = 5000.0,
    max_charge_kw: float = 1250.0,
    max_discharge_kw: float = 1250.0,
    min_soc: float = 0.10,
    max_soc: float = 0.90,
    charge_efficiency: float = 0.95,
    discharge_efficiency: float = 0.95,
    initial_soc: float = 0.50,
    alpha: float = 1.0,
    beta: float = 0.5,
    gamma: float = 2.0,
    delta: float = 0.01,
    mode: Literal["forecast", "oracle", "persistence"] = "forecast",
    horizons: int = 24,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute receding-horizon MPC simulation over test dataset.
    
    Protocol at each decision timestep t:
    1. Extract 24-hour lookahead inputs based on mode:
       - 'forecast': LightGBM predictions (pred_load_lgbm_h1..h24, pred_solar_lgbm_h1..h24)
       - 'oracle': Actual future observations (actual_load_h1..h24, actual_solar_h1..h24)
       - 'persistence': Persistence predictions (pred_load_pers_h1..h24, pred_solar_pers_h1..h24)
    2. Solve 24-hour constrained LP starting from current physical battery state SOC(t).
    3. Extract ONLY the first control action (P_c^*, P_d^*).
    4. Actuate the physical BatterySimulator under ACTUAL conditions at timestep t.
    5. Advance time by 1 hour (t <- t + 1) and repeat.
    """
    logger.info("Initializing rolling-horizon simulation in mode='%s' across %d steps...", mode, len(test_preds_df))

    bess = BatterySimulator(
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        min_soc=min_soc,
        max_soc=max_soc,
        charge_efficiency=charge_efficiency,
        discharge_efficiency=discharge_efficiency,
        initial_soc=initial_soc,
    )

    optimizer = BatteryLPOptimizer(
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        min_soc=min_soc,
        max_soc=max_soc,
        charge_efficiency=charge_efficiency,
        discharge_efficiency=discharge_efficiency,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        delta=delta,
        dt_hours=1.0,
    )

    test_index = test_preds_df.index
    n_steps = len(test_index)

    # Output arrays
    soc_record = np.zeros(n_steps)
    charge_cmd_record = np.zeros(n_steps)
    discharge_cmd_record = np.zeros(n_steps)
    actual_charge_record = np.zeros(n_steps)
    actual_discharge_record = np.zeros(n_steps)
    grid_import_record = np.zeros(n_steps)
    curtailment_record = np.zeros(n_steps)
    balance_error_record = np.zeros(n_steps)

    actual_load_seq = np.zeros(n_steps)
    actual_solar_seq = np.zeros(n_steps)
    price_seq = np.zeros(n_steps)

    # Column name mappings
    h_indices = list(range(1, horizons + 1))
    if mode == "forecast":
        load_cols = [f"pred_load_lgbm_h{h}" for h in h_indices]
        solar_cols = [f"pred_solar_lgbm_h{h}" for h in h_indices]
    elif mode == "oracle":
        load_cols = [f"actual_load_h{h}" for h in h_indices]
        solar_cols = [f"actual_solar_h{h}" for h in h_indices]
    elif mode == "persistence":
        load_cols = [f"pred_load_pers_h{h}" for h in h_indices]
        solar_cols = [f"pred_solar_pers_h{h}" for h in h_indices]
    else:
        raise ValueError(f"Unknown mode '{mode}'")

    for i in range(n_steps):
        t_now = test_index[i]
        curr_soc = bess.soc
        soc_record[i] = curr_soc

        # Actual environment conditions at current hour (from target_h1 which is at t_now + 1h or direct index)
        p_load_actual = float(test_preds_df.iloc[i]["actual_load_h1"])
        p_solar_actual = float(test_preds_df.iloc[i]["actual_solar_h1"])
        actual_load_seq[i] = p_load_actual
        actual_solar_seq[i] = p_solar_actual

        # 24-hour ahead price window
        # Target timestamps are t_now + 1h .. t_now + 24h
        future_times = [t_now + pd.Timedelta(hours=h) for h in h_indices]
        price_window = df.loc[future_times, "price_eur_kwh"].to_numpy()
        price_seq[i] = price_window[0]

        # 24-hour ahead load & solar window
        load_window = test_preds_df.iloc[i][load_cols].to_numpy(dtype=float)
        solar_window = test_preds_df.iloc[i][solar_cols].to_numpy(dtype=float)

        # Solve constrained LP
        opt_res = optimizer.optimize(
            load_kw=load_window,
            solar_kw=solar_window,
            price_eur_kwh=price_window,
            initial_soc=curr_soc,
        )

        if not opt_res.success:
            logger.warning("Optimization failed at step %d (%s). Clamping commands to 0.", i, t_now)
            c_first, d_first = 0.0, 0.0
        else:
            # Receding horizon principle: Apply ONLY the first action
            c_first = float(opt_res.charge_kw[0])
            d_first = float(opt_res.discharge_kw[0])

        charge_cmd_record[i] = c_first
        discharge_cmd_record[i] = d_first

        # Actuate physical battery simulator under ACTUAL conditions
        node_res = bess.simulate_node_step(
            load_kw=p_load_actual,
            solar_kw=p_solar_actual,
            charge_cmd_kw=c_first,
            discharge_cmd_kw=d_first,
            dt_hours=1.0,
        )

        actual_charge_record[i] = node_res.actual_charge_kw
        actual_discharge_record[i] = node_res.actual_discharge_kw
        grid_import_record[i] = node_res.grid_import_kw
        curtailment_record[i] = node_res.curtailment_kw
        balance_error_record[i] = node_res.balance_error_kw

    # Assemble results DataFrame
    sim_df = pd.DataFrame(
        {
            "load_kw": actual_load_seq,
            "solar_kw": actual_solar_seq,
            "price_eur_kwh": price_seq,
            "soc": soc_record,
            "charge_cmd_kw": charge_cmd_record,
            "discharge_cmd_kw": discharge_cmd_record,
            "battery_charge_kw": actual_charge_record,
            "battery_discharge_kw": actual_discharge_record,
            "grid_import_kw": grid_import_record,
            "curtailment_kw": curtailment_record,
            "balance_error_kw": balance_error_record,
        },
        index=test_index,
    )

    # Compute Summary Metrics
    total_grid_kwh = float(grid_import_record.sum())
    peak_grid_kw = float(grid_import_record.max())
    total_curt_kwh = float(curtailment_record.sum())
    total_solar_kwh = float(actual_solar_seq.sum())
    total_load_kwh = float(actual_load_seq.sum())
    total_cost_eur = float((grid_import_record * price_seq).sum())
    renewable_utilisation = 1.0 - (total_curt_kwh / total_solar_kwh if total_solar_kwh > 0 else 0.0)
    throughput_kwh = float((actual_charge_record + actual_discharge_record).sum())

    metrics = {
        "mode": mode,
        "total_demand_kwh": total_load_kwh,
        "total_solar_kwh": total_solar_kwh,
        "total_grid_import_kwh": total_grid_kwh,
        "peak_grid_import_kw": peak_grid_kw,
        "total_curtailment_kwh": total_curt_kwh,
        "renewable_utilisation": renewable_utilisation,
        "total_cost_eur": total_cost_eur,
        "battery_throughput_kwh": throughput_kwh,
        "mean_soc": float(soc_record.mean()),
        "min_soc": float(soc_record.min()),
        "max_soc": float(soc_record.max()),
        "max_balance_error_kw": float(balance_error_record.max()),
    }

    logger.info(
        "Simulation Complete [%s]: Grid=%.2f MWh, Peak=%.2f kW, Curtailment=%.2f MWh, Util=%.2f%%, Cost=€%.2f",
        mode.upper(),
        total_grid_kwh / 1000.0,
        peak_grid_kw,
        total_curt_kwh / 1000.0,
        renewable_utilisation * 100,
        total_cost_eur,
    )

    return sim_df, metrics
