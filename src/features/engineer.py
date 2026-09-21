"""Causal temporal feature engineering for load and renewable generation forecasting."""

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("features.engineer")


def extract_calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Extract cyclical and categorical calendar features strictly from timestamp index."""
    df_cal = pd.DataFrame(index=index)

    hour = index.hour.to_numpy()
    df_cal["hour"] = hour
    df_cal["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df_cal["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)

    dow = index.dayofweek.to_numpy()
    df_cal["dayofweek"] = dow
    df_cal["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df_cal["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)

    doy = index.dayofyear.to_numpy()
    df_cal["dayofyear"] = doy
    df_cal["doy_sin"] = np.sin(2 * np.pi * doy / 366.0)
    df_cal["doy_cos"] = np.cos(2 * np.pi * doy / 366.0)

    df_cal["month"] = index.month.to_numpy()
    df_cal["is_weekend"] = (dow >= 5).astype(int)

    return df_cal


def build_causal_time_series_features(
    series: pd.Series,
    prefix: str,
    lags: tuple[int, ...] = (1, 2, 3, 24, 48, 72, 168),
    rolling_windows: tuple[int, ...] = (3, 6, 24, 168),
) -> pd.DataFrame:
    """Build causal lag and backward-looking rolling features from historical series."""
    df_feats = pd.DataFrame(index=series.index)

    for lag in lags:
        df_feats[f"{prefix}_lag_{lag}"] = series.shift(lag - 1)

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
    """Construct causal feature matrix combining calendar, load, and solar features."""
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


def construct_horizon_feature_matrix(
    df: pd.DataFrame,
    h: int,
) -> tuple[pd.DataFrame, list[str]]:
    """Construct causal feature matrix customized for direct forecasting horizon h (1..24).
    
    At decision time t0, when forecasting target at t0 + h:
    - Recent conditions up to t0 (lags 1, 2, 3; rolling means 3h, 6h, 24h).
    - Calendar features of the TARGET time t0 + h (hour, day of week, cyclical encodings).
    - Historical observations at the SAME HOUR OF DAY as target (24h, 48h, 168h before target).
      Notice: for h in 1..24, (t0 + h - 24) <= t0, so all historical lags are strictly known at t0!
    """
    # 1. Target timestamp calendar features
    target_index = df.index + pd.Timedelta(hours=h)
    target_cal = extract_calendar_features(target_index)
    target_cal.index = df.index  # Align back to issuance index t0
    target_cal.columns = [f"target_{c}" for c in target_cal.columns]

    # 2. Recent conditions at issuance time t0
    recent_feats = pd.DataFrame(index=df.index)
    for prefix in ["load", "solar"]:
        s = df[f"{prefix}_kw"]
        recent_feats[f"{prefix}_current"] = s
        recent_feats[f"{prefix}_lag1"] = s.shift(1)
        recent_feats[f"{prefix}_lag2"] = s.shift(2)
        recent_feats[f"{prefix}_roll_3h"] = s.rolling(3, min_periods=3).mean()
        recent_feats[f"{prefix}_roll_6h"] = s.rolling(6, min_periods=6).mean()
        recent_feats[f"{prefix}_roll_24h"] = s.rolling(24, min_periods=24).mean()

        # 3. Target-aligned historical seasonal lags strictly known at t0
        # Target is at t0 + h. Observation 24h prior to target was at t0 + h - 24.
        # In pandas shift, s.shift(24 - h) at t0 produces s[t0 - (24 - h)] = s[t0 + h - 24].
        recent_feats[f"{prefix}_target_same_hour_d1"] = s.shift(24 - h)
        recent_feats[f"{prefix}_target_same_hour_d2"] = s.shift(48 - h)
        recent_feats[f"{prefix}_target_same_hour_w1"] = s.shift(168 - h)

    X_h = pd.concat([target_cal, recent_feats], axis=1)
    return X_h, list(X_h.columns)


def build_direct_multi_horizon_targets(
    series: pd.Series,
    horizons: int = 24,
) -> pd.DataFrame:
    """Construct direct multi-horizon target matrix."""
    targets = pd.DataFrame(index=series.index)
    for h in range(1, horizons + 1):
        targets[f"target_h{h}"] = series.shift(-h)
    return targets
