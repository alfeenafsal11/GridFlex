"""Exploratory data analysis and baseline visualization for GridFlex AI."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from src.battery.rule_based import (
    run_grid_only_baseline,
    run_rule_based_battery_baseline,
)
from src.utils.config import load_yaml_config
from src.utils.logger import get_logger

logger = get_logger("evaluation.exploratory")

# Plot styling configuration
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
})


def run_exploratory_analysis(
    data_path: str = "data/processed/gridflex_hourly.parquet",
    config_path: str = "configs/default.yaml",
    figures_dir: str = "figures",
) -> dict[str, Any]:
    """Generate baseline simulations, exploratory statistics, and research figures."""
    fig_path = Path(figures_dir)
    fig_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(data_path)
    cfg = load_yaml_config(config_path)
    b_cfg = cfg["battery"]

    logger.info("Loaded processed dataset with %d timesteps.", len(df))

    # Run Baselines
    res_a, metrics_a = run_grid_only_baseline(df)
    res_b, metrics_b = run_rule_based_battery_baseline(
        df,
        capacity_kwh=b_cfg["capacity_kwh"],
        max_charge_kw=b_cfg["max_charge_kw"],
        max_discharge_kw=b_cfg["max_discharge_kw"],
        min_soc=b_cfg["min_soc"],
        max_soc=b_cfg["max_soc"],
        charge_efficiency=b_cfg["charge_efficiency"],
        discharge_efficiency=b_cfg["discharge_efficiency"],
        initial_soc=b_cfg["initial_soc"],
    )

    # 1. Figure: Demand vs Renewable Generation (Full Year & Representative Summer Week)
    _fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=False)

    # Top: Full Year Monthly Resampled Overview
    df_monthly = df[["load_kw", "solar_kw", "net_load_kw"]].resample("1D").mean()
    axes[0].plot(df_monthly.index, df_monthly["load_kw"], label="Mean Electrical Demand (kW)", color="#1f77b4", lw=1.5)
    axes[0].plot(df_monthly.index, df_monthly["solar_kw"], label="Mean Solar Generation (kW)", color="#ff7f0e", lw=1.5)
    axes[0].set_title("Annual Daily Average Power Profiles (2024)")
    axes[0].set_ylabel("Power (kW)")
    axes[0].legend(loc="upper right")

    # Bottom: Representative Summer Week (June 10 - June 17, 2024)
    summer_week = df.loc["2024-06-10":"2024-06-16"]
    axes[1].plot(summer_week.index, summer_week["load_kw"], label="Demand (kW)", color="#1f77b4", lw=2)
    axes[1].plot(summer_week.index, summer_week["solar_kw"], label="Solar Generation (kW)", color="#ff7f0e", lw=2)
    axes[1].fill_between(
        summer_week.index,
        summer_week["load_kw"],
        summer_week["solar_kw"],
        where=(summer_week["solar_kw"] >= summer_week["load_kw"]),
        color="#2ca02c",
        alpha=0.3,
        label="Renewable Surplus",
    )
    axes[1].fill_between(
        summer_week.index,
        summer_week["load_kw"],
        summer_week["solar_kw"],
        where=(summer_week["solar_kw"] < summer_week["load_kw"]),
        color="#d62728",
        alpha=0.2,
        label="Renewable Deficit",
    )
    axes[1].set_title("Representative High-Solar Summer Week (June 10–16, 2024)")
    axes[1].set_xlabel("Time (UTC)")
    axes[1].set_ylabel("Power (kW)")
    axes[1].legend(loc="upper right")

    plt.tight_layout()
    fig1_path = fig_path / "fig01_demand_vs_solar.png"
    plt.savefig(fig1_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 1 to %s", fig1_path)

    # 2. Figure: Average Diurnal Profiles by Hour of Day
    df_hourly_profile = df.groupby(df.index.hour)[["load_kw", "solar_kw", "net_load_kw", "price_eur_mwh"]].mean()
    _fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.plot(df_hourly_profile.index, df_hourly_profile["load_kw"], label="Demand (kW)", color="#1f77b4", lw=2.5, marker="o")
    ax1.plot(df_hourly_profile.index, df_hourly_profile["solar_kw"], label="Solar Generation (kW)", color="#ff7f0e", lw=2.5, marker="s")
    ax1.plot(df_hourly_profile.index, df_hourly_profile["net_load_kw"], label="Net Load (kW)", color="#2ca02c", lw=2, linestyle="--")
    ax1.set_xlabel("Hour of Day (UTC)")
    ax1.set_ylabel("Power (kW)")
    ax1.set_xticks(range(24))

    ax2 = ax1.twinx()
    ax2.plot(df_hourly_profile.index, df_hourly_profile["price_eur_mwh"], label="EPEX Price (EUR/MWh)", color="#9467bd", lw=2, linestyle=":")
    ax2.set_ylabel("Price (EUR/MWh)")
    ax2.grid(False)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    plt.title("Diurnal Pattern: Mean Hourly Demand, Solar, Net Load, and Electricity Price")

    plt.tight_layout()
    fig2_path = fig_path / "fig02_daily_profiles.png"
    plt.savefig(fig2_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 2 to %s", fig2_path)

    # 3. Figure: EPEX Electricity Price Distribution & Duration Curve
    _fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Histogram / Density
    axes[0].hist(df["price_eur_mwh"], bins=50, color="#3470a3", edgecolor="black", alpha=0.7)
    axes[0].axvline(df["price_eur_mwh"].mean(), color="red", linestyle="--", label=f"Mean: {df['price_eur_mwh'].mean():.1f} EUR/MWh")
    axes[0].axvline(0, color="gray", linestyle="-", lw=1)
    axes[0].set_title("EPEX NL Spot Price Distribution (2024)")
    axes[0].set_xlabel("Electricity Price (EUR/MWh)")
    axes[0].set_ylabel("Frequency (Hours)")
    axes[0].legend()

    # Price Duration Curve
    sorted_prices = df["price_eur_mwh"].sort_values(ascending=False).values
    axes[1].plot(range(len(sorted_prices)), sorted_prices, color="#3470a3", lw=2)
    axes[1].axhline(0, color="gray", linestyle="--", lw=1)
    axes[1].set_title("Price Duration Curve")
    axes[1].set_xlabel("Hours (Ranked)")
    axes[1].set_ylabel("Electricity Price (EUR/MWh)")

    plt.tight_layout()
    fig3_path = fig_path / "fig03_price_distribution.png"
    plt.savefig(fig3_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 3 to %s", fig3_path)

    # 4. Figure: Baseline Comparison (Grid Import & Battery Operation)
    _fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    sample_slice = slice("2024-06-10", "2024-06-16")
    sub_a = res_a.loc[sample_slice]
    sub_b = res_b.loc[sample_slice]

    axes[0].plot(sub_a.index, sub_a["load_kw"], label="Demand", color="black", lw=1.5)
    axes[0].plot(sub_a.index, sub_a["solar_kw"], label="Solar Generation", color="#ff7f0e", lw=1.5)
    axes[0].set_title("Summer Week Operation: Grid-Only vs Rule-Based Battery")
    axes[0].set_ylabel("Power (kW)")
    axes[0].legend(loc="upper right")

    axes[1].plot(sub_a.index, sub_a["grid_import_kw"], label="Grid-Only Import (kW)", color="#d62728", lw=1.5, linestyle="--")
    axes[1].plot(sub_b.index, sub_b["grid_import_kw"], label="Rule-Based Battery Grid Import (kW)", color="#1f77b4", lw=2)
    axes[1].set_ylabel("Grid Import (kW)")
    axes[1].legend(loc="upper right")

    axes[2].plot(sub_b.index, sub_b["soc"] * 100, label="Battery SOC (%)", color="#2ca02c", lw=2)
    axes[2].axhline(b_cfg["max_soc"] * 100, color="gray", linestyle=":", label="Max SOC (90%)")
    axes[2].axhline(b_cfg["min_soc"] * 100, color="gray", linestyle=":", label="Min SOC (10%)")
    axes[2].set_ylabel("SOC (%)")
    axes[2].set_xlabel("Time (UTC)")
    axes[2].legend(loc="upper right")

    plt.tight_layout()
    fig4_path = fig_path / "fig04_baseline_comparison.png"
    plt.savefig(fig4_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 4 to %s", fig4_path)

    # Print baseline metrics comparison
    comparison_df = pd.DataFrame([metrics_a, metrics_b]).set_index("system")
    logger.info("Baseline Comparison Table:\n%s", comparison_df.T.to_string())

    return {
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
        "comparison_df": comparison_df,
    }


if __name__ == "__main__":
    run_exploratory_analysis()
