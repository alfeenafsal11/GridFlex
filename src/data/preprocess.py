"""Data cleaning, alignment, hourly aggregation, and representative scenario construction."""

from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.config import load_yaml_config
from src.utils.logger import get_logger

logger = get_logger("data.preprocess")


def load_and_clean_raw_series(
    raw_dir: str | Path = "data/raw",
    load_feeder: str = "load_measurements/mv_feeder/OS Leiden Noord.parquet",
    solar_park: str = "load_measurements/solar_park/Within 10 kilometers of Westwoud_normalized.parquet",
    price_file: str = "EPEX.parquet",
) -> pd.DataFrame:
    """Load raw 15-minute series, perform causal gap filling, and align onto common 15-minute index."""
    raw_path = Path(raw_dir)

    load_df = pd.read_parquet(raw_path / load_feeder)
    solar_df = pd.read_parquet(raw_path / solar_park)
    price_df = pd.read_parquet(raw_path / price_file)

    logger.info("Loaded raw series: load=%s, solar=%s, price=%s", load_df.shape, solar_df.shape, price_df.shape)

    # Standardize column names and index
    load_df["timestamp"] = pd.to_datetime(load_df["timestamp"], utc=True)
    solar_df["timestamp"] = pd.to_datetime(solar_df["timestamp"], utc=True)
    price_df["timestamp"] = pd.to_datetime(price_df["timestamp"], utc=True)

    load_df = load_df.sort_values("timestamp").set_index("timestamp")
    solar_df = solar_df.sort_values("timestamp").set_index("timestamp")
    price_df = price_df.sort_values("timestamp").set_index("timestamp")

    # Combine into unified 15-minute DataFrame
    df_15m = pd.DataFrame(index=load_df.index)
    df_15m["load_raw_w"] = load_df["load"]
    df_15m["solar_raw_norm"] = solar_df["load"]
    df_15m["epex_raw_eur_mwh"] = price_df["EPEX_NL"]

    # Check and log missingness
    missing_counts = df_15m.isna().sum()
    logger.info("Raw 15-min missing values before cleaning:\n%s", missing_counts)

    # Clean short gaps causally via forward fill (at most 4 consecutive steps = 1 hour)
    # The 3 missing records on 2024-10-27 are strictly within this threshold
    df_15m = df_15m.ffill(limit=4)
    # If any initial row is nan, backward fill safely
    df_15m = df_15m.bfill(limit=4)

    remaining_missing = df_15m.isna().sum().sum()
    if remaining_missing > 0:
        raise ValueError(f"Unresolved missing values remain after cleaning: {df_15m.isna().sum()}")

    # Physical conversion
    # 1. Load: Watts -> Kilowatts
    df_15m["load_kw"] = df_15m["load_raw_w"] / 1000.0
    if (df_15m["load_kw"] < 0).any():
        logger.warning("Detected %d negative load instances. Clamping to 0.0 kW.", (df_15m["load_kw"] < 0).sum())
        df_15m["load_kw"] = df_15m["load_kw"].clip(lower=0.0)

    # 2. Solar: OpenSTEF negative generation convention -> positive capacity factor [0.0, 1.0]
    df_15m["solar_factor"] = (-df_15m["solar_raw_norm"]).clip(lower=0.0, upper=1.0)

    # 3. Price: EUR/MWh -> EUR/kWh
    df_15m["price_eur_kwh"] = df_15m["epex_raw_eur_mwh"] / 1000.0
    df_15m["price_eur_mwh"] = df_15m["epex_raw_eur_mwh"]

    return df_15m[["load_kw", "solar_factor", "price_eur_kwh", "price_eur_mwh"]]


def aggregate_to_hourly(df_15m: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 15-minute power and prices to 1-hour intervals."""
    # Resample with left-closed intervals: 'h' creates 00:00:00 (covering 00:00, 00:15, 00:30, 00:45)
    df_hourly = df_15m.resample("1h").mean()
    logger.info("Aggregated 15-min data to hourly: shape=%s", df_hourly.shape)
    return df_hourly


def calibrate_renewable_scaling(
    df_hourly: pd.DataFrame,
    penetration_ratio: float = 0.40,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Scale solar generation factor so that total annual solar energy equals penetration_ratio * total annual load."""
    total_load_kwh = df_hourly["load_kw"].sum() * 1.0  # 1-hour dt
    total_solar_factor_sum = df_hourly["solar_factor"].sum() * 1.0

    # Calibrate solar capacity in kW
    solar_capacity_kw = (penetration_ratio * total_load_kwh) / total_solar_factor_sum

    df_scenario = df_hourly.copy()
    df_scenario["solar_capacity_kw"] = solar_capacity_kw
    df_scenario["solar_kw"] = df_scenario["solar_factor"] * solar_capacity_kw

    # Compute balance indicators
    df_scenario["net_load_kw"] = df_scenario["load_kw"] - df_scenario["solar_kw"]
    df_scenario["surplus_kw"] = (df_scenario["solar_kw"] - df_scenario["load_kw"]).clip(lower=0.0)
    df_scenario["deficit_kw"] = (df_scenario["load_kw"] - df_scenario["solar_kw"]).clip(lower=0.0)

    total_solar_kwh = df_scenario["solar_kw"].sum() * 1.0
    achieved_penetration = total_solar_kwh / total_load_kwh

    meta = {
        "penetration_target": penetration_ratio,
        "achieved_penetration": achieved_penetration,
        "solar_capacity_kw": solar_capacity_kw,
        "total_load_kwh": total_load_kwh,
        "total_solar_kwh": total_solar_kwh,
        "total_surplus_kwh": df_scenario["surplus_kw"].sum() * 1.0,
        "total_deficit_kwh": df_scenario["deficit_kw"].sum() * 1.0,
    }

    logger.info(
        "Scaled scenario: Target Penetration=%.2f%%, Solar Capacity=%.2f kW, Total Demand=%.2f MWh, Total Solar=%.2f MWh",
        penetration_ratio * 100,
        solar_capacity_kw,
        total_load_kwh / 1000.0,
        total_solar_kwh / 1000.0,
    )

    return df_scenario, meta


def build_processed_dataset(
    config_path: str = "configs/default.yaml",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute end-to-end preprocessing pipeline and save output parquet."""
    cfg = load_yaml_config(config_path)

    raw_dir = cfg["data"]["raw_dir"]
    load_feeder = cfg["data"]["load_feeder"]
    solar_park = cfg["data"]["solar_park"]
    price_file = cfg["data"]["price_file"]
    penetration = cfg["data"]["base_renewable_penetration"]
    processed_dir = Path(cfg["data"]["processed_dir"])
    processed_filename = cfg["data"]["processed_filename"]

    df_15m = load_and_clean_raw_series(
        raw_dir=raw_dir,
        load_feeder=load_feeder,
        solar_park=solar_park,
        price_file=price_file,
    )

    df_hourly = aggregate_to_hourly(df_15m)
    df_processed, meta = calibrate_renewable_scaling(df_hourly, penetration_ratio=penetration)

    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / processed_filename
    df_processed.to_parquet(out_path)
    logger.info("Saved clean hourly dataset to %s", out_path)

    return df_processed, meta


if __name__ == "__main__":
    build_processed_dataset()
