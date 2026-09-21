# Phase 10 Report — Required Metrics Specification and Analysis

## 1. Objective
Formally document the mathematical formulas, definitions, and observed values for all primary, derived, and oracle gap metrics across the forecasting and system simulation layers.

## 2. Metric Formulations

### A. Forecasting Evaluation Metrics
Evaluated over $N$ held-out test predictions $\hat{y}_i$ against ground truth $y_i$:

1. **Mean Absolute Error (MAE)**:
   $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |y_i - \hat{y}_i| \quad [\text{kW}]$$
2. **Root Mean Squared Error (RMSE)**:
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2} \quad [\text{kW}]$$
3. **Normalized RMSE (nRMSE)**:
   $$\text{nRMSE} = \frac{\text{RMSE}}{\bar{y}} \times 100\% \quad \text{where } \bar{y} = \frac{1}{N}\sum_{i=1}^N y_i$$

### B. Energy System Primary Metrics
Evaluated over $T$ simulation hours ($\Delta t = 1.0\text{ h}$):

1. **Total Grid Energy Imported ($E_{grid}$)**:
   $$E_{grid} = \sum_{t=1}^{T} P_{grid}(t) \Delta t \quad [\text{kWh}]$$
2. **Peak Grid Demand ($P_{grid, peak}$)**:
   $$P_{grid, peak} = \max_{t \in [1, T]} P_{grid}(t) \quad [\text{kW}]$$
3. **Total Electricity Cost ($C_{total}$)**:
   $$C_{total} = \sum_{t=1}^{T} \text{Price}(t) \cdot P_{grid}(t) \cdot \Delta t \quad [\text{EUR}]$$
4. **Renewable Energy Curtailment ($E_{curt}$)**:
   $$E_{curt} = \sum_{t=1}^{T} P_{curt}(t) \Delta t \quad [\text{kWh}]$$
5. **Renewable Energy Utilisation ($\text{Util}_{ren}$)**:
   $$\text{Util}_{ren} = \left( 1 - \frac{\sum_{t=1}^T P_{curt}(t)}{\sum_{t=1}^T P_{solar}(t)} \right) \times 100\%$$
6. **Battery Energy Throughput ($E_{thru}$)**:
   $$E_{thru} = \sum_{t=1}^{T} (P_c(t) + P_d(t)) \Delta t \quad [\text{kWh}]$$

### C. Derived Comparative Metrics
Comparing evaluated system ($sys$) against baseline ($base$):

1. **Grid Energy Reduction Percentage**:
   $$\text{GridReduction} = \frac{E_{grid, base} - E_{grid, sys}}{E_{grid, base}} \times 100\%$$
2. **Peak Demand Reduction Percentage**:
   $$\text{PeakReduction} = \frac{P_{peak, base} - P_{peak, sys}}{P_{peak, base}} \times 100\%$$
3. **Total Electricity Cost Savings Percentage**:
   $$\text{CostSavings} = \frac{C_{total, base} - C_{total, sys}}{C_{total, base}} \times 100\%$$
4. **Renewable Utilisation Gain**:
   $$\Delta \text{Util} = \text{Util}_{ren, sys} - \text{Util}_{ren, base} \quad [\text{percentage points}]$$

### D. Oracle Reference Gap
Quantifying suboptimality of deployable forecast-informed optimization ($C$) relative to perfect-foresight upper bound ($D$):

1. **Economic Cost Gap**:
   $$\text{CostGap} = \frac{C_{total, C} - C_{total, D}}{C_{total, D}} \times 100\%$$
2. **Peak Demand Gap**:
   $$\text{PeakGap} = P_{peak, C} - P_{peak, D} \quad [\text{kW}]$$

## 3. Complete Metric Values (Held-Out Test Set: 1,290 Hours)

| Metric | Unit | System A (Grid-Only) | System B (Rule-Based) | System C (Forecast Opt) | System D (Oracle) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Grid Import** | kWh | 2,660,221 | 2,658,321 | 2,678,332 | 2,682,513 |
| **Peak Demand** | kW | 3,279.17 | 3,279.17 | **3,033.40** | **2,897.50** |
| **Electricity Cost** | EUR | €312,513 | €312,194 | **€298,742** | **€296,611** |
| **Curtailment** | kWh | 0.00 | 0.00 | 0.00 | 0.00 |
| **Utilisation** | % | 100.0% | 100.0% | 100.0% | 100.0% |
| **Throughput** | kWh | 0.00 | 3,800 | 536,211 | 557,801 |
| **Mean SOC** | - | - | 0.499 | 0.354 | 0.381 |
| **Min SOC** | - | - | 0.498 | 0.100 | 0.100 |
| **Max SOC** | - | - | 0.500 | 0.900 | 0.900 |

### Derived Comparative Metrics vs Rule-Based Baseline
- **Peak Shaving**: **-7.49%** ($245.77\text{ kW}$ reduction)
- **Cost Savings**: **-4.31%** (€$13,452$ savings)
- **Oracle Economic Gap**: **+0.72%** (€$2,131$ above perfect foresight)
- **Oracle Peak Gap**: **+135.90 kW**

## 4. Acceptance Gate Status
- [x] All primary metric mathematical definitions documented.
- [x] All derived percentage improvement formulas formalized.
- [x] Oracle performance gap quantified.
- [x] Unit test suite passes (`tests/test_metrics.py`).
- **GATE STATUS: PASSED**
