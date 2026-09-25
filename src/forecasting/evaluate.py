"""Chronological forecasting evaluation and benchmarking against persistence."""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.features.engineer import construct_horizon_feature_matrix
from src.forecasting.baseline import generate_persistence_forecasts
from src.forecasting.lightgbm_model import DirectMultiHorizonLGBM
from src.utils.config import load_yaml_config
from src.utils.logger import get_logger

logger = get_logger("forecasting.evaluate")


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute MAE, RMSE, and nRMSE between true and predicted arrays."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mean_val = float(np.mean(y_true))
    nrmse = float(rmse / mean_val) if mean_val > 0 else float("nan")

    return {"mae": mae, "rmse": rmse, "nrmse": nrmse}


def run_forecasting_pipeline(
    data_path: str = "data/processed/gridflex_hourly.parquet",
    config_path: str = "configs/default.yaml",
    figures_dir: str = "figures",
    processed_dir: str = "data/processed",
) -> dict[str, Any]:
    """Execute end-to-end model training, test-set evaluation, and figure generation."""
    df = pd.read_parquet(data_path)
    cfg = load_yaml_config(config_path)
    f_cfg = cfg["forecasting"]
    horizons = f_cfg["target_horizon_hours"]

    # Maximum lag is 168h; maximum forward horizon is 24h
    # Common valid index ensures exact same evaluation points for all horizons
    valid_start_idx = 168
    valid_end_idx = len(df) - horizons
    valid_df = df.iloc[valid_start_idx:valid_end_idx]

    n_total = len(valid_df)
    n_train = int(f_cfg["train_split"] * n_total)
    n_val = int(f_cfg["val_split"] * n_total)
    n_test = n_total - n_train - n_val

    train_slice = slice(0, n_train)
    val_slice = slice(n_train, n_train + n_val)
    test_slice = slice(n_train + n_val, n_total)

    test_index = valid_df.index[test_slice]

    logger.info(
        "Chronological Splits: Total=%d, Train=%d (%.1f%%), Val=%d (%.1f%%), Test=%d (%.1f%%)",
        n_total,
        n_train,
        n_train / n_total * 100,
        n_val,
        n_val / n_total * 100,
        n_test,
        n_test / n_total * 100,
    )

    horizons_list = list(range(1, horizons + 1))
    eval_results: dict[str, Any] = {
        "load": {"lightgbm": {}, "persistence": {}},
        "solar": {"lightgbm": {}, "persistence": {}},
    }

    # Store prediction columns for test dataframe
    test_predictions_dict: dict[str, pd.Series] = {}
    pers_load_df = generate_persistence_forecasts(df["load_kw"], horizons=horizons)
    pers_solar_df = generate_persistence_forecasts(df["solar_kw"], horizons=horizons)

    models_load = {}
    models_solar = {}

    logger.info("Training direct LightGBM models across 24 horizons...")
    for h in horizons_list:
        X_h, _feat_names = construct_horizon_feature_matrix(df, h=h)
        y_load_h = df["load_kw"].shift(-h)
        y_solar_h = df["solar_kw"].shift(-h)

        # Slice to valid common range
        X_valid = X_h.iloc[valid_start_idx:valid_end_idx]
        y_load_valid = y_load_h.iloc[valid_start_idx:valid_end_idx]
        y_solar_valid = y_solar_h.iloc[valid_start_idx:valid_end_idx]

        X_tr, X_vl, X_te = X_valid.iloc[train_slice], X_valid.iloc[val_slice], X_valid.iloc[test_slice]
        y_load_tr, y_load_vl, y_load_te = (
            y_load_valid.iloc[train_slice],
            y_load_valid.iloc[val_slice],
            y_load_valid.iloc[test_slice],
        )
        y_solar_tr, y_solar_vl, y_solar_te = (
            y_solar_valid.iloc[train_slice],
            y_solar_valid.iloc[val_slice],
            y_solar_valid.iloc[test_slice],
        )

        # Train Load Model
        lgb_load = DirectMultiHorizonLGBM(horizons=1, lgb_params=f_cfg["lightgbm_params"], min_val=0.0)
        lgb_load.fit(X_tr, pd.DataFrame({"target_h1": y_load_tr}), X_vl, pd.DataFrame({"target_h1": y_load_vl}))
        models_load[h] = lgb_load
        pred_load_h = lgb_load.predict(X_te)["pred_h1"]

        # Train Solar Model
        lgb_solar = DirectMultiHorizonLGBM(horizons=1, lgb_params=f_cfg["lightgbm_params"], min_val=0.0)
        lgb_solar.fit(X_tr, pd.DataFrame({"target_h1": y_solar_tr}), X_vl, pd.DataFrame({"target_h1": y_solar_vl}))
        models_solar[h] = lgb_solar
        pred_solar_h = lgb_solar.predict(X_te)["pred_h1"]

        # Persistence on test set
        pers_load_h = pers_load_df.loc[test_index, f"pred_h{h}"]
        pers_solar_h = pers_solar_df.loc[test_index, f"pred_h{h}"]

        # Store test outputs
        test_predictions_dict[f"actual_load_h{h}"] = y_load_te
        test_predictions_dict[f"pred_load_lgbm_h{h}"] = pred_load_h
        test_predictions_dict[f"pred_load_pers_h{h}"] = pers_load_h

        test_predictions_dict[f"actual_solar_h{h}"] = y_solar_te
        test_predictions_dict[f"pred_solar_lgbm_h{h}"] = pred_solar_h
        test_predictions_dict[f"pred_solar_pers_h{h}"] = pers_solar_h

        # Compute per-horizon metrics
        eval_results["load"]["lightgbm"][h] = compute_metrics(y_load_te.to_numpy(), pred_load_h.to_numpy())
        eval_results["load"]["persistence"][h] = compute_metrics(y_load_te.to_numpy(), pers_load_h.to_numpy())

        eval_results["solar"]["lightgbm"][h] = compute_metrics(y_solar_te.to_numpy(), pred_solar_h.to_numpy())
        eval_results["solar"]["persistence"][h] = compute_metrics(y_solar_te.to_numpy(), pers_solar_h.to_numpy())

    test_predictions = pd.DataFrame(test_predictions_dict, index=test_index)

    # Compute overall aggregate metrics across all 24 horizons
    all_true_load = np.concatenate([test_predictions[f"actual_load_h{h}"].to_numpy() for h in horizons_list])
    all_lgbm_load = np.concatenate([test_predictions[f"pred_load_lgbm_h{h}"].to_numpy() for h in horizons_list])
    all_pers_load = np.concatenate([test_predictions[f"pred_load_pers_h{h}"].to_numpy() for h in horizons_list])

    all_true_solar = np.concatenate([test_predictions[f"actual_solar_h{h}"].to_numpy() for h in horizons_list])
    all_lgbm_solar = np.concatenate([test_predictions[f"pred_solar_lgbm_h{h}"].to_numpy() for h in horizons_list])
    all_pers_solar = np.concatenate([test_predictions[f"pred_solar_pers_h{h}"].to_numpy() for h in horizons_list])

    summary_metrics = {
        "load_aggregate": {
            "lightgbm": compute_metrics(all_true_load, all_lgbm_load),
            "persistence": compute_metrics(all_true_load, all_pers_load),
        },
        "solar_aggregate": {
            "lightgbm": compute_metrics(all_true_solar, all_lgbm_solar),
            "persistence": compute_metrics(all_true_solar, all_pers_solar),
        },
    }

    load_mae_gain = (
        summary_metrics["load_aggregate"]["persistence"]["mae"] - summary_metrics["load_aggregate"]["lightgbm"]["mae"]
    ) / summary_metrics["load_aggregate"]["persistence"]["mae"]

    solar_mae_gain = (
        summary_metrics["solar_aggregate"]["persistence"]["mae"] - summary_metrics["solar_aggregate"]["lightgbm"]["mae"]
    ) / summary_metrics["solar_aggregate"]["persistence"]["mae"]

    summary_metrics["improvements"] = {
        "load_mae_reduction_pct": float(load_mae_gain * 100),
        "solar_mae_reduction_pct": float(solar_mae_gain * 100),
    }

    logger.info("Forecasting Evaluation Summary on Held-Out Test Set:")
    logger.info(
        "Load Demand - LightGBM MAE: %.2f kW, Persistence MAE: %.2f kW (Improvement: %.1f%%)",
        summary_metrics["load_aggregate"]["lightgbm"]["mae"],
        summary_metrics["load_aggregate"]["persistence"]["mae"],
        load_mae_gain * 100,
    )
    logger.info(
        "Solar Generation - LightGBM MAE: %.2f kW, Persistence MAE: %.2f kW (Improvement: %.1f%%)",
        summary_metrics["solar_aggregate"]["lightgbm"]["mae"],
        summary_metrics["solar_aggregate"]["persistence"]["mae"],
        solar_mae_gain * 100,
    )

    # Save outputs
    out_preds_path = Path(processed_dir) / "test_predictions.parquet"
    test_predictions.to_parquet(out_preds_path)
    logger.info("Saved test predictions to %s", out_preds_path)

    out_metrics_path = Path(processed_dir) / "forecast_metrics.json"
    with open(out_metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": summary_metrics,
                "per_horizon": eval_results,
            },
            f,
            indent=2,
        )
    logger.info("Saved forecast metrics to %s", out_metrics_path)

    # Generate Figure 5
    generate_figure_5(eval_results, test_predictions, figures_dir=figures_dir)

    return {
        "summary_metrics": summary_metrics,
        "eval_results": eval_results,
        "test_predictions": test_predictions,
        "models": {"load": models_load, "solar": models_solar},
    }


