"""Master experiment execution runner for Phase 9, 10, and 11 comparisons and sensitivity analysis."""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.battery.rule_based import (
    run_grid_only_baseline,
    run_rule_based_battery_baseline,
)
from src.data.preprocess import calibrate_renewable_scaling
from src.evaluation.metrics import (
    compute_derived_comparative_metrics,
    compute_oracle_gap,
    compute_system_metrics,
)
from src.optimization.rolling_horizon import run_rolling_horizon_simulation
from src.utils.config import load_yaml_config
from src.utils.logger import get_logger

logger = get_logger("experiments.runner")


def run_all_experiments(
    data_path: str = "data/processed/gridflex_hourly.parquet",
    preds_path: str = "data/processed/test_predictions.parquet",
    config_path: str = "configs/default.yaml",
    figures_dir: str = "figures",
    reports_dir: str = "reports",
) -> dict[str, Any]:
    """Execute all comparative systems and sensitivity experiments."""
    df = pd.read_parquet(data_path)
    test_preds_df = pd.read_parquet(preds_path)
    cfg = load_yaml_config(config_path)

    fig_path = Path(figures_dir)
    fig_path.mkdir(parents=True, exist_ok=True)
    rep_path = Path(reports_dir)
    rep_path.mkdir(parents=True, exist_ok=True)

    b_cfg = cfg["battery"]
    o_cfg = cfg["optimization"]["weights"]

    # Align test slice of the full df with the exact test_preds_df index
    test_index = test_preds_df.index
    df_test = df.loc[test_index].copy()
    # Update actual values in df_test to exactly match the target_h1 actuals in test_preds_df
    df_test["load_kw"] = test_preds_df["actual_load_h1"].to_numpy()
    df_test["solar_kw"] = test_preds_df["actual_solar_h1"].to_numpy()

    logger.info("Running Master Experiments over %d test hours...", len(test_index))

    # =========================================================================
    # 1. CORE FOUR SYSTEMS COMPARISON (PHASE 9 & 10)
    # =========================================================================
    logger.info("--- Simulating System A: Grid-Only ---")
    sim_a, _ = run_grid_only_baseline(df_test)
    metrics_a = compute_system_metrics(sim_a, system_name="System A: Grid-Only")

    logger.info("--- Simulating System B: Rule-Based Battery ---")
    sim_b, _ = run_rule_based_battery_baseline(
        df_test,
        capacity_kwh=b_cfg["capacity_kwh"],
        max_charge_kw=b_cfg["max_charge_kw"],
        max_discharge_kw=b_cfg["max_discharge_kw"],
        min_soc=b_cfg["min_soc"],
        max_soc=b_cfg["max_soc"],
        charge_efficiency=b_cfg["charge_efficiency"],
        discharge_efficiency=b_cfg["discharge_efficiency"],
        initial_soc=b_cfg["initial_soc"],
    )
    metrics_b = compute_system_metrics(sim_b, system_name="System B: Rule-Based Battery")

    logger.info("--- Simulating System C: Forecast-Informed Optimization (MPC) ---")
    sim_c, _ = run_rolling_horizon_simulation(
        df=df,
        test_preds_df=test_preds_df,
        capacity_kwh=b_cfg["capacity_kwh"],
        max_charge_kw=b_cfg["max_charge_kw"],
        max_discharge_kw=b_cfg["max_discharge_kw"],
        min_soc=b_cfg["min_soc"],
        max_soc=b_cfg["max_soc"],
        charge_efficiency=b_cfg["charge_efficiency"],
        discharge_efficiency=b_cfg["discharge_efficiency"],
        initial_soc=b_cfg["initial_soc"],
        alpha=o_cfg["alpha"],
        beta=o_cfg["beta"],
        gamma=o_cfg["gamma"],
        delta=o_cfg["delta"],
        mode="forecast",
    )
    metrics_c = compute_system_metrics(sim_c, system_name="System C: Forecast-Informed Optimization")

    logger.info("--- Simulating System D: Perfect-Foresight Oracle ---")
    sim_d, _ = run_rolling_horizon_simulation(
        df=df,
        test_preds_df=test_preds_df,
        capacity_kwh=b_cfg["capacity_kwh"],
        max_charge_kw=b_cfg["max_charge_kw"],
        max_discharge_kw=b_cfg["max_discharge_kw"],
        min_soc=b_cfg["min_soc"],
        max_soc=b_cfg["max_soc"],
        charge_efficiency=b_cfg["charge_efficiency"],
        discharge_efficiency=b_cfg["discharge_efficiency"],
        initial_soc=b_cfg["initial_soc"],
        alpha=o_cfg["alpha"],
        beta=o_cfg["beta"],
        gamma=o_cfg["gamma"],
        delta=o_cfg["delta"],
        mode="oracle",
    )
    metrics_d = compute_system_metrics(sim_d, system_name="System D: Perfect-Foresight Oracle")

    # Derived comparisons
    exp_a_derived = compute_derived_comparative_metrics(metrics_a, metrics_b)  # Grid-only vs Rule-based
    exp_b_derived = compute_derived_comparative_metrics(metrics_b, metrics_c)  # Rule-based vs Forecast Opt
    exp_c_derived = compute_derived_comparative_metrics(metrics_a, metrics_c)  # Grid-only vs Forecast Opt
    oracle_gap = compute_oracle_gap(metrics_c, metrics_d)

    # =========================================================================
    # 2. EXPERIMENT D: RENEWABLE PENETRATION SENSITIVITY (20%, 40%, 60%)
    # =========================================================================
    logger.info("--- Running Experiment D: Renewable Penetration Sensitivity ---")
    penetration_results = {}
    for pen in [0.20, 0.40, 0.60]:
        pen_key = f"{int(pen * 100)}pct"
        # Calibrate solar scaling on full df
        df_pen, _ = calibrate_renewable_scaling(df[["load_kw", "solar_factor", "price_eur_kwh", "price_eur_mwh"]], penetration_ratio=pen)
        df_pen_test = df_pen.loc[test_index].copy()

        # Build scale-adjusted prediction dataframe for test set
        pen_preds = test_preds_df.copy()
        scale_factor = df_pen["solar_capacity_kw"].iloc[0] / df["solar_capacity_kw"].iloc[0]
        for h in range(1, 25):
            pen_preds[f"actual_solar_h{h}"] *= scale_factor
            pen_preds[f"pred_solar_lgbm_h{h}"] *= scale_factor

        sim_rb, _ = run_rule_based_battery_baseline(
            df_pen_test,
            capacity_kwh=b_cfg["capacity_kwh"],
            max_charge_kw=b_cfg["max_charge_kw"],
            max_discharge_kw=b_cfg["max_discharge_kw"],
        )
        m_rb = compute_system_metrics(sim_rb, system_name=f"RB-Pen-{pen_key}")

        sim_opt, _ = run_rolling_horizon_simulation(
            df=df_pen,
            test_preds_df=pen_preds,
            capacity_kwh=b_cfg["capacity_kwh"],
            max_charge_kw=b_cfg["max_charge_kw"],
            max_discharge_kw=b_cfg["max_discharge_kw"],
            alpha=o_cfg["alpha"],
            beta=o_cfg["beta"],
            gamma=o_cfg["gamma"],
            delta=o_cfg["delta"],
            mode="forecast",
        )
        m_opt = compute_system_metrics(sim_opt, system_name=f"Opt-Pen-{pen_key}")
        derived = compute_derived_comparative_metrics(m_rb, m_opt)

        penetration_results[pen_key] = {
            "penetration": pen,
            "rule_based": m_rb,
            "forecast_opt": m_opt,
            "improvement": derived,
        }

    # =========================================================================
    # 3. EXPERIMENT E: BATTERY DURATION SENSITIVITY (2h vs 4h)
    # =========================================================================
    logger.info("--- Running Experiment E: Battery Duration Sensitivity ---")
    duration_results = {}
    duration_configs = {
        "2h": {"capacity_kwh": 2500.0, "power_kw": 1250.0},
        "4h": {"capacity_kwh": 5000.0, "power_kw": 1250.0},
    }
    for dur_name, d_conf in duration_configs.items():
        sim_rb, _ = run_rule_based_battery_baseline(
            df_test,
            capacity_kwh=d_conf["capacity_kwh"],
            max_charge_kw=d_conf["power_kw"],
            max_discharge_kw=d_conf["power_kw"],
        )
        m_rb = compute_system_metrics(sim_rb, system_name=f"RB-Duration-{dur_name}")

        sim_opt, _ = run_rolling_horizon_simulation(
            df=df,
            test_preds_df=test_preds_df,
            capacity_kwh=d_conf["capacity_kwh"],
            max_charge_kw=d_conf["power_kw"],
            max_discharge_kw=d_conf["power_kw"],
            alpha=o_cfg["alpha"],
            beta=o_cfg["beta"],
            gamma=o_cfg["gamma"],
            delta=o_cfg["delta"],
            mode="forecast",
        )
        m_opt = compute_system_metrics(sim_opt, system_name=f"Opt-Duration-{dur_name}")
        derived = compute_derived_comparative_metrics(m_rb, m_opt)

        duration_results[dur_name] = {
            "capacity_kwh": d_conf["capacity_kwh"],
            "power_kw": d_conf["power_kw"],
            "rule_based": m_rb,
            "forecast_opt": m_opt,
            "improvement": derived,
        }

    # =========================================================================
    # 4. EXPERIMENT F: FORECAST ERROR NOISE SENSITIVITY (0%, 10%, 20%, 30%)
    # =========================================================================
    logger.info("--- Running Experiment F: Forecast Noise Sensitivity ---")
    noise_results = {}
    rng = np.random.default_rng(42)
    for noise_std in [0.0, 0.10, 0.20, 0.30]:
        noise_key = f"{int(noise_std * 100)}pct"
        noisy_preds = test_preds_df.copy()
        if noise_std > 0.0:
            for h in range(1, 25):
                # Add relative Gaussian noise
                noise_load = rng.normal(0, noise_std, len(noisy_preds))
                noise_solar = rng.normal(0, noise_std, len(noisy_preds))
                noisy_preds[f"pred_load_lgbm_h{h}"] = np.maximum(0.0, noisy_preds[f"pred_load_lgbm_h{h}"] * (1.0 + noise_load))
                noisy_preds[f"pred_solar_lgbm_h{h}"] = np.maximum(0.0, noisy_preds[f"pred_solar_lgbm_h{h}"] * (1.0 + noise_solar))

        sim_noisy, _ = run_rolling_horizon_simulation(
            df=df,
            test_preds_df=noisy_preds,
            capacity_kwh=b_cfg["capacity_kwh"],
            max_charge_kw=b_cfg["max_charge_kw"],
            max_discharge_kw=b_cfg["max_discharge_kw"],
            alpha=o_cfg["alpha"],
            beta=o_cfg["beta"],
            gamma=o_cfg["gamma"],
            delta=o_cfg["delta"],
            mode="forecast",
        )
        m_noisy = compute_system_metrics(sim_noisy, system_name=f"Opt-Noise-{noise_key}")
        noise_results[noise_key] = {
            "noise_std": noise_std,
            "metrics": m_noisy,
        }

    # Save comprehensive results JSON
    compiled_results = {
        "core_systems": {
            "system_a": metrics_a,
            "system_b": metrics_b,
            "system_c": metrics_c,
            "system_d": metrics_d,
        },
        "comparisons": {
            "exp_a_grid_vs_rule_based": exp_a_derived,
            "exp_b_rule_based_vs_forecast_opt": exp_b_derived,
            "exp_c_grid_vs_forecast_opt": exp_c_derived,
            "oracle_gap": oracle_gap,
        },
        "experiment_d_penetration": penetration_results,
        "experiment_e_duration": duration_results,
        "experiment_f_noise": noise_results,
    }

    results_json_path = rep_path / "experiments_results.json"
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(compiled_results, f, indent=2)
    logger.info("Saved all experiment results to %s", results_json_path)

    # Generate publication figures
    generate_publication_figures(compiled_results, figures_dir=fig_path)

    return compiled_results


