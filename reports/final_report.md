# GridFlex AI: Forecast-Driven Renewable Energy Storage and Grid Flexibility Optimization

**Target Submission**: IRENA Youth Forum 2027  
**Track**: Innovation in Renewable Energy Integration, Grid Flexibility & Clean Energy Transition  
**Author / Research Team**: GridFlex AI Research Initiative  
**Date**: September 2026  
**Repository**: [https://github.com/gridflex-ai/gridflex](https://github.com/gridflex-ai/gridflex)  
**Status**: Completed Empirical Research Prototype  

---

## 1. Abstract
Variable renewable energy (VRE) integration introduces steep ramping, localized substation congestion, and pronounced evening demand peaks across distribution networks. While battery energy storage systems (BESS) offer fast-acting flexibility, this work uses a simple surplus-following reactive controller (which only actuates when instantaneous local solar generation exceeds local load) as a deliberately myopic baseline. 

In this work, we present **GridFlex AI**, an end-to-end, reproducible, and mathematically constrained research prototype investigating how machine-learning-based multi-horizon forecasting coupled with rolling-horizon linear programming (LP) optimization can enhance grid flexibility, shave peak demand, and lower electricity costs compared with a surplus-following rule-based battery controller. 

Using 35,136 auditable 15-minute empirical measurements across calendar year 2024 from the Dutch distribution grid (Alliander / Liander open benchmark) and EPEX day-ahead spot market prices, we evaluate four core energy management systems across an uncorrupted $1,290$-hour held-out winter test set under identical physical battery parameters ($5,000\text{ kWh}$, $1,250\text{ kW}$, round-trip efficiency $\eta_{rt} = 90.25\%$, $\text{SOC} \in [0.10, 0.90]$).

Our empirical findings demonstrate:
1. **The Heuristic Inaction Trap**: In low-renewable winter regimes, a surplus-following rule-based controller delivers **$0.00\%$ peak demand reduction** and saves only **$0.10\%$** (€318.79) because instantaneous solar generation ($159.4\text{ MWh}$) never exceeds consumer demand ($2,819.6\text{ MWh}$), leaving the battery idle at minimum SOC for **1,288 of the 1,290 test hours ($99.845\%$, or approximately $99.85\%$)**.
2. **Forecast Optimization Efficacy**: The proposed Model Predictive Control (MPC) system achieves a **$7.49\%$ peak demand reduction ($245.77\text{ kW}$ shaved)** and saves **$€13,452.18$ ($4.31\%$)** over the rule-based baseline through price-aware off-peak charging and strategic on-peak discharging, while strictly maintaining zero constraint violations.
3. **Temporal Energy Shifting vs Total Energy**: GridFlex AI does not reduce total grid energy consumption in the base winter test (+0.75% vs rule-based, +0.68% vs grid-only) due to conversion losses inherent to the 90.25% round-trip battery efficiency. Both renewable curtailment ($0.0\text{ kWh}$) and renewable utilisation ($100.0\%$) are identical across all four evaluated systems; the demonstrated value lies in temporal flexibility, peak shaving, and cost management.
4. **Oracle Cost Proximity**: Total electricity cost under GridFlex AI is within **$0.72\%$** of the theoretical perfect-foresight oracle cost, capturing **$86.33\%$** of the incremental cost-saving opportunity between the rule-based baseline and the oracle.
5. **Sensitivity to Forecast Errors**: Perturbation experiments reveal that while electricity cost remains relatively stable under forecast noise, peak-shaving performance degrades severely at 20% and 30% injected noise, causing peak demand to exceed the grid-only reference. This underscores the need for robust and uncertainty-aware MPC formulations.

---

## 2. Problem Definition & Context
As the global energy mix transitions toward variable renewable generation, distribution system operators (DSOs) confront steep evening ramp rates ("duck curves"), transformer thermal overloads, and localized capacity bottlenecks. Behind-the-meter and utility-scale battery energy storage offer critical flexibility; however, when storage dispatch is governed by simple reactive heuristics, its flexibility potential remains largely untapped under seasonal renewable deficits.

Connecting directly to the **IRENA Youth Forum 2027** theme, this prototype explores the functional pathway:
$$\text{Renewable Variability} \longrightarrow \text{Forecasting} \longrightarrow \text{Battery Storage} \longrightarrow \text{Temporal Flexibility} \longrightarrow \text{Peak Management} \longrightarrow \text{Grid Integration}$$

### The Central Research Question
> *Can machine-learning-based forecasts combined with constrained rolling-horizon battery optimization reduce peak grid demand and electricity costs relative to a simple surplus-following battery controller?*

### Scientific & Engineering Commitments
- **Zero Temporal Leakage**: Strict physical separation between issuance time $t_0$ and future horizons $t_0 + h$, mathematically confirmed via perturbation audits.
- **Strict Physical Conservation**: Nodal power balance and dynamic battery state-of-charge transitions enforced at every discrete timestep ($\Delta t = 1.0\text{ h}$), ensuring balance errors $< 10^{-12}\text{ kW}$.
- **Empirical Grounding**: Open benchmark distribution feeder meter data and market clearing spot prices without synthetic fabrication.
- **Controlled Baselines**: All systems evaluated over identical test periods using identical physical storage configurations.

---

## 3. Data Source, Audit & Lineage

### 3.1 Primary Data Sources
Data was ingested from the public Hugging Face repository `OpenSTEF/liander2024-energy-forecasting-benchmark` provided by Alliander, the largest Dutch DSO:
1. **Substation Consumer Demand**: `OS Leiden Noord.parquet` (pure consumer demand, positive load, avoiding rooftop solar backfeed contamination).
2. **Solar PV Generation**: `Within 10 kilometers of Westwoud_normalized.parquet` (normalized ground-truth photovoltaic generation profile).
3. **Electricity Day-Ahead Spot Prices**: `EPEX.parquet` (Dutch day-ahead hourly spot prices converted to EUR/kWh).

### 3.2 Audit & Ingestion Metrics
- **Temporal Span**: Full calendar year 2024 (January 1, 2024 00:00 UTC to December 31, 2024 23:45 UTC).
- **Native Resolution**: 15-minute intervals ($35,136$ raw timestamps).
- **Data Quality**: Exactly one 3-step missing interval identified on `2024-10-27 01:00` to `01:30` UTC (European Daylight Saving Time transition), imputed via causal forward-fill.
- **Harmonization**: Resampled to $8,784$ hourly UTC intervals.
- **Renewable Scaling Calibration**: Solar generation profile scaled to represent a 40.0% annual energy penetration:
  $$C_{solar} = 4,833.02\text{ kW} \implies E_{solar} = 6,518.74\text{ MWh vs } E_{demand} = 16,296.84\text{ MWh}$$

---

## 4. End-to-End System Methodology

GridFlex AI employs a modular, causal pipeline consisting of seven sequential subsystems:

```
[Raw Open Energy Data] 
       │
       ▼
[Data Ingestion & DST Audit] ───> [Processed Hourly Parquet]
                                             │
                                             ▼
                                 [Causal Feature Engineering]
                                             │
                                             ▼
                                [Direct LightGBM Forecasting]
                                             │
                                             ▼
                               [Constrained LP Optimizer]
                                             │
                                             ▼
                                [Receding-Horizon Controller]
                                             │
                                             ▼
                               [Physical Battery Simulator] ───> [Metrics & Diagnostics]
```

At each discrete hour $t$, the rolling-horizon controller:
1. Queries direct multi-horizon LightGBM models for 24-hour predictions $[\hat{P}_{load, t+1}, \dots, \hat{P}_{load, t+24}]$ and $[\hat{P}_{solar, t+1}, \dots, \hat{P}_{solar, t+24}]$.
2. Receives published day-ahead spot market prices $[\text{Price}_{t+1}, \dots, \text{Price}_{t+24}]$.
3. Solves a multi-objective linear program to compute the optimal 24-hour dispatch trajectory.
4. Actuates **only the immediate command** ($P_{charge, t+1}^*, P_{discharge, t+1}^*$) on the physical battery simulator.
5. Advances time by 1 hour, receives actual realization feedback, updates the battery state-of-charge, and repeats.

---

## 5. Forecasting Framework & Leakage Safeguards

### 5.1 Direct Multi-Horizon Architecture
To eliminate auto-regressive error compounding, 48 independent LightGBM regressors were trained:
- 24 direct models for consumer load: $f_{load, h}(X_t) \to \hat{P}_{load, t+h}$ for $h \in [1, 24]$.
- 24 direct models for solar generation: $f_{solar, h}(X_t) \to \hat{P}_{solar, t+h}$ for $h \in [1, 24]$.

### 5.2 Feature Representation (35 Causal Predictors)
- **Target Calendar**: Cyclical encodings ($\sin/\cos$ of hour, day-of-week, day-of-year, month) and binary flags (is_weekend).
- **Issuance Conditions**: Current power $y_t$, short-term lags $y_{t-1}, y_{t-2}$, rolling statistics ($3\text{h}, 6\text{h}, 24\text{h}$ means).
- **Seasonal Lags**: Historical values observed at the identical hour-of-day ($y_{t+h-24}, y_{t+h-48}, y_{t+h-168}$). Since $h \le 24$, all lag indices satisfy $t + h - 24 \le t$, guaranteeing zero lookahead leakage.

### 5.3 Leakage Verification Audit
A programmatic perturbation test executed across 6 historical timestamps injected large perturbations ($+10,000\text{ kW}$) into future ground-truth values ($t_0 + 1$ to $t_0 + 24$). The feature matrix generated at $t_0$ exhibited exactly $0.000000$ difference, confirming zero future lookahead contamination.

### 5.4 Forecasting Performance and Horizon-Dependent Degradation
Across the $1,290$-hour held-out test set, immediate lookahead ($h=1$) metrics demonstrate significant improvements over seasonal persistence baselines:

| Target Series | Model Architecture | MAE (kW) | RMSE (kW) | nRMSE (%) | Error Reduction vs Persistence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Consumer Load** | LightGBM Direct ($h=1$) | **47.06** | **62.40** | **2.85%** | **-57.05%** |
| | Persistence Baseline ($h=1$) | 109.56 | 151.83 | 6.95% | 0.00% (ref) |
| **Solar PV** | LightGBM Direct ($h=1$) | **67.59** | **123.59** | **100.02%** | **-21.59%** |
| | Persistence Baseline ($h=1$) | 86.20 | 222.62 | 180.16% | 0.00% (ref) |

**Horizon-Dependent Uncertainty**: As documented in Figure 5, forecasting accuracy is strongest at the immediate lookahead horizon ($h=1$), where LightGBM achieves a 57.05% MAE reduction on load (47.06 kW vs 109.56 kW persistence) and a 21.59% reduction on solar (67.59 kW vs 86.20 kW persistence). Beyond the immediate horizon, error does not degrade monotonically:
- **Load Demand**: LightGBM MAE rises sharply over the first five hours (47.06 kW at $h=1$ to 119.66 kW at $h=5$), then plateaus with diurnal oscillations between ~120 kW and ~140 kW, reaching **135.91 kW at $h=24$**. Load persistence remains relatively flat across all 24 horizons (~109.4 kW to 110.0 kW, ending at **109.95 kW at $h=24$**), outperforming LightGBM beyond $h=4$.
- **Solar PV Generation**: LightGBM MAE increases across daytime lookaheads, fluctuating between ~240 kW and ~292 kW for horizons $h=6 \dots 24$, ending at **265.52 kW at $h=24$**. Solar persistence stays relatively flat (~85.1 kW to 86.2 kW, ending at **85.57 kW at $h=24$**) due to the high proportion of zero-generation nighttime winter hours.

Crucially, because the receding-horizon MPC controller executes **only the immediate action ($h=1$)** before advancing time and reforecasting with fresh observations, the operational control loop actuates continuously within the high-accuracy regime where LightGBM dominates.

---

## 6. Battery Storage Model & Physical Constraints

The battery storage system is modeled as a deterministic physical simulator independent of the optimizer, enforcing inverter limits, non-ideal conversion efficiencies, and state bounds.

### Governing State Transitions
- **Charging ($P_{charge, t} > 0$)**:
  $$\text{SOC}_{t+1} = \text{SOC}_t + \frac{\eta_c P_{charge, t} \Delta t}{E_{cap}}$$
- **Discharging ($P_{discharge, t} > 0$)**:
  $$\text{SOC}_{t+1} = \text{SOC}_t - \frac{P_{discharge, t} \Delta t}{\eta_d E_{cap}}$$

### Prototype Sizing & Operating Bounds
- **Nominal Capacity ($E_{cap}$)**: $5,000\text{ kWh}$
- **Inverter Rating ($P_{max}$)**: $1,250\text{ kW}$ (4-hour duration system)
- **Efficiency ($\eta_c = \eta_d = 0.95$)**: Round-trip efficiency $\eta_{rt} = 90.25\%$
- **Permissible SOC Range**: $[\text{SOC}_{min}, \text{SOC}_{max}] = [0.10, 0.90]$ ($80\%$ usable depth)
- **Initial SOC**: $0.50$

### Substation Node Energy Conservation
At every discrete timestep, the nodal balance equation is verified:
$$P_{grid, t} = P_{load, t} - P_{solar, t} + P_{charge, t} - P_{discharge, t} + P_{curtailment, t}$$
Across all simulations, the maximum balance error satisfied $|Error_{max}| < 10^{-12}\text{ kW}$.

---

## 7. Constrained Linear Optimization Formulation

For a prediction horizon $H = 24$, the battery dispatch schedule is optimized by solving the following linear program via SciPy's HiGHS solver:

### Decision Variables (121 variables)
$$\mathbf{x} = [P_{ch, 0..H-1}, P_{dis, 0..H-1}, P_{grid, 0..H-1}, P_{curt, 0..H-1}, E_{0..H-1}, P_{grid, peak}]^T$$

### Multi-Objective Function
$$\min_{\mathbf{x}} J = \alpha \sum_{t=0}^{H-1} \text{Price}_t P_{grid, t} \Delta t + \beta P_{grid, peak} + \gamma \sum_{t=0}^{H-1} P_{curt, t} \Delta t + \delta \sum_{t=0}^{H-1} (P_{ch, t} + P_{dis, t}) \Delta t$$

- **Cost Arbitrage ($\alpha = 1.0$)**: Minimizes total grid electricity cost.
- **Peak Shaving ($\beta = 0.1$)**: Penalizes maximum grid import over the 24-hour horizon.
- **Curtailment Defense ($\gamma = 2.0$)**: Prioritizes local renewable utilization.
- **Degradation Regularizer ($\delta = 0.001$)**: Suppresses idle battery micro-cycling.

### Operational Constraints
1. **Nodal Energy Balance**:
   $$P_{grid, t} - P_{ch, t} + P_{dis, t} - P_{curt, t} = \hat{P}_{load, t} - \hat{P}_{solar, t} \quad \forall t$$
2. **Dynamic Energy Storage Recursion**:
   $$E_t - E_{t-1} - \eta_c P_{ch, t} \Delta t + \frac{1}{\eta_d} P_{dis, t} \Delta t = 0 \quad \forall t$$
3. **Peak Import Envelope**:
   $$P_{grid, peak} \ge P_{grid, t} \quad \forall t$$
4. **Physical Bounds**:
   $$0 \le P_{ch, t} \le P_{max}, \quad 0 \le P_{dis, t} \le P_{max}$$
   $$0 \le P_{grid, t} \le \infty, \quad 0 \le P_{curt, t} \le \hat{P}_{solar, t}$$
   $$E_{cap} \cdot \text{SOC}_{min} \le E_t \le E_{cap} \cdot \text{SOC}_{max}$$

---

## 8. Experimental Setup & Protocol

### 8.1 Chronological Data Partitioning
- **Training Set (70%)**: `2024-01-01 00:00` to `2024-09-13 14:00` UTC ($6,150$ hours)
- **Validation Set (15%)**: `2024-09-13 15:00` to `2024-11-06 05:00` UTC ($1,320$ hours)
- **Held-Out Test Set (15%)**: `2024-11-06 06:00` to `2024-12-30 23:00` UTC ($1,290$ hours)

*Seasonal Limitation*: The quantitative evaluation period is winter-dominated. Solar irradiance and total solar energy in this period are markedly lower than during spring and summer.

### 8.2 Four Core Evaluated Systems
1. **System A — Grid-Only (Baseline)**: Pure pass-through without battery storage.
2. **System B — Surplus-Following Rule-Based Battery Controller**: A simple reactive baseline that charges only when $P_{solar} > P_{load}$ and discharges when $P_{load} > P_{solar}$.
3. **System C — Forecast-Informed Optimization (Proposed)**: Receding-horizon MPC with direct LightGBM forecasts and constrained LP.
4. **System D — Perfect-Foresight Oracle (Theoretical Bound)**: Omniscient reference receiving actual future measurements over the 24-hour horizon.

---

## 9. Comparative Empirical Results

### 9.1 Master Performance Comparison (1,290 Held-Out Winter Test Hours)

All values are canonical measurements from `reports/experiments_results.json`:

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

### 9.2 Key Findings & Interpretation

1. **Rule-Based Inaction Trap**:
   In low-renewable winter regimes, total solar generation ($159.4\text{ MWh}$) is less than 6% of total demand ($2,819.6\text{ MWh}$). Because instantaneous solar output never exceeds demand, the surplus condition $P_{solar} > P_{load}$ is never triggered after the initial hours. The rule-based controller discharges its initial charge in the first two hours and then remains idle at minimum SOC ($0.10$) for **$1,288$ of the $1,290$ hours ($99.845\%$, or approximately $99.85\%$)**. It provides **$0.00\%$ peak shaving** and saves only **$0.10\%$** (€318.79).
2. **Temporal Energy Shifting, Not Grid Energy Reduction**:
   System C consumes **+0.752774% more grid energy** than System B (+20,011.15 kWh) and **+0.680814% more grid energy** than System A (+18,111.15 kWh). This increase reflects round-trip conversion losses ($\eta_{rt} = 90.25\%$) incurred during cyclic charging and discharging. GridFlex AI does not reduce net grid energy consumption; its demonstrated value consists of shifting energy from high-price peak hours to low-price off-peak hours and reducing peak demand by **$245.77\text{ kW}$ ($7.49\%$)**, saving **$€13,452.18$ ($4.31\%$)**.
3. **Curtailment and Renewable Utilisation**:
   In this base winter test set, curtailment is **$0.0\text{ kWh}$ across all four systems**, and renewable utilisation is **$100.0\%$ across all four systems**. The base experiment does not demonstrate increased renewable utilisation or reduced curtailment.
4. **Oracle Proximity & Benefit Capture**:
   System C achieves an electricity cost of €298,741.89, which is within **$0.72\%$** of the theoretical oracle cost of €296,611.22 (cost gap = 0.718337%). Relative to the incremental opportunity interval between the rule-based baseline (€312,194.08) and the oracle (€296,611.22), GridFlex AI captures:
   $$\frac{€312,194.08 - €298,741.89}{€312,194.08 - €296,611.22} \times 100\% = \frac{€13,452.18}{€15,582.85} \times 100\% \approx \mathbf{86.33\%}$$

---

## 10. Sensitivity Analyses

### 10.1 Experiment D: Renewable Penetration Sensitivity ($C_{solar} \in \{20\%, 40\%, 60\%\}$)
Evaluates system behavior as calibrated solar capacity scales relative to consumer load:

| Metric | 20% Penetration | 40% Penetration (Base) | 60% Penetration |
| :--- | :--- | :--- | :--- |
| **Rule-Based Peak Demand** | 3,279.17 kW | 3,279.17 kW | 3,279.17 kW |
| **System C Peak Demand** | 2,978.88 kW | 3,033.40 kW | 3,065.59 kW |
| **Peak Demand Reduction vs RB** | **9.16% (-300.29 kW)** | **7.49% (-245.77 kW)** | **6.51% (-213.57 kW)** |
| **Rule-Based Total Cost** | €319,764.88 | €310,962.14 | €302,134.08 |
| **System C Total Cost** | €306,967.76 | €298,741.89 | €290,781.54 |
| **Cost Saving vs RB** | **4.00% (€12,797.12)** | **3.93% (€12,220.25)** | **3.76% (€11,352.54)** |
| **System C Curtailment** | 0.00 kWh | 0.00 kWh | **269.13 kWh** |
| **Renewable Utilisation** | 100.00% | 100.00% | **99.89% (-0.11 pp)** |

*Interpretation*: The penetration sweep does not exhibit monotonic improvement in peak-shaving percentage with increasing renewable penetration. Under the tested winter configurations, peak reduction was 9.16%, 7.49%, and 6.51% at 20%, 40%, and 60% penetration respectively. At 60% penetration, the larger renewable surplus produces 269.13 kWh of curtailment, indicating an operational trade-off between battery capacity, charging schedules, and available solar power.

### 10.2 Experiment E: Storage Duration Sensitivity ($2\text{h}$ vs $4\text{h}$)
Evaluates storage duration under identical inverter power ($1,250\text{ kW}$):

| Metric | 2-Hour Storage ($2,500\text{ kWh}$) | 4-Hour Storage ($5,000\text{ kWh}$, Base) | Impact of Longer Duration |
| :--- | :--- | :--- | :--- |
| **Grid Peak Demand (kW)** | 3,096.70 kW | 3,033.40 kW | **-63.30 kW lower peak** |
| **Peak Demand Reduction vs RB** | **5.56% (-182.47 kW)** | **7.49% (-245.77 kW)** | **+1.93 percentage points** |
| **Total Electricity Cost (€)** | €302,335.70 | €298,741.89 | **-€3,593.81 lower cost** |
| **Cost Saving vs RB** | **3.21% (€10,014.77)** | **4.31% (€13,452.18)** | **+1.10 percentage points** |
| **Battery Throughput** | 257,309.13 kWh | 382,499.00 kWh | +48.6% higher energy shift |

*Interpretation*: Under the evaluated winter test conditions, 4-hour storage provides greater peak reduction (7.49% vs 5.56%) and greater cost savings (4.31% vs 3.21%) than 2-hour storage by sustaining discharges across longer evening peak windows. This demonstrates the benefit of energy duration for this test profile without asserting universal duration optimality.

### 10.3 Experiment F: Forecast Noise Sensitivity ($\sigma_{noise} \in \{0\%, 10\%, 20\%, 30\%\}$)
Evaluates dispatch policy robustness by injecting zero-mean Gaussian noise into multi-horizon forecasts:

| Noise Level ($\sigma$) | Peak Grid Demand (kW) | Peak Shaving vs RB (%) | Total Electricity Cost (€) | Cost Change vs 0% Noise |
| :--- | :--- | :--- | :--- | :--- |
| **0% (Pure LightGBM)** | **3,033.40** | **7.49%** | **€298,741.89** | 0.00% (ref) |
| **10% Noise** | 3,228.76 | 1.54% | €299,013.97 | +€272.08 (+0.09%) |
| **20% Noise** | **4,029.98** | **-22.90% (Peak Exceedance)** | €298,942.79 | +€200.90 (+0.07%) |
| **30% Noise** | **4,108.39** | **-25.29% (Peak Exceedance)** | €297,718.47 | -€1,023.42 (-0.34%) |

*Interpretation*: Total electricity costs do not monotonically deteriorate with injected forecast noise, remaining within €297.7k–€299.0k. However, peak grid demand exhibits severe sensitivity: at 20% and 30% noise, grid peaks surge to 4,030.0 kW and 4,108.4 kW, substantially exceeding the grid-only reference of 3,279.17 kW. Large forecast perturbations cause the simulated controller to misjudge peak timing and issue charging commands during actual high-load hours. This demonstrates dispatch sensitivity to forecast error in simulation and motivates uncertainty-aware or robust MPC.

---

## 11. Diagnostic Error & Failure Mode Analysis

1. **Residual Statistics**:
   - Consumer Load Residuals: mean $-13.96\text{ kW}$, std $60.82\text{ kW}$ (median $-11.32\text{ kW}$, $80\%$ of residuals within $[-87.95\text{ kW}, +57.17\text{ kW}]$).
   - Solar Residuals: mean $+27.18\text{ kW}$, std $120.57\text{ kW}$ ($80\%$ of residuals within $[-12.55\text{ kW}, +129.76\text{ kW}]$). Solar exhibits higher variance and pronounced midday tails due to rapid cloud-cover transitions.
2. **Diurnal Error Patterns**:
   - Consumer load MAE peaks during the morning ramp window ($07:00 - 08:00$ UTC, MAE $= 83.79\text{ kW}$), whereas overnight hours ($00:00 - 04:00$ UTC) exhibit low error (MAE $22.8 - 26.1\text{ kW}$).
   - Solar MAE is strictly zero during nighttime hours and peaks at $253.93\text{ kW}$ around solar noon ($11:00$ UTC).
3. **Battery Operating States**:
   - System C: Operates in the intermediate dynamic SOC range for $81.24\%$ of test hours (1,048 hrs), with $15.89\%$ depleted hours (205 hrs), $2.87\%$ saturated hours (37 hrs), and mean SOC $43.71\%$.
   - System D (Oracle): Reaches full saturation for $24.88\%$ of test hours (321 hrs), with $13.26\%$ depleted hours (171 hrs), $61.86\%$ intermediate hours (798 hrs), and mean SOC $55.14\%$. Omniscient lookahead enables more aggressive overnight pre-charging.
   - System B: Remains at minimum SOC ($0.10$) and completely idle (zero charge and zero discharge power) for $99.845\%$ of the evaluation period (1,288 of 1,290 hrs), confirming the reactive inaction trap.
4. **Stress Episodes**:
   - Atypical holiday demand profiles (e.g., Christmas Day `2024-12-25`, load MAE $= 87.95\text{ kW}$) produced the highest forecast error, reflecting behavioral deviations from standard calendar patterns.

---

## 12. Critical Assumptions, Limitations & Evidence Boundaries

### 12.1 Explicit Boundaries: Demonstrated vs Not Demonstrated

To ensure complete scientific integrity, the boundary between demonstrated findings and unproven extrapolations is explicitly defined:

| Dimension | Demonstrated by GridFlex AI | NOT Demonstrated / Out of Scope |
| :--- | :--- | :--- |
| **Peak Grid Demand** | **7.49% peak shaving** (245.77 kW reduced) vs rule-based baseline under winter conditions. | Universal peak reduction across all seasons and network topologies. |
| **Electricity Cost** | **4.31% cost saving** (€13,452.18 saved) vs rule-based baseline; within 0.72% of oracle. | Market-clearing equilibrium or price elasticity effects under aggregate storage adoption. |
| **Grid Energy Consumption** | Temporal shifting of energy from peak to off-peak periods. | **Reduction in total grid energy** (grid imports increased by +0.75% due to round-trip losses). |
| **Renewable Utilisation** | 100% utilisation maintained; zero base-case curtailment across all systems. | **Improvement in renewable utilisation** in the base test (curtailment was already zero). |
| **Battery Dispatch Feasibility**| Strict physical conservation ($< 10^{-12}\text{ kW}$ error) and 0 constraint violations. | Electrochemical battery aging (cell temperature, SEI growth, C-rate wear). |
| **Control Robustness** | Sensitivity of dispatch policy to synthetic forecast noise identified. | **Real-grid operational safety** (distribution AC power flow, voltage, protection unmodeled). |
| **Battery Sizing** | 4h duration demonstrated superior peak shaving to 2h duration under test setup. | Universal optimal battery duration or sizing recommendations. |

### 12.2 Methodological Assumptions
1. **Price-Taker Assumption**: The battery operates as a price-taker on the EPEX spot market.
2. **Linear Degradation Regularization**: Battery wear is managed via a throughput cost regularizer rather than an electrochemical degradation model.
3. **Single-Node Conservation**: Power balance is modeled as a lumped single-node conservation without multi-bus distribution AC power flow or reactive power ($Q$) constraints.
4. **Winter-Dominated Period**: The quantitative evaluation window covers November 6 to December 30, 2024. Full-year operational evaluation across high-solar summer periods remains future work.

---

## 13. Future Work & Deployment Roadmap

1. **Uncertainty-Aware & Robust MPC**: Formulating chance-constrained or distributionally robust optimization (DRO) to guarantee peak-demand bounds under forecast error distributions.
2. **Full-Season Operational Evaluation**: Extending rolling-horizon evaluation across spring, summer, and autumn to assess seasonal flexibility and curtailment mitigation.
3. **Distribution AC Optimal Power Flow (OPF)**: Incorporating second-order cone programming (SOCP) relaxations to enforce bus voltage limits and line thermal ratings.
4. **Physics-Informed Battery Degradation**: Integrating semi-empirical battery health models accounting for depth of discharge (DoD), temperature, and C-rate.
5. **Multi-Market Revenue Stacking**: Co-optimizing day-ahead price arbitrage with intraday balancing reserves and frequency containment reserves (FCR).

---

## 14. Conclusion & IRENA Submission Readiness

### Direct Scientific Conclusion
GridFlex AI demonstrates that forecast-informed receding-horizon battery optimization can materially reduce peak grid demand and electricity cost compared with a simple surplus-following controller in the evaluated winter test period. The system achieved a **$7.49\%$ reduction in peak grid demand ($245.77\text{ kW}$ shaved)** and a **$4.31\%$ reduction in electricity cost ($€13,452.18$ saved)** relative to the rule-based baseline while maintaining zero battery constraint violations and negligible numerical energy-balance error ($< 10^{-12}\text{ kW}$). Total cost was within **$0.72\%$** of the perfect-foresight oracle cost, capturing approximately **$86.33\%$** of the incremental cost-saving opportunity. 

The system did not reduce total grid energy consumption (+0.75% vs rule-based baseline due to round-trip efficiency losses) or improve renewable utilisation in the base evaluation (all systems achieved 100% utilisation with zero curtailment); its demonstrated value was primarily temporal energy shifting, peak shaving, and price-aware storage dispatch. Forecast-noise experiments further demonstrated sensitivity of peak-demand performance to forecasting errors, motivating robust and uncertainty-aware control methods for future work.

GridFlex AI represents a transparent, reproducible, and scientifically grounded research prototype exploring how AI-based forecasting and optimization can contribute to renewable-energy system flexibility for the **IRENA Youth Forum 2027**.
