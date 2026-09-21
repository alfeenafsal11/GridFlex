"""Persistence baseline forecaster for 24-hour lookahead multi-step predictions."""

import pandas as pd


def generate_persistence_forecasts(
    series: pd.Series,
    horizons: int = 24,
) -> pd.DataFrame:
    """Generate 24-hour seasonal persistence forecasts.
    
    For horizon h in 1..24 at issuance time t0:
    forecast(t0 + h) = series[t0 + h - 24].
    Since h <= 24, (t0 + h - 24) <= t0, so this observation is strictly in the past or present.
    """
    forecasts = pd.DataFrame(index=series.index)
    for h in range(1, horizons + 1):
        lag_steps = 24 - h
        forecasts[f"pred_h{h}"] = series.shift(lag_steps)

    return forecasts
