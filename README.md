# GridFlex AI — Forecast-Driven Renewable Energy Storage and Grid Flexibility Optimization

A reproducible, technically defensible research prototype for renewable energy storage dispatch and grid flexibility optimization, designed for submission to the **IRENA Youth Forum 2027**.

## Core Research Question
> **Can machine-learning-based forecasts combined with constrained battery-storage optimization reduce grid dependence and peak demand while increasing renewable-energy utilisation compared with rule-based battery management?**

## System Architecture

```text
       OpenSTEF / Liander Benchmark (2024)
                        │
                        ▼
            Data Acquisition & Lineage
                        │
                        ▼
      Data Cleaning & 1h UTC Normalization
                        │
                        ▼
          Temporal Feature Engineering
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
  Solar Generation              Electrical Demand
  24h LightGBM Forecast         24h LightGBM Forecast
         │                             │
         └──────────────┬──────────────┘
                        ▼
             Constrained LP Optimizer
             (SciPy HiGHS Solver)
                        │
                        ▼
         Receding-Horizon Simulation Loop
                        │
                        ▼
    Comparative Evaluation Across 4 Systems:
    - System A: Grid-Only
    - System B: Rule-Based Battery
    - System C: Forecast-Informed Optimization
    - System D: Perfect-Foresight Oracle
                        │
                        ▼
          Sensitivity & Error Analysis
```

## Repository Structure

```text
├── configs/          # YAML configuration files (default and scenarios)
├── data/
│   ├── raw/          # Cached raw benchmark series
│   └── processed/    # Processed hourly modelling dataset
├── src/
│   ├── data/         # Ingestion, validation, and preprocessing
│   ├── features/     # Causal temporal feature engineering
│   ├── forecasting/  # Persistence and LightGBM direct forecasters
│   ├── battery/      # Physically constrained battery simulator
│   ├── optimization/ # Constrained LP formulation & MPC loop
│   ├── evaluation/   # Metrics, error analysis, and visualization
│   └── utils/        # Logging and configuration utilities
├── experiments/      # Experiment runners and ablation sweeps
├── tests/            # Automated test suite
├── figures/          # High-resolution research plots
├── reports/          # Detailed phase-by-phase scientific reports
├── requirements.txt  # Pinned dependencies
├── EXECUTION_LOG.md  # Chronological execution audit trail
└── README.md
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run test suite
pytest tests/ -v

# 3. Code quality inspection
ruff check src/ tests/ configs/
```