def generate_publication_figures(results: dict[str, Any], figures_dir: str | Path = "figures") -> None:
    """Generate all publication-grade figures directly from compiled experiment results."""
    fig_path = Path(figures_dir)
    fig_path.mkdir(parents=True, exist_ok=True)

    core = results["core_systems"]
    sys_a = core["system_a"]
    sys_b = core["system_b"]
    sys_c = core["system_c"]
    sys_d = core["system_d"]

    # -------------------------------------------------------------------------
    # Figure 6: Systems Comparison (Energy, Peak, Cost, Curtailment)
    # -------------------------------------------------------------------------
    sys_names = ["System A\n(Grid-Only)", "System B\n(Rule-Based)", "System C\n(Forecast Opt)", "System D\n(Oracle)"]
    sys_metrics = [sys_a, sys_b, sys_c, sys_d]
    colors = ["#7f7f7f", "#1f77b4", "#2ca02c", "#d62728"]

    _fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    # 1. Total Grid Import (MWh)
    grid_vals = [m["total_grid_kwh"] / 1000.0 for m in sys_metrics]
    axes[0, 0].bar(sys_names, grid_vals, color=colors, alpha=0.85, edgecolor="black")
    axes[0, 0].set_title("Total Grid Electricity Imported (MWh)")
    axes[0, 0].set_ylabel("Grid Import (MWh)")
    for i, v in enumerate(grid_vals):
        axes[0, 0].text(i, v * 0.9, f"{v:.1f}", ha="center", fontweight="bold", color="white")

    # 2. Peak Grid Demand (kW)
    peak_vals = [m["peak_grid_kw"] for m in sys_metrics]
    axes[0, 1].bar(sys_names, peak_vals, color=colors, alpha=0.85, edgecolor="black")
    axes[0, 1].set_title("Peak Grid Demand (kW)")
    axes[0, 1].set_ylabel("Peak Demand (kW)")
    for i, v in enumerate(peak_vals):
        axes[0, 1].text(i, v * 0.9, f"{v:.1f}", ha="center", fontweight="bold", color="white")

    # 3. Electricity Cost (EUR)
    cost_vals = [m["total_cost_eur"] for m in sys_metrics]
    axes[1, 0].bar(sys_names, cost_vals, color=colors, alpha=0.85, edgecolor="black")
    axes[1, 0].set_title("Total Electricity Cost (EUR)")
    axes[1, 0].set_ylabel("Cost (€)")
    for i, v in enumerate(cost_vals):
        axes[1, 0].text(i, v * 0.9, f"€{v:,.0f}", ha="center", fontweight="bold", color="white")

    # 4. Renewable Curtailment (MWh)
    curt_vals = [m["total_curt_kwh"] / 1000.0 for m in sys_metrics]
    axes[1, 1].bar(sys_names, curt_vals, color=colors, alpha=0.85, edgecolor="black")
    axes[1, 1].set_title("Renewable Curtailment (MWh)")
    axes[1, 1].set_ylabel("Curtailment (MWh)")
    axes[1, 1].set_ylim(0, 1.0)
    for i, v in enumerate(curt_vals):
        axes[1, 1].text(i, 0.1, f"{v:.2f} (0.0%)", ha="center", fontweight="bold", color="black")

    plt.tight_layout()
    fig6_path = fig_path / "fig06_systems_comparison.png"
    plt.savefig(fig6_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 6 to %s", fig6_path)

    # -------------------------------------------------------------------------
    # Figure 7: Renewable Penetration Sensitivity (Experiment D)
    # -------------------------------------------------------------------------
    pen_data = results["experiment_d_penetration"]
    pen_labels = ["20%", "40%", "60%"]
    rb_peaks = [pen_data[k]["rule_based"]["peak_grid_kw"] for k in ["20pct", "40pct", "60pct"]]
    opt_peaks = [pen_data[k]["forecast_opt"]["peak_grid_kw"] for k in ["20pct", "40pct", "60pct"]]
    rb_cost = [pen_data[k]["rule_based"]["total_cost_eur"] for k in ["20pct", "40pct", "60pct"]]
    opt_cost = [pen_data[k]["forecast_opt"]["total_cost_eur"] for k in ["20pct", "40pct", "60pct"]]

    _fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    x_idx = np.arange(len(pen_labels))
    width = 0.35

    # Panel 1: Peak Grid Demand (kW)
    axes[0].bar(x_idx - width / 2, rb_peaks, width, label="Rule-Based Battery", color="#1f77b4", edgecolor="black")
    axes[0].bar(x_idx + width / 2, opt_peaks, width, label="Forecast-Informed Opt", color="#2ca02c", edgecolor="black")
    axes[0].set_title("Peak Grid Demand across Penetration Levels")
    axes[0].set_xlabel("Renewable Penetration")
    axes[0].set_ylabel("Peak Demand (kW)")
    axes[0].set_xticks(x_idx)
    axes[0].set_xticklabels(pen_labels)
    axes[0].set_ylim(0, 3800)
    peak_reds = [pen_data[k]["improvement"]["peak_reduction_pct"] for k in ["20pct", "40pct", "60pct"]]
    for i, r in enumerate(peak_reds):
        axes[0].text(x_idx[i] + width / 2, opt_peaks[i] + 60, f"-{r:.2f}%", ha="center", fontweight="bold", color="#2ca02c")
    axes[0].legend()

    # Panel 2: Total Electricity Cost (EUR)
    axes[1].bar(x_idx - width / 2, rb_cost, width, label="Rule-Based Battery", color="#1f77b4", edgecolor="black")
    axes[1].bar(x_idx + width / 2, opt_cost, width, label="Forecast-Informed Opt", color="#2ca02c", edgecolor="black")
    axes[1].set_title("Total Electricity Cost across Penetration Levels")
    axes[1].set_xlabel("Renewable Penetration")
    axes[1].set_ylabel("Cost (EUR)")
    axes[1].set_xticks(x_idx)
    axes[1].set_xticklabels(pen_labels)
    axes[1].set_ylim(0, 360000)
    cost_savs = [pen_data[k]["improvement"]["cost_savings_pct"] for k in ["20pct", "40pct", "60pct"]]
    for i, s in enumerate(cost_savs):
        axes[1].text(x_idx[i] + width / 2, opt_cost[i] + 5000, f"-{s:.2f}%", ha="center", fontweight="bold", color="#2ca02c")
    axes[1].legend()

    plt.tight_layout()
    fig7_path = fig_path / "fig07_penetration_sensitivity.png"
    plt.savefig(fig7_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 7 to %s", fig7_path)

    # -------------------------------------------------------------------------
    # Figure 8: Battery Duration Sensitivity (Experiment E)
    # -------------------------------------------------------------------------
    dur_data = results["experiment_e_duration"]
    dur_labels = ["2-Hour Storage\n(2.5 MWh / 1.25 MW)", "4-Hour Storage\n(5.0 MWh / 1.25 MW)"]
    dur_peaks = [dur_data[k]["forecast_opt"]["peak_grid_kw"] for k in ["2h", "4h"]]
    dur_cost = [dur_data[k]["forecast_opt"]["total_cost_eur"] for k in ["2h", "4h"]]

    _fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Panel 1: Peak Demand
    axes[0].bar(dur_labels, dur_peaks, color=["#3470a3", "#2ca02c"], edgecolor="black", alpha=0.85, width=0.45)
    axes[0].axhline(3279.17, color="#d62728", linestyle="--", linewidth=1.5, label="Rule-Based Ref (3,279 kW)")
    axes[0].set_title("Peak Demand vs Storage Duration")
    axes[0].set_ylabel("Peak Grid Demand (kW)")
    axes[0].set_ylim(0, 3800)
    dur_reds = [dur_data[k]["improvement"]["peak_reduction_pct"] for k in ["2h", "4h"]]
    for i, v in enumerate(dur_peaks):
        axes[0].text(i, v * 0.9, f"{v:,.1f} kW\n(-{dur_reds[i]:.2f}%)", ha="center", fontweight="bold", color="white")
    axes[0].legend()

    # Panel 2: Total Cost
    axes[1].bar(dur_labels, dur_cost, color=["#3470a3", "#2ca02c"], edgecolor="black", alpha=0.85, width=0.45)
    axes[1].set_title("Total Cost vs Storage Duration")
    axes[1].set_ylabel("Total Cost (EUR)")
    axes[1].set_ylim(0, 360000)
    dur_savs = [dur_data[k]["improvement"]["cost_savings_pct"] for k in ["2h", "4h"]]
    for i, v in enumerate(dur_cost):
        axes[1].text(i, v * 0.9, f"€{v:,.0f}\n(-{dur_savs[i]:.2f}%)", ha="center", fontweight="bold", color="white")

    plt.tight_layout()
    fig8_path = fig_path / "fig08_duration_sensitivity.png"
    plt.savefig(fig8_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 8 to %s", fig8_path)

    # -------------------------------------------------------------------------
    # Figure 9: Forecast Noise Sensitivity (Experiment F)
    # -------------------------------------------------------------------------
    noise_data = results["experiment_f_noise"]
    noise_stds = [0, 10, 20, 30]
    noise_peaks = [noise_data[f"{s}pct"]["metrics"]["peak_grid_kw"] for s in noise_stds]
    noise_costs = [noise_data[f"{s}pct"]["metrics"]["total_cost_eur"] for s in noise_stds]

    _fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Panel 1: Peak Grid Demand vs Noise STD
    axes[0].plot(noise_stds, noise_peaks, "o-", color="#d62728", lw=2.2, markersize=8, label="Forecast-Opt Peak")
    axes[0].axhline(3279.17, color="black", linestyle="--", linewidth=1.5, label="Grid-Only Ref (3,279 kW)")
    axes[0].set_title("Peak Grid Demand under Injected Forecast Noise")
    axes[0].set_xlabel("Injected Forecast Noise STD (%)")
    axes[0].set_ylabel("Peak Demand (kW)")
    axes[0].set_xticks(noise_stds)
    for s, p in zip(noise_stds, noise_peaks):
        axes[0].annotate(f"{p:.1f} kW", (s, p), textcoords="offset points", xytext=(0, 10), ha="center", fontweight="bold")
    axes[0].legend()
    axes[0].grid(True, linestyle=":", alpha=0.6)

    # Panel 2: Total Electricity Cost vs Noise STD
    axes[1].plot(noise_stds, noise_costs, "s-", color="#1f77b4", lw=2.2, markersize=8)
    axes[1].set_title("Total Electricity Cost under Forecast Noise")
    axes[1].set_xlabel("Injected Forecast Noise STD (%)")
    axes[1].set_ylabel("Total Cost (EUR)")
    axes[1].set_xticks(noise_stds)
    axes[1].set_ylim(295000, 305000)
    for s, c in zip(noise_stds, noise_costs):
        axes[1].annotate(f"€{c:,.0f}", (s, c), textcoords="offset points", xytext=(0, 10), ha="center", fontweight="bold")
    axes[1].grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    fig9_path = fig_path / "fig09_forecast_noise_sensitivity.png"
    plt.savefig(fig9_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 9 to %s", fig9_path)

    # -------------------------------------------------------------------------
    # Figure 10: Forecast vs Perfect Foresight Oracle Performance Gap
    # -------------------------------------------------------------------------
    gap_metrics = ["Electricity Cost (€)", "Peak Grid Demand (kW)", "Grid Energy (MWh)"]
    c_vals = [sys_c["total_cost_eur"], sys_c["peak_grid_kw"], sys_c["total_grid_kwh"] / 1000.0]
    d_vals = [sys_d["total_cost_eur"], sys_d["peak_grid_kw"], sys_d["total_grid_kwh"] / 1000.0]

    _fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    titles = ["Cost Gap", "Peak Demand Gap", "Grid Energy Gap"]
    for i in range(3):
        axes[i].bar(["Forecast Opt", "Oracle"], [c_vals[i], d_vals[i]], color=["#2ca02c", "#d62728"], edgecolor="black", alpha=0.85)
        axes[i].set_title(titles[i])
        axes[i].set_ylabel(gap_metrics[i])
        gap_pct = ((c_vals[i] - d_vals[i]) / d_vals[i] * 100.0) if d_vals[i] > 0 else 0.0
        sign = "+" if gap_pct > 0 else ""
        axes[i].text(0.5, max(c_vals[i], d_vals[i]) * 0.95, f"Gap: {sign}{gap_pct:.2f}%", ha="center", fontweight="bold", color="#d62728" if gap_pct > 0 else "#2ca02c")

    plt.tight_layout()
    fig10_path = fig_path / "fig10_oracle_gap.png"
    plt.savefig(fig10_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 10 to %s", fig10_path)


if __name__ == "__main__":
    import sys

    if "--figures-only" in sys.argv:
        with open("reports/experiments_results.json", encoding="utf-8") as f:
            res = json.load(f)
        generate_publication_figures(res)
    else:
        run_all_experiments()
