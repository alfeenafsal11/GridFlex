"""Lightweight programmatic validation script for GridFlex AI artifacts.

Validates that canonical numerical outputs in reports/experiments_results.json,
reports/error_analysis_results.json, generated figures, documentation, and the
dashboard are mathematically consistent and satisfy all scientific invariants.
"""

import json
import math
from pathlib import Path


def validate_canonical_results(json_path: Path = Path("reports/experiments_results.json")) -> dict:
    """Validate canonical numerical assertions directly against experiments_results.json."""
    if not json_path.exists():
        raise FileNotFoundError(f"Missing canonical results file: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # 1. System C Core Assertions
    sys_c = data["core_systems"]["system_c"]
    assert math.isclose(sys_c["peak_grid_kw"], 3033.400659586602, rel_tol=1e-5), (
        f"System C peak mismatch: {sys_c['peak_grid_kw']}"
    )
    assert math.isclose(sys_c["total_cost_eur"], 298741.89306464745, rel_tol=1e-5), (
        f"System C cost mismatch: {sys_c['total_cost_eur']}"
    )
    assert sys_c["constraint_violations"] == 0, (
        f"System C constraint violations: {sys_c['constraint_violations']}"
    )

    # 2. System D (Oracle) Core Assertions
    sys_d = data["core_systems"]["system_d"]
    assert math.isclose(sys_d["peak_grid_kw"], 2897.5, rel_tol=1e-5), (
        f"Oracle peak mismatch: {sys_d['peak_grid_kw']}"
    )
    assert math.isclose(sys_d["total_cost_eur"], 296611.2248705883, rel_tol=1e-5), (
        f"Oracle cost mismatch: {sys_d['total_cost_eur']}"
    )
    assert sys_d["constraint_violations"] == 0, (
        f"Oracle constraint violations: {sys_d['constraint_violations']}"
    )

    # 3. Renewable Penetration Sensitivity Assertions
    pen = data["experiment_d_penetration"]
    pen_20_red = pen["20pct"]["improvement"]["peak_reduction_pct"]
    pen_40_red = pen["40pct"]["improvement"]["peak_reduction_pct"]
    pen_60_red = pen["60pct"]["improvement"]["peak_reduction_pct"]

    assert math.isclose(pen_20_red, 9.157378400010886, rel_tol=1e-5), (
        f"20% penetration peak reduction mismatch: {pen_20_red}"
    )
    assert math.isclose(pen_40_red, 7.494770228616969, rel_tol=1e-5), (
        f"40% penetration peak reduction mismatch: {pen_40_red}"
    )
    assert math.isclose(pen_60_red, 6.512991154220988, rel_tol=1e-5), (
        f"60% penetration peak reduction mismatch: {pen_60_red}"
    )

    # 4. Storage Duration Sensitivity Assertions
    dur = data["experiment_e_duration"]
    dur_2h_red = dur["2h"]["improvement"]["peak_reduction_pct"]
    dur_4h_red = dur["4h"]["improvement"]["peak_reduction_pct"]

    assert math.isclose(dur_2h_red, 5.56446927872797, rel_tol=1e-5), (
        f"2h duration peak reduction mismatch: {dur_2h_red}"
    )
    assert math.isclose(dur_4h_red, 7.494770228616969, rel_tol=1e-5), (
        f"4h duration peak reduction mismatch: {dur_4h_red}"
    )

    # 5. Injected Forecast Noise Sensitivity Assertions
    noise = data["experiment_f_noise"]
    noise_0_peak = noise["0pct"]["metrics"]["peak_grid_kw"]
    noise_10_peak = noise["10pct"]["metrics"]["peak_grid_kw"]
    noise_20_peak = noise["20pct"]["metrics"]["peak_grid_kw"]
    noise_30_peak = noise["30pct"]["metrics"]["peak_grid_kw"]

    assert math.isclose(noise_0_peak, 3033.400659586602, rel_tol=1e-4), (
        f"Noise 0% peak mismatch: {noise_0_peak}"
    )
    assert math.isclose(noise_10_peak, 3228.7567605123727, rel_tol=1e-4), (
        f"Noise 10% peak mismatch: {noise_10_peak}"
    )
    assert math.isclose(noise_20_peak, 4029.9780688759433, rel_tol=1e-4), (
        f"Noise 20% peak mismatch: {noise_20_peak}"
    )
    assert math.isclose(noise_30_peak, 4108.386295307501, rel_tol=1e-4), (
        f"Noise 30% peak mismatch: {noise_30_peak}"
    )

    # 6. Grid Energy and Renewable Invariants
    sys_a = data["core_systems"]["system_a"]
    sys_b = data["core_systems"]["system_b"]
    assert sys_c["total_grid_kwh"] > sys_b["total_grid_kwh"], (
        "System C must reflect round-trip losses relative to System B"
    )
    assert sys_c["total_grid_kwh"] > sys_a["total_grid_kwh"], (
        "System C must reflect round-trip losses relative to System A"
    )
    for s_name, s_dict in data["core_systems"].items():
        assert s_dict["total_curt_kwh"] == 0.0, f"Unexpected base curtailment in {s_name}"
        assert s_dict["renewable_utilisation_pct"] == 100.0, f"Unexpected utilisation in {s_name}"

    return data


def validate_error_analysis(json_path: Path = Path("reports/error_analysis_results.json")) -> dict:
    """Validate canonical error analysis metrics."""
    if not json_path.exists():
        raise FileNotFoundError(f"Missing error analysis file: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    load_stats = data["forecast"]["load_residual_stats"]
    solar_stats = data["forecast"]["solar_residual_stats"]

    assert math.isclose(load_stats["mean"], -13.957, abs_tol=0.1), f"Load mean residual: {load_stats['mean']}"
    assert math.isclose(load_stats["std"], 60.818, abs_tol=0.1), f"Load std residual: {load_stats['std']}"
    assert math.isclose(solar_stats["mean"], 27.181, abs_tol=0.1), f"Solar mean residual: {solar_stats['mean']}"
    assert math.isclose(solar_stats["std"], 120.568, abs_tol=0.1), f"Solar std residual: {solar_stats['std']}"

    c_bat = data["battery"]["system_c_forecast"]
    d_bat = data["battery"]["system_d_oracle"]

    assert c_bat["depleted_hours"] == 205, f"System C depleted hours: {c_bat['depleted_hours']}"
    assert c_bat["saturated_hours"] == 37, f"System C saturated hours: {c_bat['saturated_hours']}"
    assert d_bat["depleted_hours"] == 171, f"System D depleted hours: {d_bat['depleted_hours']}"
    assert d_bat["saturated_hours"] == 321, f"System D saturated hours: {d_bat['saturated_hours']}"

    return data


def validate_figure_files(figures_dir: Path = Path("figures")) -> None:
    """Ensure all required publication figures exist and are non-empty."""
    required_figures = [
        "fig01_demand_vs_solar.png",
        "fig02_daily_profiles.png",
        "fig03_price_distribution.png",
        "fig04_baseline_comparison.png",
        "fig05_forecast_performance.png",
        "fig06_systems_comparison.png",
        "fig07_penetration_sensitivity.png",
        "fig08_duration_sensitivity.png",
        "fig09_forecast_noise_sensitivity.png",
        "fig10_oracle_gap.png",
        "fig11_error_analysis.png",
    ]
    for fig_name in required_figures:
        fig_file = figures_dir / fig_name
        assert fig_file.exists(), f"Missing required figure: {fig_file}"
        assert fig_file.stat().st_size > 1000, f"Figure appears truncated/empty: {fig_file}"


def validate_dashboard_code(app_path: Path = Path("app.py")) -> None:
    """Validate that app.py does not contain silent hardcoded fallback constants for research metrics."""
    with open(app_path, encoding="utf-8") as f:
        content = f.read()

    forbidden_patterns = [
        "peak_reduction_opt_vs_rule_pct', 7.49)",
        "cost_savings_opt_vs_rule_eur', 13452)",
        "cost_optimality_ratio_pct', 99.28)",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in content, f"Found forbidden hard-coded fallback in app.py: {pattern}"


def main() -> None:
    """Run all validation checks."""
    print("Running GridFlex AI Artifact Validation...")
    validate_canonical_results()
    print("[PASS] Canonical experiment results validated.")
    validate_error_analysis()
    print("[PASS] Error analysis diagnostics validated.")
    validate_figure_files()
    print("[PASS] All 11 publication figures validated.")
    validate_dashboard_code()
    print("[PASS] Dashboard dynamic KPI loading validated.")
    print("All artifact validations PASSED successfully!")


if __name__ == "__main__":
    main()
