# GridFlex AI

## End-to-End Sequential Implementation Plan

### Overall Architecture

```text
                    PUBLIC ENERGY DATA
                           │
                           ▼
                 Data Acquisition Layer
                           │
                           ▼
                Data Quality / Validation
                           │
                           ▼
              Temporal Feature Engineering
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
     Renewable Forecast            Load Forecast
             │                           │
             └─────────────┬─────────────┘
                           ▼
                 Scenario Construction
                           │
                           ▼
                  Battery Simulation
                           │
                           ▼
             Constrained Optimization
                           │
                           ▼
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
 Grid-Only            Rule-Based          Forecast +
 Baseline              Battery           Optimization
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                  Test-Time Evaluation
                           │
                           ▼
               Sensitivity / Ablation
                           │
                           ▼
                 Final Research Report
                           │
                           ▼
                    Demo / Dashboard
```

---

# Phase 0 — Scope Lock and Repository Initialization

## Objective

Freeze the project scope before implementation begins.

## Actions

1. Inspect the current workspace.
2. Ensure the project is isolated from unrelated work.
3. Create or switch to a dedicated Git branch:
   `feat/gridflex-ai`
4. Create the initial repository structure.
5. Create:

   * README.md
   * requirements.txt or pyproject.toml
   * LICENSE if appropriate
   * .gitignore
   * configs/
   * data/raw/
   * data/processed/
   * src/
   * experiments/
   * tests/
   * reports/
   * figures/
6. Record Python version.
7. Establish a reproducible virtual environment.
8. Add the initial Git commit.

## Technology

* Python 3.11
* Git
* GitHub
* pandas
* NumPy
* PyArrow
* scikit-learn
* LightGBM
* SciPy
* Matplotlib
* pytest

## Phase exit criteria

* Environment works.
* Project structure exists.
* Dependencies install successfully.
* Git history begins with a clean baseline.

---

# Phase 1 — Dataset Acquisition and Data Lineage

## Objective

Acquire the main energy dataset and document exactly where every field originated.

## Primary Dataset

Use:

**OpenSTEF / Liander 2024 Energy Forecasting Benchmark**

The dataset is available on Hugging Face and contains:

* 15-minute electrical load measurements;
* solar-park measurements;
* wind-park measurements;
* historical weather measurements;
* weather forecasts;
* day-ahead electricity prices.

It covers the 2024 calendar year and 55 points in the Dutch grid. The dataset is distributed under CC BY 4.0, with source-data-specific licensing information documented by the dataset creators.

