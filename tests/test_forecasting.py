"""Unit tests for forecasting models and persistence baseline."""

import numpy as np
import pandas as pd

from src.forecasting.baseline import generate_persistence_forecasts
from src.forecasting.evaluate import compute_metrics
from src.forecasting.lightgbm_model import DirectMultiHorizonLGBM


def test_persistence_forecast_shape_and_values():
    """Verify persistence forecasts shift by exactly 24-h steps."""
    dates = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    series = pd.Series(range(100), index=dates, dtype=float)

    pers = generate_persistence_forecasts(series, horizons=24)
    assert pers.shape == (100, 24)

    # For h=24: forecast(t+24) = series[t]. lag_steps = 24 - 24 = 0.
    assert pers.iloc[50]["pred_h24"] == 50.0

    # For h=1: forecast(t+1) = series[t+1-24] = series[t-23]. lag_steps = 23.
    assert pers.iloc[50]["pred_h1"] == 50.0 - 23.0


def test_compute_metrics():
    """Verify standard metric calculations."""
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 20.0, 28.0])

    res = compute_metrics(y_true, y_pred)
    # Errors: [2, 0, -2] -> MAE = 4/3 = 1.3333
    assert np.isclose(res["mae"], 4.0 / 3.0)
    # RMSE = sqrt(8/3) = 1.63299
    assert np.isclose(res["rmse"], np.sqrt(8.0 / 3.0))
    # Mean = 20 -> nRMSE = RMSE / 20
    assert np.isclose(res["nrmse"], res["rmse"] / 20.0)


def test_direct_lgbm_fit_and_predict():
    """Verify LightGBM training on miniature dataset."""
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    X = pd.DataFrame(
        {"feat1": rng.standard_normal(n), "feat2": rng.standard_normal(n)},
        index=dates,
    )
    Y = pd.DataFrame(
        {f"target_h{h}": np.abs(X["feat1"] * 2 + rng.standard_normal(n) * 0.1) for h in range(1, 5)},
        index=dates,
    )

    model = DirectMultiHorizonLGBM(horizons=4, min_val=0.0)
    model.fit(X.iloc[:150], Y.iloc[:150], X.iloc[150:], Y.iloc[150:])

    preds = model.predict(X.iloc[150:])
    assert preds.shape == (50, 4)
    assert (preds >= 0.0).all().all()
