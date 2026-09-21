"""Unit tests for preprocessing and representative scenario construction."""

from pathlib import Path

import numpy as np

from src.data.preprocess import (
    aggregate_to_hourly,
    calibrate_renewable_scaling,
    load_and_clean_raw_series,
)


def test_preprocessing_pipeline():
    """Verify end-to-end preprocessing produces valid, continuous, uncorrupted hourly data."""
    raw_dir = Path("data/raw")
    if not (raw_dir / "EPEX.parquet").exists():
        return  # Skip if raw data not yet downloaded

    df_15m = load_and_clean_raw_series(
        raw_dir="data/raw",
        load_feeder="load_measurements/mv_feeder/OS Leiden Noord.parquet",
        solar_park="load_measurements/solar_park/Within 10 kilometers of Westwoud_normalized.parquet",
        price_file="EPEX.parquet",
    )

    # Check 15m cleaning
    assert len(df_15m) == 35136
    assert df_15m.isna().sum().sum() == 0
    assert (df_15m["load_kw"] >= 0).all()
    assert (df_15m["solar_factor"] >= 0.0).all()
    assert (df_15m["solar_factor"] <= 1.0).all()

    # Check hourly aggregation
    df_hourly = aggregate_to_hourly(df_15m)
    assert len(df_hourly) == 8784  # 366 days * 24 hours
    assert df_hourly.isna().sum().sum() == 0

    # Check scenario scaling for 40% penetration
    df_scen, meta = calibrate_renewable_scaling(df_hourly, penetration_ratio=0.40)
    assert len(df_scen) == 8784
    assert np.isclose(meta["achieved_penetration"], 0.40, rtol=1e-5)

    # Balance identities
    # net_load = load - solar = deficit - surplus
    balance_error = (df_scen["net_load_kw"] - (df_scen["deficit_kw"] - df_scen["surplus_kw"])).abs()
    assert (balance_error < 1e-6).all()
