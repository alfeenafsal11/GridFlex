# GridFlex AI — Forecast-Driven Renewable Energy Storage and Grid Flexibility Optimization

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests: pytest](https://img.shields.io/badge/tests-30%20passed-brightgreen.svg)](https://docs.pytest.org/)
[![IRENA Youth Forum 2027](https://img.shields.io/badge/IRENA%20Youth%20Forum-2027%20Submission-orange.svg)](https://www.irena.org/)

An end-to-end, reproducible, and mathematically constrained research prototype investigating how machine-learning-based forecasting combined with rolling-horizon battery optimization provides flexibility in a renewable-integrated distribution grid environment.

---

## 1. Problem

As distribution grids incorporate increasing levels of variable renewable energy (VRE), distribution system operators (DSOs) experience steep ramp rates, localized substation congestion, and pronounced evening demand peaks. While battery energy storage systems (BESS) offer fast-acting flexibility, simple reactive operational strategies—such as surplus-following controllers that only actuate when local solar generation exceeds local load—remain common in behind-the-meter and distribution installations. In low-solar seasonal conditions, these reactive heuristics can remain almost entirely idle, failing to alleviate grid peaks or capture economic value.

GridFlex AI investigates the following research question:
> *Can machine-learning-based forecasts combined with constrained rolling-horizon battery optimization reduce peak grid demand and electricity costs relative to a simple surplus-following battery controller?*

### The Scientific Conclusion
The held-out evaluation shows that forecast-informed receding-horizon battery optimization can materially reduce peak grid demand and electricity cost relative to a simple surplus-following battery controller. However, the base winter evaluation does not demonstrate reduced total grid energy consumption or improved renewable utilisation; GridFlex AI primarily provides temporal energy shifting, peak shaving and price-aware storage flexibility under the tested conditions.

---

## 2. Approach

GridFlex AI couples multi-horizon machine learning forecasting with rolling-horizon linear programming (LP) under a receding-horizon Model Predictive Control (MPC) framework, simulated on a deterministic battery physical simulator:

```text
    Alliander Open Benchmark (2024) + EPEX Day-Ahead Hourly Spot Prices
                               │
                               ▼
               Phase 1 & 2: Ingestion & Preprocessing
            (8,784 hourly UTC records, 40% solar calibration)
                               │
                               ▼
               Phase 4: Causal Feature Engineering
          (35 predictors, 0-lookahead perturbation verified)
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
        Solar Generation              Consumer Demand
      24 Direct LightGBMs           24 Direct LightGBMs
                │                             │
                └──────────────┬──────────────┘
                               ▼
             Phase 7: Constrained Linear Programming
               (SciPy HiGHS Solver, Multi-Objective)
                               │
                               ▼
             Phase 8: Receding-Horizon Control (MPC)
                (Single-action actuation protocol)
                               │
                               ▼
             Phase 6: Physical Battery Simulator
     (Exact nodal balance, η_rt=90.25%, SOC in [10%, 90%])
                               │
                               ▼
         Phase 9–12: Comparative Evaluation & Diagnostics
     (Systems A, B, C, D + Parametric Sensitivity Sweeps)
```

1. **Direct Multi-Horizon Forecasting**: 48 independent LightGBM regressors forecast consumer demand ($h=1 \dots 24$) and solar PV generation ($h=1 \dots 24$) using 35 strictly causal predictors (calendar encodings, historic lags, rolling statistics) with zero future lookahead.
2. **Constrained Linear Optimization**: Formulates a 24-hour multi-objective LP balancing grid electricity cost minimization, peak grid import penalties, curtailment prevention, and battery degradation regularization, subject to physical power, state-of-charge (SOC), and nodal conservation constraints.
3. **Receding-Horizon MPC**: At each hourly step $t$, the controller solves the 24-hour optimization, executes only the first-hour battery power command ($P_{charge}^*, P_{discharge}^*$), advances the clock by 1 hour, receives actual realization feedback, and repeats.
4. **Physical Battery Simulator**: Actuates commands against an independent physical battery model enforcing inverter limits, sub-cycle efficiency losses ($\eta_c = \eta_d = 0.95$, $\eta_{rt} = 90.25\%$), and SOC bounds ($\text{SOC} \in [0.10, 0.90]$).

---

## 3. Experimental Setup

- **Primary Dataset**: Open benchmark from Alliander/Liander (`load_measurements/mv_feeder/OS Leiden Noord.parquet`), normalized solar park generation (`Within 10 kilometers of Westwoud_normalized.parquet`), and Dutch EPEX day-ahead spot market prices (`EPEX.parquet`) spanning full calendar year 2024.
- **Renewable Scaling**: Calibrated to a 40.0% annual energy penetration ($C_{solar} = 4,833.02\text{ kW}$, generating 6,518.74 MWh against 16,296.84 MWh total annual demand).
- **Chronological Split**:
  - Training: 2024-01-01 00:00 to 2024-09-13 14:00 UTC (6,150 hours, 70%)
  - Validation: 2024-09-13 15:00 to 2024-11-06 05:00 UTC (1,320 hours, 15%)
  - Held-Out Test Period: 2024-11-06 06:00 to 2024-12-30 23:00 UTC (1,290 hours, 15%)
- **Battery Storage Specifications**:
  - Nominal Capacity ($E_{cap}$): 5,000 kWh (4-hour duration)
  - Inverter Power Rating ($P_{max}$): 1,250 kW
  - Charge & Discharge Efficiency: $\eta_c = \eta_d = 0.95$ (Round-trip efficiency $\eta_{rt} = 90.25\%$)
  - State-of-Charge Limits: $[\text{SOC}_{min}, \text{SOC}_{max}] = [0.10, 0.90]$
  - Initial SOC: 0.50
- **Evaluated Systems**:
  - **System A (Grid-Only)**: Deterministic reference system without battery storage.
  - **System B (Surplus-Following Rule-Based Battery)**: Reactive baseline charging only when $P_{solar} > P_{load}$ and discharging when $P_{load} > P_{solar}$.
  - **System C (Forecast-Informed Optimization)**: Receding-horizon MPC using direct LightGBM forecasts and constrained LP.
  - **System D (Perfect-Foresight Oracle)**: Omniscient benchmark receiving ground-truth future realizations across the 24-hour horizon.

---

## 4. Results

### 4.1 Core Benchmark Results (1,290 Held-Out Winter Test Hours)

All measurements are derived directly from the canonical experiment output `reports/experiments_results.json`:

| Performance Metric | System A (Grid-Only) | System B (Rule-Based) | System C (Forecast Opt) | System D (Oracle) |
| :--- | :--- | :--- | :--- | :--- |
| **Total Consumer Demand** | 2,819,622.08 kWh | 2,819,622.08 kWh | 2,819,622.08 kWh | 2,819,622.08 kWh |
| **Total Solar Generation** | 159,401.43 kWh | 159,401.43 kWh | 159,401.43 kWh | 159,401.43 kWh |
| **Total Grid Energy Imported** | 2,660,220.65 kWh | 2,658,320.65 kWh | 2,678,331.80 kWh | 2,682,513.10 kWh |
| **Peak Grid Demand** | 3,279.17 kW | 3,279.17 kW | **3,033.40 kW** | **2,897.50 kW** |
| **Peak Reduction vs System B** | 0.00% (ref) | 0.00% (ref) | **7.49% (-245.77 kW)** | **11.64% (-381.67 kW)** |
| **Total Electricity Cost** | €312,512.86 | €312,194.08 | **€298,741.89** | **€296,611.22** |
| **Cost Saving vs System B** | -€318.79 (-0.10%) | 0.00% (ref) | **-€13,452.18 (-4.31%)** | **-€15,582.85 (-4.99%)** |
| **Cost Saving vs System A** | 0.00% (ref) | -€318.79 (-0.10%) | **-€13,770.97 (-4.41%)** | **-€15,901.64 (-5.09%)** |
| **Battery Energy Throughput** | 0.0 kWh | 1,900.0 kWh | 382,499.00 kWh | 468,615.21 kWh |
| **Renewable Curtailment** | 0.00 kWh | 0.00 kWh | 0.00 kWh | 0.00 kWh |
| **Renewable Utilisation** | 100.00% | 100.00% | 100.00% | 100.00% |
| **Max Balance Error** | $< 10^{-12}\text{ kW}$ | $< 10^{-12}\text{ kW}$ | $< 10^{-12}\text{ kW}$ | $< 10^{-12}\text{ kW}$ |
| **Constraint Violations** | 0 | 0 | 0 | 0 |

### 4.2 Derived Comparative Metrics
- **Grid Energy Difference**:
  - System C vs System B: **+0.752774%** (+20,011.15 kWh)
  - System C vs System A: **+0.680814%** (+18,111.15 kWh)
- **Peak Demand Reduction**: System C vs System B: **7.494770%** (245.766 kW shaved)
- **Cost Saving**: System C vs System B: **4.308917%** (€13,452.18 saved)
- **Oracle Proximity & Benefit Capture**:
  - Oracle Cost Gap: **0.718337%** (System C cost is within 0.72% of the oracle cost).
  - Incremental Opportunity Capture: $\frac{€312,194.08 - €298,741.89}{€312,194.08 - €296,611.22} = \mathbf{86.33\%}$ of available savings opportunity between rule-based and oracle.

### 4.3 Sensitivity Sweeps
- **Renewable Penetration (Experiment D)**:
  - 20% Penetration: Peak reduction = **9.1574%** (Opt Peak = 2,978.88 kW), Cost saving vs RB = **4.0020%** (€12,797.12), Curtailment = 0 kWh.
  - 40% Penetration: Peak reduction = **7.4948%** (Opt Peak = 3,033.40 kW), Cost saving vs RB = **3.9298%** (€12,220.25), Curtailment = 0 kWh.
  - 60% Penetration: Peak reduction = **6.5130%** (Opt Peak = 3,065.59 kW), Cost saving vs RB = **3.7575%** (€11,352.54), Curtailment = **269.132 kWh**, Utilisation = **99.8874%** (-0.1126 pp).
- **Storage Duration (Experiment E)**:
  - 2-Hour Storage ($2,500\text{ kWh}$, $1,250\text{ kW}$): Peak = 3,096.70 kW (5.5645% reduction), Cost = €302,335.70 (3.2063% saving vs RB), Throughput = 257,309.13 kWh.
  - 4-Hour Storage ($5,000\text{ kWh}$, $1,250\text{ kW}$): Peak = 3,033.40 kW (7.4948% reduction), Cost = €298,741.89 (4.3089% saving vs RB), Throughput = 382,499.00 kWh.
- **Injected Forecast Noise (Experiment F)**:
  - 0% Noise: Peak = 3,033.40 kW, Cost = €298,741.89
  - 10% Noise: Peak = 3,228.76 kW, Cost = €299,013.97
  - 20% Noise: Peak = 4,029.98 kW, Cost = €298,942.79
  - 30% Noise: Peak = 4,108.39 kW, Cost = €297,718.47
  - *Observation*: Total electricity cost does not monotonically surge with forecast noise (ranging €297.7k–€299.0k). However, peak grid demand surges above the grid-only reference (3,279.17 kW) at 20% and 30% noise.

---

## 5. Interpretation

1. **Temporal Energy Shifting, Not Energy Reduction**:
   GridFlex AI does not reduce total grid energy consumption in the base test (+0.75% vs System B). The additional 20 MWh imported reflects round-trip battery conversion losses ($\eta_{rt} = 90.25\%$). The system’s economic and operational value derives entirely from temporal flexibility: shifting demand away from expensive peak tariff hours into low-cost off-peak hours and lowering peak import by 245.77 kW.
2. **The Reactive Inaction of Surplus-Following Heuristics**:
   During winter, solar generation (159.4 MWh) is small compared to consumer load (2,819.6 MWh), and local solar power rarely exceeds local demand. Under the surplus-following rule-based controller, the battery discharges its initial energy in the first two hours and remains pinned at minimum SOC (0.10) for 1,288 out of 1,290 hours (99.85% idle time), delivering 0.00% peak demand reduction.
3. **Forecasting Horizon Sensitivity**:
   LightGBM achieves strong error reduction at $h=1$ (-57.05% for load, -21.59% for solar vs persistence), but accuracy degrades across the 24-hour horizon. Forecast perturbations show that dispatch quality is sensitive to forecast errors: sufficiently large noise (20%–30%) can cause the simulated controller to charge during peak periods, worsening peak demand relative to the no-battery baseline.
4. **Penetration and Duration Dynamics**:
   The renewable penetration sweep does not exhibit monotonic improvement in peak shaving (9.16%, 7.49%, and 6.51% at 20%, 40%, and 60% penetration). At 60% penetration, renewable surplus produces measurable curtailment (269.13 kWh), reflecting storage saturation under winter dispatch profiles. A 4-hour battery duration delivers greater peak shaving (+1.93 percentage points) and higher cost savings (+1.10 percentage points) than a 2-hour battery under identical power ratings.

---

## 6. Limitations

To maintain scientific integrity, the findings must be interpreted within the constraints of the study:
1. **Winter-Dominated Quantitative Test Set**: The core evaluation spans November 6 to December 30, 2024, characterized by low solar output. These results cannot be generalized to summer or full-annual solar regimes without further operational evaluation.
2. **No Demonstration of Base-Case Renewable Utilisation Gain**: In the base 40% penetration winter test, both the grid-only system and all battery systems have 100.0% renewable utilisation and zero curtailment. The prototype does not demonstrate increased renewable utilisation in this base regime.
3. **Price-Taker Assumption**: The model assumes the battery acts as a price-taker on the EPEX day-ahead market without price elasticity or market-clearing impact.
4. **Simplified Physical & Degradation Dynamics**: Battery aging is modeled via a linear throughput penalty ($\delta$) rather than electrochemical degradation (SEI layer growth, temperature effects, C-rate wear).
5. **Single-Node Conservation**: The evaluation models a single lumped substation node (`OS Leiden Noord`) and does not capture multi-bus AC power flow, voltage regulation, reactive power ($Q$), or line thermal impedance constraints.
6. **Simulated Environment**: Battery dispatch was evaluated in a simulated rolling-horizon loop; real-world grid safety and distribution protection constraints were not modeled.

---

## 7. Reproduction

The complete pipeline is deterministic and reproducible via standard commands:

### 1. Environment Setup
```bash
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Data Ingestion & Preprocessing
```bash
python -m src.data.download
python -m src.data.preprocess
```

### 3. Feature Engineering & Multi-Horizon Model Training
```bash
python -m src.features.leakage_check
python -m src.forecasting.train
```

### 4. Execute Comparative Experiments & Sensitivity Sweeps
```bash
python -m experiments.run_experiments
```

### 5. Run Error Diagnostics & Figure Regeneration
```bash
python -m src.evaluation.error_analysis
python -m experiments.run_experiments --figures-only
```

### 6. Verify Artifacts, Quality Checks & Automated Tests
```bash
# Programmatic artifact consistency validation
python -m src.evaluation.validate_artifacts

# Full automated test suite (30 passed)
python -m pytest tests/ -v

# Static analysis and linting
python -m ruff check src/ tests/ configs/ experiments/ app.py
```

### 7. Interactive Demonstration Dashboard
```bash
streamlit run app.py
```

---

## 8. Future Work

1. **Uncertainty-Aware & Robust Model Predictive Control**: Implementing chance-constrained or distributionally robust optimization (DRO) to guarantee peak-demand upper bounds under forecast error distributions.
2. **Full-Year & Multi-Season Operational Evaluation**: Extending rolling-horizon optimization across complete spring, summer, and autumn regimes to evaluate seasonal flexibility trade-offs and curtailment mitigation.
3. **Distribution AC Optimal Power Flow (OPF)**: Incorporating second-order cone programming (SOCP) relaxations to enforce voltage limits and line thermal constraints across multi-bus distribution networks.
4. **Physics-Informed Battery Degradation**: Integrating semi-empirical battery health models accounting for depth of discharge (DoD), temperature, and C-rate into the objective formulation.
5. **Multi-Market Revenue Stacking**: Co-optimizing day-ahead price arbitrage with intraday balancing reserves and frequency containment reserves (FCR).

---

## Publication Figures

All 11 research figures are saved at 200–300 DPI in `figures/`:
- `fig01_demand_vs_solar.png`: Full-year daily power trajectories and high-solar summer week.
- `fig02_daily_profiles.png`: 24-hour diurnal profiles of load, solar, net load, and EPEX spot prices.
- `fig03_price_distribution.png`: EPEX NL electricity price histogram and price duration curve.
- `fig04_baseline_comparison.png`: Time-series traces of grid import and battery SOC under Grid-Only vs Rule-Based control.
- `fig05_forecast_performance.png`: Multi-horizon LightGBM MAE curves and test trajectory samples.
- `fig06_systems_comparison.png`: 4-way comparative performance across Grid Energy, Peak Demand, Cost, and Curtailment.
- `fig07_penetration_sensitivity.png`: Peak Grid Demand and Total Electricity Cost across 20%, 40%, 60% solar penetration.
- `fig08_duration_sensitivity.png`: 2-hour vs 4-hour battery storage comparison for Peak Demand and Cost.
- `fig09_forecast_noise_sensitivity.png`: Peak Grid Demand and Total Cost curves under 0%, 10%, 20%, 30% injected forecast noise.
- `fig10_oracle_gap.png`: Economic, Peak Demand, and Grid Energy gap analysis between Forecast-Informed MPC and Oracle.
- `fig11_error_analysis.png`: 4-panel diagnostic deep dive (residual distributions, diurnal error vs SOC, SOC saturation histograms, high-stress event trace).

---

## Citation & IRENA Track

**GridFlex AI Research Initiative**  
Prepared for submission to the **IRENA Youth Forum 2027**  
*Track: Innovation in Renewable Energy Integration, Grid Flexibility & Clean Energy Transition*  
Repository: [https://github.com/gridflex-ai/gridflex](https://github.com/gridflex-ai/gridflex)
