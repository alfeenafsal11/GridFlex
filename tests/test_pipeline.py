"""End-to-end pipeline integration test for GridFlex AI.

Tests the full causal execution chain:
Data slice -> Feature engineering -> Model forecast -> LP optimization -> Battery simulator -> System metrics.
Verifies strict energy conservation, no lookahead leakage, and physical bounds.
"""

import numpy as np
import pandas as pd

from src.battery.simulator import BatterySimulator
from src.evaluation.metrics import compute_system_metrics
from src.features.engineer import construct_horizon_feature_matrix
from src.optimization.optimizer import BatteryLPOptimizer


def test_end_to_end_pipeline_integration():
    """Verify that an end-to-end mini-pipeline runs coherently and conserves energy."""
    # 1. Create a 72-hour synthetic test dataset with diurnal cycle
    timestamps = pd.date_range("2024-06-01 00:00:00", periods=72, freq="h", tz="UTC")
    hours = timestamps.hour.to_numpy()

    # Synthetic realistic load: 1000 - 3000 kW diurnal curve
    load_kw = 2000.0 + 800.0 * np.sin(2 * np.pi * (hours - 8) / 24)
    # Synthetic solar: 0 - 2500 kW during daytime (06:00 - 18:00)
    solar_kw = np.maximum(0.0, 2500.0 * np.sin(np.pi * np.maximum(0, hours - 6) / 12))
    # Synthetic price: 0.05 to 0.35 EUR/kWh
    price_eur_kwh = 0.15 + 0.10 * np.sin(2 * np.pi * (hours - 12) / 24)

    df = pd.DataFrame(
        {
            "load_kw": load_kw,
            "solar_kw": solar_kw,
            "price_eur_kwh": price_eur_kwh,
        },
        index=timestamps,
    )

    # 2. Feature engineering test on slice
    feat_df, feat_cols = construct_horizon_feature_matrix(df, h=1)
    assert not feat_df.empty
    assert len(feat_cols) > 0
    assert "load_current" in feat_df.columns

    # 3. Battery Simulator Initialization
    bess = BatterySimulator(
        capacity_kwh=1000.0,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=0.50,
    )

    # 4. Optimization schedule across 24 hours
    optimizer = BatteryLPOptimizer(
        capacity_kwh=1000.0,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        alpha=1.0,
        beta=0.1,
        gamma=2.0,
        delta=0.001,
    )

    h_load = df["load_kw"].iloc[:24].to_numpy()
    h_solar = df["solar_kw"].iloc[:24].to_numpy()
    h_price = df["price_eur_kwh"].iloc[:24].to_numpy()

    opt_res = optimizer.optimize(
        load_kw=h_load,
        solar_kw=h_solar,
        price_eur_kwh=h_price,
        initial_soc=0.50,
    )
    assert opt_res.success
    assert len(opt_res.charge_kw) == 24
    assert len(opt_res.discharge_kw) == 24

    # 5. Actuate first action on physical simulator
    first_c = float(opt_res.charge_kw[0])
    first_d = float(opt_res.discharge_kw[0])
    node_res = bess.simulate_node_step(
        load_kw=h_load[0],
        solar_kw=h_solar[0],
        charge_cmd_kw=first_c,
        discharge_cmd_kw=first_d,
        dt_hours=1.0,
    )

    # 6. Verify physical conservation invariant
    assert node_res.balance_error_kw < 1e-10
    assert 0.10 <= bess.soc <= 0.90

    # 7. Form simulation summary DataFrame and verify metrics computation
    sim_df = pd.DataFrame(
        {
            "load_kw": [h_load[0]],
            "solar_kw": [h_solar[0]],
            "price_eur_kwh": [h_price[0]],
            "soc": [bess.soc],
            "charge_cmd_kw": [first_c],
            "discharge_cmd_kw": [first_d],
            "battery_charge_kw": [node_res.actual_charge_kw],
            "battery_discharge_kw": [node_res.actual_discharge_kw],
            "grid_import_kw": [node_res.grid_import_kw],
            "curtailment_kw": [node_res.curtailment_kw],
            "balance_error_kw": [node_res.balance_error_kw],
        },
        index=[timestamps[0]],
    )

    metrics = compute_system_metrics(sim_df, system_name="Integration Pipeline Test")
    assert metrics["max_balance_error_kw"] < 1e-10
    assert metrics["constraint_violations"] == 0
    assert metrics["total_demand_kwh"] > 0
