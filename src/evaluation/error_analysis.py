"""Comprehensive error analysis, failure mode diagnostics, and operational review.

Investigates:
1. Forecast residual distributions across horizons and diurnal cycles.
2. Worst-case error episodes (extreme overcast, sudden demand swings).
3. Battery saturation/depletion dynamics and diurnal state of charge profiles.
4. Attribution of the Forecast-to-Oracle dispatch gap.
5. Scientific answers to core diagnostic questions for IRENA submission.
"""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.battery.rule_based import run_rule_based_battery_baseline
from src.optimization.rolling_horizon import run_rolling_horizon_simulation
from src.utils.config import load_yaml_config
from src.utils.logger import get_logger

logger = get_logger("evaluation.error_analysis")


def analyze_forecast_residuals(
    test_preds_df: pd.DataFrame,
) -> dict[str, Any]:
    """Compute detailed statistical diagnostics on forecast residuals."""
    pred_load_col = "pred_load_lgbm_h1" if "pred_load_lgbm_h1" in test_preds_df.columns else "pred_load_h1"
    pred_solar_col = "pred_solar_lgbm_h1" if "pred_solar_lgbm_h1" in test_preds_df.columns else "pred_solar_h1"
    residuals_load = test_preds_df[pred_load_col] - test_preds_df["actual_load_h1"]
    residuals_solar = test_preds_df[pred_solar_col] - test_preds_df["actual_solar_h1"]

    def _stats(arr: pd.Series) -> dict[str, float]:
        a = arr.to_numpy()
        std_val = float(np.std(a))
        skew_val = float(stats.skew(a)) if std_val > 1e-9 else 0.0
        kurt_val = float(stats.kurtosis(a)) if std_val > 1e-9 else 0.0
        return {
            "mean": float(np.mean(a)),
            "std": std_val,
            "median": float(np.median(a)),
            "p10": float(np.percentile(a, 10)),
            "p25": float(np.percentile(a, 25)),
            "p75": float(np.percentile(a, 75)),
            "p90": float(np.percentile(a, 90)),
            "max_overprediction": float(np.max(a)),
            "max_underprediction": float(np.min(a)),
            "skewness": skew_val,
            "kurtosis": kurt_val,
        }

    # Diurnal MAE breakdown (by hour of day)
    hours = test_preds_df.index.hour
    diurnal_load_mae = {}
    diurnal_solar_mae = {}
    for h in range(24):
        mask = hours == h
        diurnal_load_mae[h] = float(np.mean(np.abs(residuals_load[mask]))) if np.any(mask) else 0.0
        diurnal_solar_mae[h] = float(np.mean(np.abs(residuals_solar[mask]))) if np.any(mask) else 0.0

    # Identify worst 5 days for load and solar
    test_preds_df_copy = test_preds_df.copy()
    test_preds_df_copy["load_abs_err"] = np.abs(residuals_load)
    test_preds_df_copy["solar_abs_err"] = np.abs(residuals_solar)
    test_preds_df_copy["date"] = test_preds_df.index.date

    daily_load_mae = test_preds_df_copy.groupby("date")["load_abs_err"].mean()
    daily_solar_mae = test_preds_df_copy.groupby("date")["solar_abs_err"].mean()

    worst_load_days = [
        {"date": str(d), "mae_kw": float(mae)}
        for d, mae in daily_load_mae.nlargest(5).items()
    ]
    worst_solar_days = [
        {"date": str(d), "mae_kw": float(mae)}
        for d, mae in daily_solar_mae.nlargest(5).items()
    ]

    return {
        "load_residual_stats": _stats(residuals_load),
        "solar_residual_stats": _stats(residuals_solar),
        "diurnal_load_mae": diurnal_load_mae,
        "diurnal_solar_mae": diurnal_solar_mae,
        "worst_load_days": worst_load_days,
        "worst_solar_days": worst_solar_days,
    }


