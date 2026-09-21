# Phase 2 Report — Cleaning and Preprocessing

## 1. Objective
Transform the raw 15-minute OpenSTEF benchmark measurements into a continuous, leak-free, hourly modelling dataset for the complete 2024 calendar leap year (8,784 hours), calibrating the representative solar penetration layer.

## 2. Preprocessing & Cleaning Implementation
- **Source Files Ingested**:
  - `data/raw/load_measurements/mv_feeder/OS Leiden Noord.parquet`
  - `data/raw/load_measurements/solar_park/Within 10 kilometers of Westwoud_normalized.parquet`
  - `data/raw/EPEX.parquet`
- **Missing Data Resolution**:
  - Exactly 3 records were missing at `2024-10-27 00:15:00`, `00:30:00`, `00:45:00` (UTC) due to European daylight saving time adjustment.
  - Causal forward-fill with a tight 4-step limit ($\le 1$ hour) resolved the gap without using future observations.
  - Remaining missing values after fill: 0.
- **Physical Validity & Sign Conventions**:
  - Load: converted from Watts to kW ($P_{load} = \text{load} / 1000.0$). Strictly positive: minimum observed load is $1,016.67\text{ kW}$.
  - Solar: normalized generation inverted from OpenSTEF negative load convention: $s(t) = \max(0.0, -\text{load}_{norm}) \in [0.0, 1.0]$.
  - Market Price: converted from EUR/MWh to EUR/kWh ($\text{Price} = \text{EPEX\_NL} / 1000.0$).
- **Hourly Aggregation**:
  - 15-minute observations resampled to 1-hour left-closed intervals via mean aggregation, representing average hourly power (kW) and energy (kWh over $\Delta t = 1\text{ h}$).

## 3. Representative Scenario Calibration
- Target annual renewable penetration: $\rho = 40.0\%$
- Total annual electricity demand: $16,296,839.99\text{ kWh} \approx 16.30\text{ GWh}$
- Annual normalized solar yield factor: $1,348.80\text{ h}$ (capacity factor $= 15.36\%$)
- Calibrated Solar Nameplate Capacity:
  $$C_{solar} = \frac{0.40 \times 16,296,839.99}{1,348.80} = 4,833.02\text{ kW} \approx 4.83\text{ MW}$$
- Achieved annual solar energy: $6,518,736.00\text{ kWh} \approx 6.52\text{ GWh}$ (exactly $40.000\%$).

## 4. Hourly Dataset Summary Statistics (8,784 Timesteps)
| Variable | Unit | Minimum | Mean | Maximum | Std Dev |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `load_kw` | kW | 1,016.67 | 1,855.29 | 3,694.17 | 515.63 |
| `solar_factor` | - | 0.0000 | 0.1536 | 0.9978 | 0.2442 |
| `solar_kw` | kW | 0.00 | 742.11 | 4,822.24 | 1,180.19 |
| `net_load_kw` | kW | -3,673.91 | 1,113.17 | 3,618.26 | 1,312.58 |
| `surplus_kw` | kW | 0.00 | 229.13 | 3,673.91 | 631.37 |
| `deficit_kw` | kW | 0.00 | 1,342.30 | 3,618.26 | 842.06 |
| `price_eur_kwh` | €/kWh | -0.2000 | 0.0773 | 0.8730 | 0.0495 |

## 5. Energy Balance & Validation Checks
- **Hourly Continuity**: Perfectly regular 1-hour interval across the entire year (366 days $\times$ 24 hours $= 8,784$ steps).
- **Physical Balance Identity**: For all $t$, $|P_{net}(t) - (P_{deficit}(t) - P_{surplus}(t))| < 10^{-6}\text{ kW}$.
- **Saved Output**: `data/processed/gridflex_hourly.parquet` (686 KB).

## 6. Acceptance Gate Status
- [x] Clean hourly dataset exists and persisted to parquet.
- [x] No missing or NaN values across 8,784 records.
- [x] Schema and units documented.
- [x] Processing is deterministic, causal, and fully reproducible.
- **GATE STATUS: PASSED**
