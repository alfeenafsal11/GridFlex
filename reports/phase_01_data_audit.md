# Phase 1 Report — Data Acquisition and Audit

## 1. Objective
Acquire the OpenSTEF / Liander 2024 Short Term Energy Forecasting Benchmark dataset, perform an exhaustive structural audit of the time index, column schema, units, missingness, and values, and establish a mathematically rigorous, documented scaling method for representative grid node construction.

## 2. Dataset Provenance and Lineage
- **Source Repository**: `OpenSTEF/liander2024-energy-forecasting-benchmark` (Hugging Face)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Publisher**: Liander N.V. / OpenSTEF
- **Temporal Span**: Complete 2024 calendar leap year (2024-01-01 00:00:00 UTC to 2024-12-31 23:45:00 UTC)
- **Native Resolution**: 15 minutes (35,136 timesteps)

## 3. Audited Asset Details

### A. Electrical Load Series: `OS Leiden Noord.parquet`
- **Location**: Latitude 52.174, Longitude 4.494 (Leiden, Netherlands)
- **Asset Type**: Medium Voltage (MV) Feeder Substation
- **Native Units**: Watts (W)
- **Observed Range**:
  - Minimum: 986,666.67 W (986.67 kW)
  - Mean: 1,855,331.17 W (1,855.33 kW)
  - Maximum: 3,763,333.33 W (3,763.33 kW)
  - Standard Deviation: 519,280.32 W (519.28 kW)
- **Selection Justification**: Unlike other feeders (such as `OS Edam`, whose minimum load is -1,130 kW due to unmetered rooftop PV backfeed into the medium-voltage grid), `OS Leiden Noord` maintains strictly positive demand throughout the year. It represents a clean, uncontaminated consumer demand profile.

### B. Solar Generation Series: `Within 10 kilometers of Westwoud_normalized.parquet`
- **Location**: Latitude 52.684, Longitude 5.133 (Westwoud, North Holland)
- **Asset Type**: Commercial Solar Photovoltaic Park
- **Native Units**: Normalized power relative to nominal capacity ($[-1.0, 0.01]$)
- **Sign Convention**: Generation fed into the grid is negative in OpenSTEF conventions (-1.0 = 100% nominal peak generation). Small positive values (+0.01) represent nocturnal parasitic inverter consumption.
- **Physical Solar Power Extraction**:
  $$s(t) = \max(0.0, -\text{load}_{norm}(t)) \in [0.0, 1.0]$$

### C. Day-Ahead Electricity Market Prices: `EPEX.parquet`
- **Market Zone**: EPEX Spot Netherlands (EPEX_NL)
- **Native Units**: EUR/MWh (€/MWh)
- **Observed Range**:
  - Minimum: -200.00 EUR/MWh (-0.200 EUR/kWh, negative price during high renewable surplus)
  - Mean: 77.29 EUR/MWh (0.07729 EUR/kWh)
  - Maximum: 872.96 EUR/MWh (0.87296 EUR/kWh, extreme scarcity peak)
  - Standard Deviation: 62.45 EUR/MWh
- **Conversion to Modelling Units**:
  $$\text{Price}(t) \, [\text{EUR/kWh}] = \frac{\text{EPEX\_NL}(t)}{1000.0}$$

## 4. Missingness and Quality Assessment
- **Timestamps**: All 35,136 expected 15-minute timestamps exist. No duplicate timestamps exist.
- **Timezone**: Native index is explicit `UTC`.
- **Missing Values**:
  - Exactly 3 records missing in load and solar files at `2024-10-27 00:15:00+00:00`, `2024-10-27 00:30:00+00:00`, `2024-10-27 00:45:00+00:00` (European DST transition).
  - Total missing rate: $3 / 35,136 = 0.0085\%$ (negligible).
  - Clean causal linear interpolation or forward-fill during Phase 2 preprocessing will handle this 45-minute gap without future leakage.

## 5. Representative Scenario Scaling Methodology
Because the solar park and MV feeder load are geographically distributed in the Dutch network, we construct a representative microgrid/distribution substation scenario:
Let $P_{load}(t)$ be the feeder load in kW.
Let $s(t) \in [0, 1]$ be the normalized solar capacity factor.
For a target annual renewable penetration $\rho \in \{0.20, 0.40, 0.60\}$:

1. Compute total annual demand energy:
   $$E_{demand} = \sum_{t=1}^{T} P_{load}(t) \Delta t$$
2. Compute total annual normalized solar yield:
   $$Y_{norm} = \sum_{t=1}^{T} s(t) \Delta t$$
3. Calibrate solar nameplate capacity $C_{solar}$ (kW):
   $$C_{solar} = \frac{\rho \cdot E_{demand}}{Y_{norm}}$$
4. The scaled renewable generation is:
   $$P_{solar}(t) = C_{solar} \cdot s(t)$$

This guarantees:
$$\frac{\sum_{t=1}^{T} P_{solar}(t)}{\sum_{t=1}^{T} P_{load}(t)} \equiv \rho$$
For the base scenario ($\rho = 0.40$), total annual solar energy equals 40% of total electrical demand.

## 6. Acceptance Gate Status
- [x] Dataset successfully downloaded and cached locally in `data/raw/`.
- [x] Columns, schema, and units identified and documented.
- [x] Time axis validated (15-min, 35,136 steps, UTC timezone).
- [x] Missing values quantified ($0.0085\%$) and explained.
- [x] Selected signals justified (`OS Leiden Noord` for pure demand, `Westwoud` for solar, `EPEX_NL` for prices).
- [x] Renewable penetration scaling formula formalized.
- **GATE STATUS: PASSED**