def generate_figure_5(
    eval_results: dict[str, Any],
    test_predictions: pd.DataFrame,
    figures_dir: str = "figures",
) -> Path:
    """Generate Figure 5 directly from evaluation results and test predictions."""
    fig_dir = Path(figures_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig5_path = fig_dir / "fig05_forecast_performance.png"

    horizons_list = list(range(1, 25))
    _fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    def get_mae(series: str, model: str, h: int) -> float:
        sub = eval_results[series][model]
        if h in sub:
            return float(sub[h]["mae"])
        return float(sub[str(h)]["mae"])

    # Top-Left: Load Error across Horizons
    load_lgbm_mae = [get_mae("load", "lightgbm", h) for h in horizons_list]
    load_pers_mae = [get_mae("load", "persistence", h) for h in horizons_list]
    axes[0, 0].plot(horizons_list, load_lgbm_mae, "o-", color="#1f77b4", label="LightGBM MAE (kW)", lw=2)
    axes[0, 0].plot(horizons_list, load_pers_mae, "s--", color="#7f7f7f", label="Persistence MAE (kW)", lw=2)
    axes[0, 0].set_title("Electrical Demand: MAE vs Forecast Horizon", fontsize=11, fontweight="bold")
    axes[0, 0].set_xlabel("Horizon h (Hours)")
    axes[0, 0].set_ylabel("MAE (kW)")
    axes[0, 0].set_xticks(horizons_list)
    axes[0, 0].grid(True, linestyle=":", alpha=0.6)
    axes[0, 0].legend()

    # Top-Right: Solar Error across Horizons
    solar_lgbm_mae = [get_mae("solar", "lightgbm", h) for h in horizons_list]
    solar_pers_mae = [get_mae("solar", "persistence", h) for h in horizons_list]
    axes[0, 1].plot(horizons_list, solar_lgbm_mae, "o-", color="#ff7f0e", label="LightGBM MAE (kW)", lw=2)
    axes[0, 1].plot(horizons_list, solar_pers_mae, "s--", color="#7f7f7f", label="Persistence MAE (kW)", lw=2)
    axes[0, 1].set_title("Solar Generation: MAE vs Forecast Horizon", fontsize=11, fontweight="bold")
    axes[0, 1].set_xlabel("Horizon h (Hours)")
    axes[0, 1].set_ylabel("MAE (kW)")
    axes[0, 1].set_xticks(horizons_list)
    axes[0, 1].grid(True, linestyle=":", alpha=0.6)
    axes[0, 1].legend()

    # Bottom: Sample 5-day Test Window Trajectory (h=1)
    sample_sub = test_predictions.iloc[100:220]
    axes[1, 0].plot(sample_sub.index, sample_sub["actual_load_h1"], label="Actual Demand", color="black", lw=1.5)
    axes[1, 0].plot(
        sample_sub.index, sample_sub["pred_load_lgbm_h1"], label="LightGBM (h=1)", color="#1f77b4", lw=2, linestyle="--"
    )
    axes[1, 0].plot(
        sample_sub.index, sample_sub["pred_load_pers_h1"], label="Persistence (h=1)", color="#7f7f7f", lw=1, linestyle=":"
    )
    axes[1, 0].set_title("Demand Trajectory Sample (Test Period, h=1)", fontsize=11, fontweight="bold")
    axes[1, 0].set_ylabel("Power (kW)")
    axes[1, 0].grid(True, linestyle=":", alpha=0.6)
    axes[1, 0].legend(loc="upper right")

    axes[1, 1].plot(sample_sub.index, sample_sub["actual_solar_h1"], label="Actual Solar", color="black", lw=1.5)
    axes[1, 1].plot(
        sample_sub.index, sample_sub["pred_solar_lgbm_h1"], label="LightGBM (h=1)", color="#ff7f0e", lw=2, linestyle="--"
    )
    axes[1, 1].plot(
        sample_sub.index, sample_sub["pred_solar_pers_h1"], label="Persistence (h=1)", color="#7f7f7f", lw=1, linestyle=":"
    )
    axes[1, 1].set_title("Solar Trajectory Sample (Test Period, h=1)", fontsize=11, fontweight="bold")
    axes[1, 1].set_ylabel("Power (kW)")
    axes[1, 1].grid(True, linestyle=":", alpha=0.6)
    axes[1, 1].legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(fig5_path, dpi=200)
    plt.close()
    logger.info("Saved Figure 5 to %s", fig5_path)
    return fig5_path


if __name__ == "__main__":
    import sys

    if "--figures-only" in sys.argv:
        metrics_file = Path("data/processed/forecast_metrics.json")
        preds_file = Path("data/processed/test_predictions.parquet")
        with open(metrics_file, encoding="utf-8") as f_in:
            m_data = json.load(f_in)
        preds_df = pd.read_parquet(preds_file)
        generate_figure_5(m_data["per_horizon"], preds_df)
    else:
        run_forecasting_pipeline()
