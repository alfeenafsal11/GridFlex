"""Automated temporal leakage verification routine for forecasting feature matrix."""

from typing import Any

import pandas as pd

from src.features.engineer import construct_feature_matrix
from src.utils.logger import get_logger

logger = get_logger("features.leakage_check")


def run_perturbation_leakage_audit(
    df: pd.DataFrame,
    test_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Verify that features at time t0 are mathematically invariant to future observations (t > t0)."""
    if test_indices is None:
        # Sample points across different months, ensuring ample history (> 168h) and future (> 24h)
        test_indices = [300, 1000, 2500, 4000, 6000, 7500]

    X_orig, feature_names = construct_feature_matrix(df)

    audit_results = {
        "num_features": len(feature_names),
        "tested_points": len(test_indices),
        "violations": 0,
        "details": [],
    }

    for t0_idx in test_indices:
        t0_timestamp = df.index[t0_idx]
        orig_row = X_orig.iloc[t0_idx].copy()

        # Corrupt future points (t0 + 1, t0 + 5, t0 + 24)
        df_corrupted = df.copy()
        for offset in [1, 5, 12, 24, 48]:
            if t0_idx + offset < len(df):
                df_corrupted.iloc[t0_idx + offset, df.columns.get_loc("load_kw")] = 9.99e9
                df_corrupted.iloc[t0_idx + offset, df.columns.get_loc("solar_kw")] = 9.99e9

        # Recompute feature matrix on future-corrupted data
        X_corrupted, _ = construct_feature_matrix(df_corrupted)
        corrupted_row = X_corrupted.iloc[t0_idx].copy()

        # Compute maximum absolute difference between clean and future-corrupted features
        diff = (orig_row - corrupted_row).abs()
        max_diff = float(diff.max())

        # Sensitivity check: verify that modifying a PAST point DOES alter the features
        df_past_corrupted = df.copy()
        df_past_corrupted.iloc[t0_idx - 1, df.columns.get_loc("load_kw")] = 9.99e9
        X_past_corrupted, _ = construct_feature_matrix(df_past_corrupted)
        past_diff = (X_past_corrupted.iloc[t0_idx] - orig_row).abs().max()

        passed = (max_diff == 0.0) and (past_diff > 0.0)
        if not passed:
            audit_results["violations"] += 1

        audit_results["details"].append(
            {
                "index": t0_idx,
                "timestamp": str(t0_timestamp),
                "future_invariance_max_diff": max_diff,
                "past_sensitivity_diff": float(past_diff),
                "status": "PASSED" if passed else "FAILED",
            }
        )

    # Check horizon-specific features across h=1..24
    from src.features.engineer import construct_horizon_feature_matrix
    for h in [1, 6, 12, 18, 24]:
        X_h_orig, _ = construct_horizon_feature_matrix(df, h=h)
        for t0_idx in test_indices:
            df_corrupted = df.copy()
            for offset in [1, 5, 12, 24]:
                if t0_idx + offset < len(df):
                    df_corrupted.iloc[t0_idx + offset, df.columns.get_loc("load_kw")] = 9.99e9
                    df_corrupted.iloc[t0_idx + offset, df.columns.get_loc("solar_kw")] = 9.99e9
            X_h_corrupted, _ = construct_horizon_feature_matrix(df_corrupted, h=h)
            h_diff = float((X_h_orig.iloc[t0_idx] - X_h_corrupted.iloc[t0_idx]).abs().max())
            if h_diff > 0.0:
                audit_results["violations"] += 1
                logger.error("Horizon %d leakage violation at index %d: diff=%.6e", h, t0_idx, h_diff)

    logger.info(
        "Temporal Leakage Audit: %d/%d test points passed (Violations: %d).",
        len(test_indices) - audit_results["violations"],
        len(test_indices),
        audit_results["violations"],
    )

    if audit_results["violations"] > 0:
        raise AssertionError(f"Temporal data leakage detected! Details: {audit_results['details']}")

    return audit_results


if __name__ == "__main__":
    df = pd.read_parquet("data/processed/gridflex_hourly.parquet")
    run_perturbation_leakage_audit(df)