[OpenSTEF Liander 2024 dataset on Hugging Face](https://huggingface.co/datasets/OpenSTEF/liander2024-energy-forecasting-benchmark?utm_source=chatgpt.com)

## Acquisition

Use:

* huggingface_hub;
* datasets if convenient;
* PyArrow/Parquet;
* local cached files.

Do not rely on manually downloaded files in the final pipeline.

The code should be able to reproduce acquisition or clearly document the exact local-source mechanism.

## Actions

1. Inspect dataset directory structure.
2. Identify:

   * load files;
   * solar files;
   * wind files;
   * price file;
   * metadata;
   * weather data.
3. Inspect schema.
4. Record:

   * timestamp field;
   * timezone;
   * units;
   * missing values;
   * location identifiers;
   * availability timestamps.
5. Select a representative load series.
6. Select a representative solar series.
7. Determine whether their units and scale are directly compatible.
8. If not, construct an explicit scaling procedure.
9. Document the resulting scenario assumption.

## Deliverable

`reports/phase_01_data_audit.md`

Must contain:

* dataset provenance;
* selected files;
* selected signals;
* units;
* coverage;
* missingness;
* scaling assumptions;
* known limitations.

---

# Phase 2 — Data Cleaning and Scenario Construction

## Objective

Transform raw measurements into a clean modelling dataset.

## Temporal resolution

Primary simulation resolution:

**1 hour**

The original 15-minute measurements will be aggregated to hourly values for the main prototype.

15-minute data remains available for future expansion.

## Actions

1. Convert timestamps to UTC-aware datetime.
2. Sort chronologically.
3. Remove duplicates.
4. Detect missing intervals.
5. Quantify missingness.
6. Handle short missing gaps.
7. Explicitly mark longer gaps.
8. Validate physically impossible values.
9. Aggregate 15-minute data to hourly:

   * load;
   * solar generation;
   * wind if used.
10. Align hourly signals.
11. Join day-ahead prices where available.
12. Create the representative scenario.

## Scenario construction

Because the solar-park and load measurements may not represent one physical site:

```text
Observed load profile
        +
Selected renewable profile
        ↓
Scaling layer
        ↓
Representative grid node
```

The renewable penetration should be configurable.

Example scenarios:

* 20% renewable penetration;
* 40%;
* 60%.

The exact scaling definition must be expressed mathematically and written into the report.

## Deliverable

`data/processed/gridflex_hourly.parquet`

and

`reports/phase_02_preprocessing.md`

---

# Phase 3 — Exploratory Analysis and Baseline Definition

## Objective

Understand the system before training any model.

## Analyses

Produce:

1. renewable-generation time series;
2. demand time series;
3. daily renewable profiles;
4. daily load profiles;
5. seasonal behaviour;
6. renewable-to-demand ratio;
7. renewable surplus periods;
8. renewable deficit periods;
9. peak demand periods;
10. price distribution.

## Baseline A — Grid Only

Calculate:

* total grid energy;
* peak grid demand;
* renewable curtailment;
* renewable utilisation;
* energy cost if price data are used.

## Baseline B — Rule-Based Battery

Implement:

```text
if renewable > demand:
    charge battery
    curtail remainder if battery is full

if renewable < demand:
    discharge battery
    import remainder from grid if battery is insufficient
```

## Deliverable

A baseline evaluation table and visualizations.

---

# Phase 4 — Forecasting Dataset Construction

## Objective

Create leakage-free ML datasets.

## Targets

Two targets:

1. renewable generation;
2. electricity demand.

## Forecast horizon

Primary:

**next 24 hourly observations**

## Features

Initial feature set:

### Calendar

* hour;
* day of week;
* day of year;
* month;
* weekend flag.

### Lag features

* lag 1;
* lag 2;
* lag 3;
* lag 24;
* lag 48;
* lag 72;
* lag 168.

### Rolling features

* 3-hour mean;
* 6-hour mean;
* 24-hour mean;
* 24-hour standard deviation;
* 168-hour mean.

Only historical data may be used.

## Weather

Do not use actual future weather measurements in the first production experiment.

If weather is introduced, only use information that would genuinely be available at prediction time.

The benchmark contains weather forecasts and availability timestamps, making a future version of the prototype possible, but this is not necessary for the September deadline.

---

# Phase 5 — Forecasting Models

## Objective

Build and evaluate a reliable forecasting component.

## Baseline

Persistence:

```text
forecast(t + 24h) = observed(t)
```

or equivalent horizon-specific historical baseline.

## ML Model

Primary:

**LightGBM Regressor**

Build separate direct forecasting models for the 24 horizons if computationally reasonable.

Alternative:

recursive multi-step forecasting if implementation simplicity becomes more important than the direct formulation.

The choice must be documented.

## Split

Chronological:

```text
70% → Training
15% → Validation
15% → Test
```

No random shuffle.

## Evaluation

Metrics:

* MAE;
* RMSE;
* nRMSE;
* optional MAPE where target values make it meaningful.

Evaluate:

```text
Persistence
vs
LightGBM
```

## Model tracking

Save:

* model parameters;
* feature list;
* training period;
* validation metrics;
* test metrics.

Do not tune on the test set.

## Phase gate

Do not proceed to final optimization experiments until:

1. Forecast predictions exist for the entire test period.
2. The baseline comparison is complete.
3. Leakage checks pass.
4. Errors are documented.

---

# Phase 6 — Battery Energy Storage System Simulator

## Objective

Create a deterministic battery simulator independent of the optimizer.

## Configurable parameters

* energy capacity;
* maximum charge power;
* maximum discharge power;
* minimum SOC;
* maximum SOC;
* charge efficiency;
* discharge efficiency;
* initial SOC.

Example starting configuration:

```yaml
battery:
  capacity_kwh: configurable
  max_charge_kw: configurable
  max_discharge_kw: configurable
  min_soc: 0.20
  max_soc: 0.90
  charge_efficiency: 0.95
  discharge_efficiency: 0.95
  initial_soc: 0.50
```

Values are prototype assumptions, not measured battery specifications.

## Simulator equations

For charging:

$$
SOC_{t+1}
=
SOC_t
+
\frac{\eta_c P_{charge,t}\Delta t}{E_{max}}
$$

For discharging:

$$
SOC_{t+1}
=
SOC_t
-
\frac{P_{discharge,t}\Delta t}
{\eta_d E_{max}}
$$

Enforce:

$$
SOC_{min} \le SOC_t \le SOC_{max}
$$

## Required checks

At every timestep:

* energy balance;
* SOC bounds;
* charge-power bound;
* discharge-power bound;
* no negative grid import;
* no negative curtailment.

## Unit tests

Create tests for:

* empty battery;
* full battery;
* surplus generation;
* severe deficit;
* maximum charge;
* maximum discharge;
* efficiency losses;
* SOC boundary conditions.

---

# Phase 7 — Forecast-Informed Optimization

## Objective

Determine the optimal battery operating schedule using forecasted future conditions.

## Decision variables

For every timestep:

* battery charge;
* battery discharge;
* SOC;
* grid import;
* renewable curtailment.

## Energy-balance constraint

$$
Load_t
=
Renewable_t
+
Grid_t
+
Discharge_t
-
Charge_t
-
Curtailment_t
$$

## Objective

A weighted objective:

$$
J =
\alpha \sum_t Price_t Grid_t
+
\beta \max(Grid_t)
+
\gamma \sum_t Curtailment_t
+
\delta \sum_t (Charge_t + Discharge_t)
$$

The exact coefficients must be configurable.

## Solver

Use:

**SciPy `linprog`**

unless the formulation demonstrably requires a different solver.

The project should favour a transparent linear formulation over unnecessary optimization complexity.

## Optimization modes

### Mode A

Rule-based.

### Mode B

Forecast-informed optimization.

### Mode C

Perfect-foresight optimization.

The perfect-foresight mode receives actual future load and renewable generation and therefore represents an oracle upper bound rather than a deployable strategy.

---

# Phase 8 — Integrated Rolling-Horizon System

## Objective

Connect forecasting and optimization without giving the optimizer information it would not possess in reality.

Pipeline:

```text
Historical data up to t
        ↓
Forecast next 24 h
        ↓
Optimization
        ↓
First control action
        ↓
Advance timestep
        ↓
Observe new data
        ↓
Forecast again
        ↓
Re-optimize
```

This is a rolling/receding-horizon controller.

Only the first action from each optimization window should be applied.

This prevents the optimizer from receiving future actual measurements that would not be available during operation.

---

# Phase 9 — Experimental Evaluation

## Objective

Determine whether the project actually works.

## Systems compared

| System                   | Forecast      | Battery | Optimization |
| ------------------------ | ------------- | ------- | ------------ |
| Grid Only                | No            | No      | No           |
| Rule-Based               | No            | Yes     | No           |
| Forecast + Optimization  | Yes           | Yes     | Yes          |
| Perfect-Foresight Oracle | Actual future | Yes     | Yes          |

## Primary system metrics

### Grid dependence

$$
GridReduction =
\frac{Grid_{baseline} - Grid_{system}}
{Grid_{baseline}}
$$

### Peak shaving

$$
PeakReduction =
\frac{Peak_{baseline} - Peak_{system}}
{Peak_{baseline}}
$$

### Renewable utilisation

$$
RenewableUtilisation =
1 -
\frac{Curtailment}{AvailableRenewable}
$$

### Cost

$$
Cost = \sum_t Price_t Grid_t \Delta t
$$

### Battery metrics

* average SOC;
* minimum SOC;
* maximum SOC;
* battery throughput;
* charge/discharge cycles;
* number of constraint violations.

## Required experiments

### Experiment 1

Baseline vs rule-based battery.

### Experiment 2

Rule-based vs forecast optimization.

### Experiment 3

Forecast optimization vs perfect foresight.

### Experiment 4

20%, 40%, 60% renewable penetration.

### Experiment 5

2-hour vs 4-hour battery duration.

### Experiment 6

Forecast error sensitivity.

---

# Phase 10 — Error Analysis and Scientific Review

## Objective

Determine why the system succeeds or fails.

Analyze:

* high-error forecast periods;
* cloudy/variable renewable periods;
* demand peaks;
* battery saturation;
* battery depletion;
* curtailment periods;
* price spikes;
* forecast-vs-oracle performance gap.

Questions:

1. Does forecast error cause bad battery decisions?
2. Does the battery saturate during renewable peaks?
3. Is the battery too small?
4. Does increasing battery duration improve outcomes?
5. Does higher renewable penetration increase the value of storage?
6. Where does the system fail?

The answer should not simply be "the model works."

The report must explain operating behaviour.

---

# Phase 11 — Reproducibility, Testing and Packaging

## Objective

Turn the research experiment into a usable prototype.

## Code quality

Run:

* pytest;
* ruff;
* import checks;
* configuration validation.

## Reproducibility

Provide:

```text
1 command → data preparation
1 command → model training
1 command → evaluation
```

or an equivalent documented workflow.

## Artifacts

Final repository should contain:

```text
gridflex-ai/
│
├── configs/
│   ├── default.yaml
│   └── scenarios.yaml
│
├── data/
│   ├── raw/
│   └── processed/
│
├── src/
│   ├── data/
│   ├── features/
│   ├── forecasting/
│   ├── battery/
│   ├── optimization/
│   └── evaluation/
│
├── experiments/
│
├── tests/
│
├── figures/
│
├── reports/
│
├── README.md
├── requirements.txt
└── EXECUTION_LOG.md
```

---

# Phase 12 — Optional Demonstration Interface

Only start this phase after the scientific core passes all previous gates.

Build a small Streamlit interface showing:

1. demand;
2. renewable generation;
3. forecast;
4. battery SOC;
5. charge/discharge;
6. grid import;
7. curtailment;
8. baseline vs optimized result.

The dashboard is a presentation layer.

It is not part of the scientific core.

If time is insufficient, omit it.

A correct experiment with no dashboard is preferable to a polished dashboard sitting on an unreliable experiment.

---

# Phase 13 — Final Research Package

The final package must contain:

### README

* problem;
* architecture;
* dataset;
* methodology;
* experiments;
* results;
* limitations;
* reproduction instructions.

### Final report

Sections:

1. Abstract
2. Problem Definition
3. Dataset
4. Methodology
5. Forecasting
6. Battery Model
7. Optimization
8. Experimental Setup
9. Results
10. Sensitivity Analysis
11. Failure Analysis
12. Limitations
13. Future Work
14. Conclusion

### Final figures

At minimum:

1. Renewable generation vs demand.
2. Forecast vs actual.
3. Forecast-error distribution.
4. Battery SOC.
5. Grid import before/after optimization.
6. Renewable curtailment.
7. Performance across renewable penetration.
8. Forecast vs perfect-foresight performance gap.

### Final result statement

The final conclusion must explicitly answer:

> Did forecast-informed storage optimization measurably improve system flexibility relative to the selected baselines?

The answer must be based on the final held-out test set.

---

# Recommended deadline schedule

### September 21

Phase 0

### September 22

Phase 1

### September 23

Phase 2–3

### September 24

Phase 4

### September 25

Phase 5

### September 26

Phase 6

### September 27

Phase 7

### September 28

Phase 8–9

### September 29

Phase 10–11

### September 30

Phase 12–13 + application submission

If the project falls behind, cut the dashboard first, then secondary datasets, then advanced weather features.

Do not cut:

**data validation → leakage control → forecasting evaluation → battery constraints → optimization → baseline comparison.**
