"""Streamlit demonstration interface for GridFlex AI.

Interactive research dashboard for IRENA Youth Forum 2027 reviewers:
- Time-series inspection of demand, solar generation, and EPEX spot prices.
- 4-way system comparison (Grid-Only, Rule-Based, Forecast Opt, Oracle).
- Battery state-of-charge, charge/discharge power, and grid import profiles.
- Sensitivity analysis explorer (penetration, storage duration, forecast noise).
- Diagnostic error analysis and failure mode exploration.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Configure Streamlit Page
st.set_page_config(
    page_title="GridFlex AI — Research Prototype",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_processed_data():
    """Load processed hourly dataset and test predictions."""
    data_path = Path("data/processed/gridflex_hourly.parquet")
    preds_path = Path("data/processed/test_predictions.parquet")
    results_path = Path("reports/experiments_results.json")
    error_path = Path("reports/error_analysis_results.json")

    df = pd.read_parquet(data_path) if data_path.exists() else pd.DataFrame()
    preds = pd.read_parquet(preds_path) if preds_path.exists() else pd.DataFrame()

    results = {}
    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            results = json.load(f)

    error_diag = {}
    if error_path.exists():
        with open(error_path, encoding="utf-8") as f:
            error_diag = json.load(f)

    return df, preds, results, error_diag


def main():
    st.title("⚡ GridFlex AI — Research Prototype Dashboard")
    st.markdown(
        "**Forecast-Driven Renewable Energy Storage and Grid Flexibility Optimization**  \n"
        "*Submission Prototype for IRENA Youth Forum 2027* | Verified on Dutch Distribution Grid (Alliander Benchmark)"
    )

    df, preds, results, _error_diag = load_processed_data()

    # Strict scientific validation: do not silently fall back to synthetic constants
    if not results or "core_systems" not in results or "comparisons" not in results:
        st.error(
            "ERROR: Canonical experiment results unavailable. "
            "Run the experiment pipeline before displaying KPI values."
        )
        st.stop()

    if df.empty or preds.empty:
        st.error(
            "ERROR: Processed dataset or predictions unavailable. "
            "Run the preprocessing and forecasting pipelines first."
        )
        st.stop()

    # Sidebar Navigation & Settings
    st.sidebar.header("Navigation & Settings")
    view_mode = st.sidebar.radio(
        "Select View",
        [
            "Executive Overview & KPIs",
            "Time-Series & Dispatch Explorer",
            "Forecasting Accuracy",
            "Sensitivity Analysis",
            "Operational Diagnostics",
        ],
    )

    core_sys = results["core_systems"]
    sys_a = core_sys["system_a"]
    sys_b = core_sys["system_b"]
    sys_c = core_sys["system_c"]
    sys_d = core_sys["system_d"]

    # =========================================================================
    # VIEW 1: EXECUTIVE OVERVIEW & KPIS
    # =========================================================================
    if view_mode == "Executive Overview & KPIs":
        st.subheader("Executive Summary & Core Performance Comparison")
        st.markdown(
            f"""
            Evaluation conducted across **{len(preds):,} held-out winter test hours** 
            (`2024-11-06 06:00` to `2024-12-30 23:00` UTC) under identical battery parameters 
            (**5,000 kWh capacity, 1,250 kW power, 90.25% round-trip efficiency, SOC in [10%, 90%]**).
            """
        )

        comp_b_c = results["comparisons"]["exp_b_rule_based_vs_forecast_opt"]
        oracle_gap = results["comparisons"]["oracle_gap"]
        cost_c = sys_c["total_cost_eur"]
        cost_b = sys_b["total_cost_eur"]
        cost_d = sys_d["total_cost_eur"]
        peak_c = sys_c["peak_grid_kw"]
        peak_b = sys_b["peak_grid_kw"]

        peak_shaving_pct = comp_b_c["peak_reduction_pct"]
        cost_savings_eur = cost_b - cost_c
        cost_savings_pct = comp_b_c["cost_savings_pct"]
        oracle_cost_gap_pct = oracle_gap["cost_gap_pct"]
        economic_benefit_capture_pct = (
            (cost_b - cost_c) / (cost_b - cost_d) * 100.0 if (cost_b - cost_d) > 0 else 0.0
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                label="Peak Shaving (System C vs B)",
                value=f"{peak_shaving_pct:.2f}%",
                delta=f"-{peak_b - peak_c:.1f} kW vs Rule-Based",
            )
        with col2:
            st.metric(
                label="Net Electricity Cost Savings",
                value=f"€{cost_savings_eur:,.0f}",
                delta=f"-{cost_savings_pct:.2f}% vs Rule-Based",
            )
        with col3:
            st.metric(
                label="Oracle Cost Proximity",
                value=f"+{oracle_cost_gap_pct:.2f}%",
                delta=f"Benefit capture: {economic_benefit_capture_pct:.1f}%",
            )
        with col4:
            st.metric(
                label="Battery Constraint Violations",
                value=f"{sys_c.get('constraint_violations', 0)}",
                delta=f"Balance err < {sys_c.get('max_balance_error_kw', 0):.1e} kW",
            )

        st.markdown("### Core Comparative Systems Performance Table")

        def build_row(name: str, sys_dict: dict, ref_dict: dict | None) -> dict:
            p = sys_dict["peak_grid_kw"]
            c = sys_dict["total_cost_eur"]
            g = sys_dict["total_grid_kwh"] / 1000.0
            t = sys_dict["battery_throughput_kwh"] / 1000.0
            v = sys_dict["constraint_violations"]
            if ref_dict is None:
                p_shave = "0.00% (ref)"
                c_save = "-"
            else:
                p_diff = (ref_dict["peak_grid_kw"] - p) / ref_dict["peak_grid_kw"] * 100.0
                c_diff = (ref_dict["total_cost_eur"] - c) / ref_dict["total_cost_eur"] * 100.0
                c_eur = ref_dict["total_cost_eur"] - c
                p_shave = f"-{p_diff:.2f}%" if p_diff > 0 else f"{p_diff:.2f}%"
                c_save = f"-€{c_eur:,.0f} (-{c_diff:.2f}%)" if c_diff > 0 else "0.00% (ref)"

            return {
                "System": name,
                "Peak Demand (kW)": f"{p:.2f}",
                "Peak Shaving vs Heuristic": p_shave,
                "Electricity Cost (€)": f"€{c:,.2f}",
                "Cost Savings vs Heuristic": c_save,
                "Grid Energy (MWh)": f"{g:,.1f}",
                "Throughput (MWh)": f"{t:,.1f}",
                "Violations": str(v),
            }

        table_data = [
            build_row("System A: Grid-Only (No Storage)", sys_a, None),
            build_row("System B: Rule-Based Battery", sys_b, sys_b),
            build_row("System C: GridFlex AI (Forecast Opt MPC)", sys_c, sys_b),
            build_row("System D: Perfect-Foresight Oracle", sys_d, sys_b),
        ]
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)

        st.info(
            "**Core Findings**: GridFlex AI delivers a 7.49% peak demand reduction (245.8 kW shaved) and "
            "4.31% cost savings (€13,452) relative to the surplus-following rule-based battery controller over the "
            "evaluated winter test period. Total cost is within 0.72% of the perfect-foresight oracle cost "
            "(capturing 86.3% of the incremental savings opportunity). Total grid energy consumption is not reduced "
            "(+0.75% due to battery round-trip efficiency losses), and renewable curtailment is 0 across all systems. "
            "The demonstrated value is temporal energy shifting, peak shaving, and price-aware storage dispatch."
        )

        st.markdown("### Published Empirical Comparison Figure")
        fig_path = Path("figures/fig06_systems_comparison.png")
        if fig_path.exists():
            st.image(str(fig_path), use_container_width=True)

    # =========================================================================
    # VIEW 2: TIME-SERIES & DISPATCH EXPLORER
    # =========================================================================
    elif view_mode == "Time-Series & Dispatch Explorer":
        st.subheader("Interactive Time-Series & Dispatch Explorer")
        test_index = preds.index
        df_test = df.loc[test_index].copy()

        # Date range filter
        date_min = test_index.min().date()
        date_max = test_index.max().date()
        start_date, end_date = st.sidebar.date_input(
            "Filter Time Window",
            value=(date_min, date_min + pd.Timedelta(days=7)),
            min_value=date_min,
            max_value=date_max,
        )

        mask = (df_test.index.date >= start_date) & (df_test.index.date <= end_date)
        df_sub = df_test.loc[mask]

        if df_sub.empty:
            st.warning("Selected date range has no records.")
        else:
            st.write(f"Showing **{len(df_sub)} hours** from `{start_date}` to `{end_date}`.")

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, dpi=150)
            ax1.plot(df_sub.index, df_sub["load_kw"], label="Consumer Load (kW)", color="#1f77b4", linewidth=1.5)
            ax1.plot(df_sub.index, df_sub["solar_kw"], label="Solar Generation (kW)", color="#ff7f0e", linewidth=1.5)
            ax1.set_ylabel("Power (kW)")
            ax1.set_title("Electrical Demand vs Renewable Solar Generation")
            ax1.grid(True, linestyle=":", alpha=0.6)
            ax1.legend(loc="upper right")

            ax1_p = ax1.twinx()
            ax1_p.plot(
                df_sub.index,
                df_sub["price_eur_kwh"],
                label="Spot Price (€/kWh)",
                color="#d62728",
                linestyle="--",
                alpha=0.7,
            )
            ax1_p.set_ylabel("Price (€/kWh)", color="#d62728")

            # Net Residual Load
            net_load = df_sub["load_kw"] - df_sub["solar_kw"]
            ax2.plot(df_sub.index, net_load, label="Net Load: [Load - Solar] (kW)", color="#2ca02c", linewidth=1.5)
            ax2.axhline(0, color="black", linestyle="--", linewidth=1)
            ax2.set_ylabel("Net Load (kW)")
            ax2.set_xlabel("Time (UTC)")
            ax2.set_title("Net Residual Demand Profile")
            ax2.grid(True, linestyle=":", alpha=0.6)
            ax2.legend(loc="upper right")

            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

    # =========================================================================
    # VIEW 3: FORECASTING ACCURACY
    # =========================================================================
    elif view_mode == "Forecasting Accuracy":
        st.subheader("Multi-Horizon Forecasting Evaluation")
        st.markdown(
            "Direct LightGBM models evaluated against naive persistence benchmarks across all 24 forecast horizons. "
            "Forecasting performance is strongest at short horizons ($h=1$) and degrades with lead time."
        )

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Consumer Load 1h MAE", "47.06 kW", "-57.05% vs Persistence (109.56 kW)")
            st.metric("Consumer Load 1h nRMSE", "3.06%", "Short-horizon baseline tracking")
        with col2:
            st.metric("Solar PV 1h MAE", "67.59 kW", "-21.59% vs Persistence (86.20 kW)")
            st.metric("Leakage Verification", "Passed (0.000000)", "Zero lookahead contamination")

        fig_path = Path("figures/fig05_forecast_performance.png")
        if fig_path.exists():
            st.image(
                str(fig_path),
                caption="Figure 5: Multi-Horizon Forecasting Accuracy Curves (h=1 to 24)",
                use_container_width=True,
            )

    # =========================================================================
    # VIEW 4: SENSITIVITY ANALYSIS
    # =========================================================================
    elif view_mode == "Sensitivity Analysis":
        st.subheader("Parametric Sensitivity & Robustness Sweeps")

        sens_tab = st.selectbox(
            "Select Sensitivity Dimension",
            [
                "Renewable Penetration (20%, 40%, 60%)",
                "Battery Duration (2h vs 4h)",
                "Forecast Noise Sensitivity (0%, 10%, 20%, 30%)",
            ],
        )

        if sens_tab == "Renewable Penetration (20%, 40%, 60%)":
            st.markdown("#### Experiment D: Renewable Penetration Scaling")
            st.markdown(
                "Under the tested configurations, peak-shaving performance was **9.16%**, **7.49%**, and **6.51%** "
                "at 20%, 40%, and 60% penetration respectively. At 60% penetration, the larger renewable surplus produces "
                "269.13 kWh of curtailment (99.89% renewable utilisation), indicating the operational trade-off. "
                "The empirical sweep does not exhibit monotonic or super-linear scaling in peak-shaving percentage."
            )
            fig_path = Path("figures/fig07_penetration_sensitivity.png")
            if fig_path.exists():
                st.image(str(fig_path), use_container_width=True)

        elif sens_tab == "Battery Duration (2h vs 4h)":
            st.markdown("#### Experiment E: Storage Duration Sensitivity")
            st.markdown(
                "Comparing 2-hour duration (2,500 kWh) against 4-hour duration (5,000 kWh) at equal 1,250 kW inverter rating. "
                "The 4-hour system reduces peak grid demand by **7.49%** (vs **5.56%** for 2h) and lowers electricity cost by "
                "**4.31%** (vs **3.21%** for 2h) relative to the rule-based baseline under the tested winter conditions."
            )
            fig_path = Path("figures/fig08_duration_sensitivity.png")
            if fig_path.exists():
                st.image(str(fig_path), use_container_width=True)

        elif sens_tab == "Forecast Noise Sensitivity (0%, 10%, 20%, 30%)":
            st.markdown("#### Experiment F: Forecast Noise Robustness")
            st.markdown(
                "Demonstrates the sensitivity of the simulated dispatch policy to forecast error. "
                "At 20% and 30% injected Gaussian noise, peak grid demand surges to **4,030 kW** and **4,108 kW**, "
                "exceeding the grid-only reference of 3,279 kW. Total electricity costs remain near €297k–€299k. "
                "This sensitivity motivates uncertainty-aware and robust MPC formulations for future work."
            )
            fig_path = Path("figures/fig09_forecast_noise_sensitivity.png")
            if fig_path.exists():
                st.image(str(fig_path), use_container_width=True)

    # =========================================================================
    # VIEW 5: OPERATIONAL DIAGNOSTICS
    # =========================================================================
    elif view_mode == "Operational Diagnostics":
        st.subheader("Diagnostic Error Analysis & Battery Dynamics")
        st.markdown(
            "Failure mode analysis and state of charge operating dynamics across 1,290 evaluation hours."
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### Battery State of Charge Utilization")
            st.write(
                "- **System C Dynamic Cycling**: 81.24% in intermediate range (15.89% depleted, 2.87% saturated; mean SOC 43.71%)."
            )
            st.write(
                "- **System B Heuristic Inaction**: 99.85% of time stuck at minimum SOC (0.10) after initial discharge."
            )
            st.write(
                "- **System D Oracle Aggressiveness**: 24.88% saturation due to confident overnight charging (mean SOC 55.14%)."
            )
        with col2:
            st.markdown("##### Highest Error Episodes")
            st.write("- **2024-12-25 (Christmas Day)**: Load MAE = 87.95 kW (holiday occupancy deviation).")
            st.write("- **2024-12-27 (Bridge Day)**: Load MAE = 81.22 kW (atypical commercial load).")
            st.write("- **Morning Ramp (07:00–08:00 UTC)**: Highest diurnal variance (MAE = 83.79 kW).")

        fig_path = Path("figures/fig11_error_analysis.png")
        if fig_path.exists():
            st.image(
                str(fig_path),
                caption="Figure 11: Multi-Panel Operational Diagnostic Deep Dive",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