def analyze_battery_dynamics(
    sim_c_df: pd.DataFrame,
    sim_d_df: pd.DataFrame,
    min_soc: float = 0.10,
    max_soc: float = 0.90,
    tol: float = 0.01,
    sim_b_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Analyze battery SOC saturation, depletion, and cycling characteristics."""
    total_hours = len(sim_c_df)

    def _soc_dynamics(df: pd.DataFrame) -> dict[str, Any]:
        soc = df["soc"].to_numpy()
        depleted_hrs = int(np.sum(soc <= (min_soc + tol)))
        saturated_hrs = int(np.sum(soc >= (max_soc - tol)))
        intermediate_hrs = total_hours - depleted_hrs - saturated_hrs

        # Diurnal SOC profile (average SOC per hour of day)
        hours = df.index.hour
        diurnal_soc = {}
        for h in range(24):
            mask = hours == h
            diurnal_soc[int(h)] = float(np.mean(soc[mask])) if np.any(mask) else 0.0

        return {
            "depleted_hours": depleted_hrs,
            "depleted_pct": float(depleted_hrs / total_hours * 100),
            "saturated_hours": saturated_hrs,
            "saturated_pct": float(saturated_hrs / total_hours * 100),
            "intermediate_hours": intermediate_hrs,
            "intermediate_pct": float(intermediate_hrs / total_hours * 100),
            "mean_soc": float(np.mean(soc)),
            "std_soc": float(np.std(soc)),
            "diurnal_soc_profile": diurnal_soc,
        }

    res: dict[str, Any] = {
        "system_c_forecast": _soc_dynamics(sim_c_df),
        "system_d_oracle": _soc_dynamics(sim_d_df),
    }

    if sim_b_df is not None:
        b_dyn = _soc_dynamics(sim_b_df)
        p_ch = (
            sim_b_df["battery_charge_kw"].to_numpy()
            if "battery_charge_kw" in sim_b_df.columns
            else np.zeros(len(sim_b_df))
        )
        p_dis = (
            sim_b_df["battery_discharge_kw"].to_numpy()
            if "battery_discharge_kw" in sim_b_df.columns
            else np.zeros(len(sim_b_df))
        )
        idle_hours = int(np.sum((p_ch == 0.0) & (p_dis == 0.0)))
        b_dyn["idle_hours"] = idle_hours
        b_dyn["idle_pct"] = float(idle_hours / len(sim_b_df) * 100)
        b_dyn["minimum_soc_hours"] = b_dyn["depleted_hours"]
        b_dyn["minimum_soc_pct"] = b_dyn["depleted_pct"]
        b_dyn["minimum_soc_value"] = min_soc
        b_dyn["total_evaluation_hours"] = len(sim_b_df)
        res["system_b_rule_based"] = b_dyn

    return res


def analyze_oracle_performance_gap(
    sim_c_df: pd.DataFrame,
    sim_d_df: pd.DataFrame,
    test_preds_df: pd.DataFrame,
) -> dict[str, Any]:
    """Diagnose the root causes of the performance gap between System C and System D."""
    # Peak hour comparison
    peak_hr_c = sim_c_df["grid_import_kw"].idxmax()
    peak_val_c = float(sim_c_df["grid_import_kw"].max())
    peak_val_d_at_c = float(sim_d_df.loc[peak_hr_c, "grid_import_kw"])

    peak_hr_d = sim_d_df["grid_import_kw"].idxmax()
    peak_val_d = float(sim_d_df["grid_import_kw"].max())

    # Hourly grid difference: positive when System C imported more than System D
    price_col = "price_eur_kwh" if "price_eur_kwh" in sim_c_df.columns else "price"
    price_series = sim_c_df[price_col]
    cost_c = sim_c_df["grid_import_kw"] * price_series
    cost_d = sim_d_df["grid_import_kw"] * price_series

    grid_diff = sim_c_df["grid_import_kw"] - sim_d_df["grid_import_kw"]
    hourly_cost_diff = cost_c - cost_d

    # Correlation between forecast error and suboptimal dispatch (excess grid import)
    pred_load_col = "pred_load_lgbm_h1" if "pred_load_lgbm_h1" in test_preds_df.columns else "pred_load_h1"
    pred_solar_col = "pred_solar_lgbm_h1" if "pred_solar_lgbm_h1" in test_preds_df.columns else "pred_solar_h1"
    load_err = np.abs(test_preds_df[pred_load_col] - test_preds_df["actual_load_h1"])
    solar_err = np.abs(test_preds_df[pred_solar_col] - test_preds_df["actual_solar_h1"])
    total_forecast_err = load_err + solar_err

    corr_err_grid_diff = float(np.corrcoef(total_forecast_err, grid_diff)[0, 1])

    # Top 5 timesteps where System C suffered the largest cost penalty vs Oracle
    worst_dispatch_steps = []
    top_cost_diff_indices = hourly_cost_diff.nlargest(5).index
    for t in top_cost_diff_indices:
        worst_dispatch_steps.append({
            "timestamp": str(t),
            "cost_penalty_eur": float(hourly_cost_diff.loc[t]),
            "grid_import_c_kw": float(sim_c_df.loc[t, "grid_import_kw"]),
            "grid_import_d_kw": float(sim_d_df.loc[t, "grid_import_kw"]),
            "soc_c": float(sim_c_df.loc[t, "soc"]),
            "soc_d": float(sim_d_df.loc[t, "soc"]),
            "price_eur_per_kwh": float(price_series.loc[t]),
            "load_err_kw": float(load_err.loc[t]),
            "solar_err_kw": float(solar_err.loc[t]),
        })

    return {
        "system_c_peak_kw": peak_val_c,
        "system_c_peak_timestamp": str(peak_hr_c),
        "system_d_import_at_c_peak_kw": peak_val_d_at_c,
        "system_d_peak_kw": peak_val_d,
        "system_d_peak_timestamp": str(peak_hr_d),
        "correlation_forecast_error_excess_grid": corr_err_grid_diff,
        "total_cost_gap_eur": float(cost_c.sum() - cost_d.sum()),
        "worst_dispatch_timesteps": worst_dispatch_steps,
    }


def generate_error_analysis_figure(
    test_preds_df: pd.DataFrame,
    sim_c_df: pd.DataFrame,
    sim_d_df: pd.DataFrame,
    diagnostics: dict[str, Any],
    output_path: str = "figures/fig11_error_analysis.png",
) -> None:
    """Generate professional 4-panel diagnostic figure for IRENA publication."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=300)
    fig.subplots_adjust(hspace=0.32, wspace=0.22)

    # 1. Residual Distributions
    ax1 = axes[0, 0]
    pred_load_col = "pred_load_lgbm_h1" if "pred_load_lgbm_h1" in test_preds_df.columns else "pred_load_h1"
    pred_solar_col = "pred_solar_lgbm_h1" if "pred_solar_lgbm_h1" in test_preds_df.columns else "pred_solar_h1"
    res_load = test_preds_df[pred_load_col] - test_preds_df["actual_load_h1"]
    res_solar = test_preds_df[pred_solar_col] - test_preds_df["actual_solar_h1"]

    ax1.hist(
        res_load,
        bins=40,
        density=True,
        alpha=0.6,
        color="#1f77b4",
        label=f"Load Residuals (Mean: {np.mean(res_load):.1f} kW, Std: {np.std(res_load):.1f})",
    )
    ax1.hist(
        res_solar,
        bins=40,
        density=True,
        alpha=0.6,
        color="#ff7f0e",
        label=f"Solar Residuals (Mean: {np.mean(res_solar):.1f} kW, Std: {np.std(res_solar):.1f})",
    )
    ax1.axvline(0, color="black", linestyle="--", linewidth=1.2, alpha=0.7)
    ax1.set_title("(A) 1-Hour Ahead Forecast Residual Distributions", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Prediction Residual: [Forecast - Actual] (kW)", fontsize=10)
    ax1.set_ylabel("Probability Density", fontsize=10)
    ax1.legend(loc="upper right", frameon=True, fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # 2. Diurnal Forecast Error vs Diurnal Battery Action
    ax2 = axes[0, 1]
    hours = np.arange(24)
    load_mae_by_hr = [diagnostics["forecast"]["diurnal_load_mae"][h] for h in hours]
    solar_mae_by_hr = [diagnostics["forecast"]["diurnal_solar_mae"][h] for h in hours]
    soc_c_by_hr = [diagnostics["battery"]["system_c_forecast"]["diurnal_soc_profile"][h] * 100 for h in hours]

    ax2_soc = ax2.twinx()
    p1 = ax2.plot(hours, load_mae_by_hr, color="#1f77b4", marker="o", linewidth=2, label="Load MAE (kW)")
    p2 = ax2.plot(hours, solar_mae_by_hr, color="#ff7f0e", marker="s", linewidth=2, label="Solar MAE (kW)")
    p3 = ax2_soc.plot(hours, soc_c_by_hr, color="#2ca02c", linestyle="--", linewidth=2.5, label="Mean Battery SOC (%)")

    ax2.set_title("(B) Diurnal Error Profile vs Battery SOC Schedule", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Hour of Day (UTC)", fontsize=10)
    ax2.set_ylabel("Mean Absolute Error (kW)", fontsize=10)
    ax2_soc.set_ylabel("Battery State of Charge (%)", fontsize=10, color="#2ca02c")
    ax2.set_xticks(hours[::2])
    ax2.grid(True, linestyle=":", alpha=0.6)

    plots = p1 + p2 + p3
    labels = [p.get_label() for p in plots]
    ax2.legend(plots, labels, loc="upper left", frameon=True, fontsize=9)

    # 3. SOC Distribution / Saturation Breakdown
    ax3 = axes[1, 0]
    soc_c = sim_c_df["soc"] * 100
    soc_d = sim_d_df["soc"] * 100

    ax3.hist(
        soc_c,
        bins=25,
        alpha=0.7,
        color="#1f77b4",
        edgecolor="black",
        label="System C (Forecast Opt)",
    )
    ax3.hist(
        soc_d,
        bins=25,
        alpha=0.5,
        color="#2ca02c",
        edgecolor="black",
        linestyle="--",
        label="System D (Oracle)",
    )
    ax3.axvline(10, color="red", linestyle=":", linewidth=1.5, label="Min SOC Limit (10%)")
    ax3.axvline(90, color="red", linestyle=":", linewidth=1.5, label="Max SOC Limit (90%)")
    ax3.set_title("(C) Battery SOC Operating Distribution", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Battery State of Charge (%)", fontsize=10)
    ax3.set_ylabel("Operating Hours (out of 1,290 hrs)", fontsize=10)
    ax3.legend(loc="upper center", frameon=True, fontsize=9)
    ax3.grid(True, linestyle=":", alpha=0.6)

    # 4. Deep Dive Case Study: Worst Forecast Error Day / High-Stress Event
    ax4 = axes[1, 1]
    worst_day_str = diagnostics["forecast"]["worst_load_days"][0]["date"]
    day_mask = sim_c_df.index.strftime("%Y-%m-%d") == worst_day_str
    sub_c = sim_c_df[day_mask]
    sub_d = sim_d_df[day_mask]
    sub_times = np.arange(len(sub_c))

    ax4.plot(sub_times, sub_c["grid_import_kw"], color="#d62728", linewidth=2, label="Grid Import (System C)")
    ax4.plot(sub_times, sub_d["grid_import_kw"], color="#2ca02c", linestyle="--", linewidth=2, label="Grid Import (Oracle)")
    ax4.plot(sub_times, sub_c["load_kw"], color="black", linestyle=":", alpha=0.7, label="Total Actual Load")

    ax4.set_title(f"(D) High-Stress Event Trace ({worst_day_str})", fontsize=12, fontweight="bold")
    ax4.set_xlabel("Hour of Day", fontsize=10)
    ax4.set_ylabel("Power (kW)", fontsize=10)
    ax4.set_xticks(sub_times[::3])
    ax4.legend(loc="upper right", frameon=True, fontsize=9)
    ax4.grid(True, linestyle=":", alpha=0.6)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info("Saved Figure 11 to %s", output_path)


def run_error_analysis(
    data_path: str = "data/processed/gridflex_hourly.parquet",
    preds_path: str = "data/processed/test_predictions.parquet",
    config_path: str = "configs/default.yaml",
    output_json: str = "reports/error_analysis_results.json",
    output_fig: str = "figures/fig11_error_analysis.png",
) -> dict[str, Any]:
    """Execute full diagnostic error analysis pipeline."""
    df = pd.read_parquet(data_path)
    test_preds_df = pd.read_parquet(preds_path)
    cfg = load_yaml_config(config_path)

    b_cfg = cfg["battery"]
    o_cfg = cfg["optimization"]["weights"]

    # Align test data
    test_index = test_preds_df.index
    df_test = df.loc[test_index].copy()
    df_test["load_kw"] = test_preds_df["actual_load_h1"].to_numpy()
    df_test["solar_kw"] = test_preds_df["actual_solar_h1"].to_numpy()

    logger.info("Executing simulation traces for error analysis...")
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

    logger.info("Computing forecast residuals diagnostics...")
    forecast_diag = analyze_forecast_residuals(test_preds_df)

    logger.info("Computing battery dynamics diagnostics...")
    battery_diag = analyze_battery_dynamics(
        sim_c, sim_d, min_soc=b_cfg["min_soc"], max_soc=b_cfg["max_soc"], sim_b_df=sim_b
    )

    logger.info("Computing oracle performance gap diagnostics...")
    oracle_gap_diag = analyze_oracle_performance_gap(sim_c, sim_d, test_preds_df)

    results = {
        "forecast": forecast_diag,
        "battery": battery_diag,
        "oracle_gap": oracle_gap_diag,
        "system_b_rule_based": battery_diag.get("system_b_rule_based", {}),
    }

    # Save JSON report
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Saved error analysis results to %s", output_json)

    # Generate Figure 11
    generate_error_analysis_figure(
        test_preds_df=test_preds_df,
        sim_c_df=sim_c,
        sim_d_df=sim_d,
        diagnostics=results,
        output_path=output_fig,
    )

    return results


if __name__ == "__main__":
    run_error_analysis()
