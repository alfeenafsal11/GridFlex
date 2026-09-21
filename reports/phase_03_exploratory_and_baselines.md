# Phase 3 Report — Exploratory Analysis and Deterministic Baselines

## 1. Objective
Perform an in-depth exploratory data analysis of the hourly 2024 system conditions, characterize demand, solar production, and price volatility, and evaluate two reference benchmarks:
1. **Baseline A (Grid-Only)**: No battery storage; all residual deficit is imported directly from the grid and all surplus renewable energy is curtailed.
2. **Baseline B (Rule-Based Battery)**: Greedy heuristic controller charging during renewable surplus ($P_{solar} > P_{load}$) and discharging during deficit ($P_{solar} < P_{load}$) respecting power limits and state-of-charge boundaries.

## 2. Exploratory Findings & System Dynamics

### A. Diurnal Patterns
- **Electrical Demand**: Characterized by a dual-peak profile typical of European distribution feeders. Morning peak occurs around 08:00–10:00 UTC (~2,100 kW), followed by a secondary evening peak between 18:00–20:00 UTC (~2,400 kW). Base nocturnal demand hovers around 1,200 kW.
- **Solar Generation**: Follows a strict diurnal bell curve concentrated between 06:00 and 18:00 UTC, peaking at midday (11:00–13:00 UTC) with average summer midday generation exceeding 2,500 kW.
- **EPEX Market Price**: Displays distinct morning (07:00–09:00 UTC) and evening (18:00–20:00 UTC) price spikes corresponding to system-wide peak consumption, while frequently depressing to near-zero or negative values during sunny summer afternoons.

### B. Seasonal Surplus & Deficit
- **Winter (Nov–Feb)**: Severe renewable deficit. Total solar output is minimal (~15% of annual total). Demand is at its highest, resulting in near-continuous grid import and virtually zero battery charging opportunities.
- **Summer (May–Aug)**: Substantial renewable surplus. Midday generation routinely exceeds feeder load by up to $3,673.91\text{ kW}$, resulting in heavy curtailment unless stored.

## 3. Baseline Comparative Performance (Full Year 2024, 8,784 Hours)

| Metric | Grid-Only (Baseline A) | Rule-Based Battery (Baseline B) | Delta / Change | Relative Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Total Demand** | 16,296,840 kWh | 16,296,840 kWh | 0 kWh | - |
| **Total Solar Generation** | 6,518,736 kWh | 6,518,736 kWh | 0 kWh | - |
| **Total Grid Import** | 11,790,780 kWh | 11,108,190 kWh | -682,590 kWh | **-5.79%** |
| **Peak Grid Demand** | 3,618.26 kW | 3,618.26 kW | 0.00 kW | **0.00%** (Unchanged) |
| **Renewable Curtailment** | 2,012,673 kWh | 1,258,453 kWh | -754,220 kWh | **-37.47%** |
| **Renewable Utilisation** | 69.12% | 80.69% | +11.57 pp | **+16.74%** |
| **Total Electricity Cost** | €1,096,594 | €1,022,338 | -€74,256 | **-6.77%** |
| **Battery Throughput** | 0.0 kWh | 1,436,803 kWh | +1,436,803 kWh | - |
| **Average Battery SOC** | N/A | 22.06% | - | - |
| **Max Energy Balance Error** | $4.55 \times 10^{-13}\text{ kW}$ | $6.82 \times 10^{-13}\text{ kW}$ | - | Strict physical balance |

## 4. Key Scientific Observations
1. **Curtailment Reduction & Utilisation**: A 5,000 kWh battery with rule-based control captures $754.2\text{ MWh}$ of otherwise curtailed solar power, elevating annual renewable utilisation from $69.12\%$ to $80.69\%$.
2. **Failure of Rule-Based Control to Shave Peak Demand**:
   - The annual grid peak ($3,618.26\text{ kW}$) occurs during a dark, cold winter evening (December 2024) with zero solar generation.
   - Because the rule-based controller is greedy and non-anticipative, the battery has already been depleted hours prior to the peak. Consequently, the rule-based system achieves **0.00% peak reduction**.
   - This directly establishes the core scientific motivation for **Forecast-Informed Constrained Optimization** (Phases 7–8): an optimizer with lookahead foresight can strategically preserve battery energy specifically to shave high demand peaks and avoid high-price hours.

## 5. Generated Figures
- `figures/fig01_demand_vs_solar.png`: Full year daily power trajectories and summer high-solar week.
- `figures/fig02_daily_profiles.png`: 24-hour diurnal profile of load, solar, net load, and EPEX price.
- `figures/fig03_price_distribution.png`: EPEX NL price histogram and price duration curve.
- `figures/fig04_baseline_comparison.png`: Time series comparison of grid import and battery SOC under Grid-Only vs Rule-Based control.

## 6. Acceptance Gate Status
- [x] Baseline A (Grid-Only) and Baseline B (Rule-Based) implemented deterministically.
- [x] Energy balance validated on every timestep with error $< 10^{-12}\text{ kW}$.
- [x] SOC constraints ($10\% \le SOC \le 90\%$) strictly enforced.
- [x] Full unit test suite passes (`tests/test_baselines.py`).
- [x] Exploratory figures generated and saved.
- **GATE STATUS: PASSED**
