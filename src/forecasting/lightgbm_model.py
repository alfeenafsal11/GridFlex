"""Direct multi-horizon LightGBM forecasting models."""

from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("forecasting.lightgbm")


class DirectMultiHorizonLGBM:
    """Collection of 24 independent LightGBM regressors for multi-horizon forecasting."""

    def __init__(self, horizons: int = 24, lgb_params: dict[str, Any] | None = None, min_val: float = 0.0):
        self.horizons = horizons
        self.min_val = min_val
        self.models: dict[int, lgb.LGBMRegressor] = {}
        self.params = lgb_params or {
            "objective": "regression",
            "metric": "rmse",
            "boosting_type": "gbdt",
            "n_estimators": 150,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        }

    def fit(
        self,
        X_train: pd.DataFrame,
        Y_train: pd.DataFrame,
        X_val: pd.DataFrame | None = None,
        Y_val: pd.DataFrame | None = None,
    ) -> "DirectMultiHorizonLGBM":
        """Train an independent model for each horizon h in 1..horizons."""
        logger.info("Training %d direct LightGBM models...", self.horizons)
        for h in range(1, self.horizons + 1):
            col = f"target_h{h}"
            y_tr = Y_train[col]

            model = lgb.LGBMRegressor(**self.params)
            if X_val is not None and Y_val is not None:
                y_vl = Y_val[col]
                model.fit(
                    X_train,
                    y_tr,
                    eval_set=[(X_val, y_vl)],
                    callbacks=[lgb.early_stopping(stopping_rounds=15, verbose=False)],
                )
            else:
                model.fit(X_train, y_tr)

            self.models[h] = model

        logger.info("Successfully trained all %d models.", self.horizons)
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """Generate predictions for all horizons h in 1..horizons, enforcing physical non-negativity."""
        preds = pd.DataFrame(index=X.index)
        for h in range(1, self.horizons + 1):
            raw_pred = self.models[h].predict(X)
            preds[f"pred_h{h}"] = np.maximum(self.min_val, raw_pred)

        return preds
