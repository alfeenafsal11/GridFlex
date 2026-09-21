"""Causal temporal feature engineering for load and renewable generation forecasting."""

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("features.engineer")


def extract_calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Extract cyclical and categorical calendar features strictly from timestamp index."""
    df_cal = pd.DataFrame(index=index)

    # Hour of day (0-23) + cyclical encoding
    hour = index.hour.to_numpy()
    df_cal["hour"] = hour
    df_cal["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df_cal["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)

    # Day of week (0=Mon, 6=Sun) + cyclical encoding
    dow = index.dayofweek.to_numpy()
    df_cal["dayofweek"] = dow
    df_cal["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df_cal["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)

    # Day of year (1-366) + cyclical encoding
    doy = index.dayofyear.to_numpy()
    df_cal["dayofyear"] = doy
    df_cal["doy_sin"] = np.sin(2 * np.pi * doy / 366.0)
    df_cal["doy_cos"] = np.cos(2 * np.pi * doy / 366.0)

    # Month (1-12)
    df_cal["month"] = index.month.to_numpy()

    # Weekend flag (1 for Sat/Sun, 0 otherwise)
    df_cal["is_weekend"] = (dow >= 5).astype(int)

    return df_cal


def build_causal_time_series_features(
    series: pd.Series,
    prefix: str,
    lags: tuple[int, ...] = (1, 2, 3, 24, 48, 72, 168),
    rolling_windows: tuple[int, ...] = (3, 6, 24, 168),
) -> pd.DataFrame:
    """Build causal lag and backward-looking rolling features from a historical series.
    
    At index t, the observation series[t] is the most recently completed measurement.
    All features represent historical values up to and including time t.
    """
    df_feats = pd.DataFrame(index=series.index)

    # Historical lag features relative to current observation t
    for lag in lags:
        df_feats[f"{prefix}_lag_{lag}"] = series.shift(lag - 1)

    # Backward-looking rolling statistics computed over history up to t
    for window in rolling_windows:
        rolling_obj = series.rolling(window=window, min_periods=window)
        df_feats[f"{prefix}_roll_mean_{window}h"] = rolling_obj.mean()
        if window == 24:
            df_feats[f"{prefix}_roll_std_{window}h"] = rolling_obj.std()

    return df_feats


def construct_feature_matrix(
    df: pd.DataFrame,
    lags: tuple[int, ...] = (1, 2, 3, 24, 48, 72, 168),
    rolling_windows: tuple[int, ...] = (3, 6, 24, 168),
) -> tuple[pd.DataFrame, list[str]]:
    """Construct complete causal feature matrix combining calendar, load, and solar features."""
    cal_feats = extract_calendar_features(df.index)
    load_feats = build_causal_time_series_features(
        df["load_kw"], prefix="load", lags=lags, rolling_windows=rolling_windows
    )
    solar_feats = build_causal_time_series_features(
        df["solar_kw"], prefix="solar", lags=lags, rolling_windows=rolling_windows
    )

    X = pd.concat([cal_feats, load_feats, solar_feats], axis=1)
    feature_names = list(X.columns)

    return X, feature_names


def build_direct_multi_horizon_targets(
    series: pd.Series,
    horizons: int = 24,
) -> pd.DataFrame:
    """Construct direct multi-horizon target matrix.
    
    At feature issuance time t, the target for horizon h is series[t + h].
    """
    targets = pd.DataFrame(index=series.index)
    for h in range(1, horizons + 1):
        targets[f"target_h{h}"] = series.shift(-h)
    return targets
