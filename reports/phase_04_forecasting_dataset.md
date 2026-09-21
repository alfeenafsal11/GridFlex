# Phase 4 Report — Forecasting Dataset and Temporal Leakage Verification

## 1. Objective
Construct a strictly causal, multi-horizon feature matrix for 24-hour lookahead forecasting of electricity demand (`load_kw`) and renewable generation (`solar_kw`), and establish an automated perturbation-based temporal leakage audit to guarantee zero lookahead bias.

## 2. Feature Specification (35 Causal Predictors)

### A. Calendar & Cyclical Features (11 Features)
- `hour` (0–23): Categorical integer
- `hour_sin`, `hour_cos`: Cyclical diurnal transformation: $\sin(2\pi h / 24)$, $\cos(2\pi h / 24)$
- `dayofweek` (0–6): Monday through Sunday
- `dow_sin`, `dow_cos`: Weekly cyclical transformation: $\sin(2\pi d / 7)$, $\cos(2\pi d / 7)$
- `dayofyear` (1–366): Leap year annual index
- `doy_sin`, `doy_cos`: Annual seasonal transformation: $\sin(2\pi d / 366)$, $\cos(2\pi d / 366)$
- `month` (1–12): Calendar month
- `is_weekend` (0 or 1): Indicator for Saturday and Sunday

### B. Demand Series Lags and Rolling Statistics (12 Features)
- **Lags relative to issuance time $t_0$**: $t_0, t_0-1, t_0-2, t_0-23, t_0-47, t_0-71, t_0-167$ (representing lags 1, 2, 3, 24, 48, 72, 168 hours).
- **Backward-looking Rolling Statistics**:
  - `load_roll_mean_3h`: 3-hour backward moving average
  - `load_roll_mean_6h`: 6-hour backward moving average
  - `load_roll_mean_24h`: 24-hour backward moving average
  - `load_roll_std_24h`: 24-hour backward moving standard deviation
  - `load_roll_mean_168h`: 168-hour (7-day) backward moving average

### C. Solar Series Lags and Rolling Statistics (12 Features)
- **Lags relative to issuance time $t_0$**: Lags 1, 2, 3, 24, 48, 72, 168 hours.
- **Backward-looking Rolling Statistics**:
  - `solar_roll_mean_3h`: 3-hour backward moving average
  - `solar_roll_mean_6h`: 6-hour backward moving average
  - `solar_roll_mean_24h`: 24-hour backward moving average
  - `solar_roll_std_24h`: 24-hour backward moving standard deviation
  - `solar_roll_mean_168h`: 168-hour (7-day) backward moving average

## 3. Direct Multi-Horizon Target Formulation
For each forecast issuance time $t_0$, separate direct forecasting models will predict horizons $h \in \{1, 2, \dots, 24\}$:
$$y_{t_0 + h} = f_h(\mathbf{x}(t_0)) + \epsilon$$
Target columns: `target_h1`, `target_h2`, $\dots$, `target_h24`.
This direct formulation avoids error accumulation inherent in autoregressive recursive multi-step forecasting while maintaining strict causal decoupling between decision time $t_0$ and target time $t_0 + h$.

## 4. Automated Perturbation Leakage Audit
- **Methodology**:
  1. For sampled timestamps across all seasons, the original feature row $\mathbf{x}(t_0)$ is extracted.
  2. Future measurements at $t_0 + 1, t_0 + 5, t_0 + 12, t_0 + 24, t_0 + 48$ are drastically corrupted with artificial noise ($9.99 \times 10^9$).
  3. The feature pipeline is re-executed on the corrupted dataset to produce $\mathbf{x}_{corrupted}(t_0)$.
  4. The maximum absolute difference $\|\mathbf{x}_{corrupted}(t_0) - \mathbf{x}_{original}(t_0)\|_\infty$ is measured.
  5. As a sensitivity control, past observation at $t_0 - 1$ is corrupted to verify that $\mathbf{x}(t_0)$ responds.
- **Results**:
  - Tested Points: 6 distinct timestamps across 2024.
  - Future Invariance Max Difference: **0.000000** (Zero leakage).
  - Past Sensitivity Difference: **$9.99 \times 10^9$** (Confirmed sensitive).
  - Detected Violations: **0**.

## 5. Acceptance Gate Status
- [x] Causal feature matrix implemented and verified.
- [x] All 35 features constructed strictly from historical observations up to $t_0$.
- [x] Multi-horizon target shifting verified.
- [x] Automated perturbation leakage audit passes with 0 violations.
- [x] Unit test suite passes (`tests/test_features.py`).
- **GATE STATUS: PASSED**
