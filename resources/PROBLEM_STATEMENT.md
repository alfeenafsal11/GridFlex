# GridFlex AI

## Forecast-Driven Renewable Energy Storage and Grid Flexibility Optimization

### 1. Problem Context

The rapid deployment of variable renewable-energy resources such as solar and wind introduces a systems problem that is different from simply generating more renewable electricity.

Renewable generation is variable over time, while electricity demand also changes continuously. Generation may exceed demand during periods of strong solar or wind production and fall below demand when renewable output decreases. Without sufficient flexibility, the mismatch can result in increased reliance on the conventional grid, renewable-energy curtailment, higher peak demand, and under-utilisation of available renewable generation.

Battery energy storage can provide temporal flexibility by charging when renewable generation is available in excess of demand and discharging when generation is insufficient. However, the battery itself is a constrained resource: it has finite energy capacity, finite charging/discharging power, efficiency losses, state-of-charge limits, and operating constraints.

Consequently, the central problem is not simply:

> "Should the battery charge or discharge?"

The actual problem is:

> **Given uncertain renewable generation and electricity demand, how should a finite battery be scheduled over time so that renewable energy is utilised more effectively while reducing grid dependence, peak demand and operating cost without violating physical battery constraints?**

This creates an intersection of three technical domains:

1. **Machine learning** — forecasting future renewable generation and demand.
2. **Energy-storage modelling** — representing battery state and operational constraints.
3. **Optimization** — determining the battery schedule that best satisfies the system objective.

### 2. Motivation

This project exists to investigate whether a data-driven forecasting-and-optimization pipeline can improve the operational flexibility of a renewable-heavy electricity system compared with simpler operational strategies.

The project is deliberately framed as a research-oriented prototype rather than a production grid-control system.

Its purpose is to demonstrate that an AI/ML engineering capability can be applied to a concrete energy-transition problem involving renewable integration, storage and grid flexibility.

This direction is particularly relevant to the IRENA Youth Forum context because IRENA's 2026 Youth Forum explicitly explored AI and digitalisation in renewable energy and identified emerging roles involving energy data analytics, data science, AI/ML and software development.

### 3. System Scenario

The prototype models a representative renewable-energy grid node.

The node consists of:

* electricity demand;
* variable renewable generation, primarily solar and optionally wind;
* a battery energy-storage system;
* electricity imported from the external grid;
* renewable-energy curtailment when available generation cannot be consumed or stored;
* time-varying electricity prices for economic evaluation.

The real-world measurements are obtained from an open energy-system dataset.

Because the selected public benchmark does not guarantee that a specific solar-park measurement and a specific feeder-load measurement represent a physically co-located site, the prototype will explicitly construct a configurable representative scenario by scaling renewable generation relative to a selected load profile.

This assumption will be documented rather than hidden.

### 4. Input Problem

At time t, the system has historical observations of:

* electricity demand;
* renewable generation;
* timestamps and calendar variables;
* optionally weather measurements or weather forecasts;
* electricity prices.

The system must use information available up to time t to estimate future operating conditions.

It must not use future actual measurements when generating predictions used by the optimizer.

### 5. Forecasting Task

The first computational task is to forecast:

* future renewable generation;
* future electricity demand.

The primary prototype horizon will be the next 24 hours at hourly resolution.

The forecasting system will compare:

* a naïve persistence baseline;
* a machine-learning forecasting model based primarily on historical temporal features.

The initial ML model will be LightGBM because it is computationally efficient, well suited to structured time-series features and compatible with the user's existing technical expertise.

Forecasting accuracy will be measured using:

* MAE;
* RMSE;
* normalized error where appropriate.

### 6. Battery-Storage Task

The second task is to construct a physically constrained battery model.

The battery must maintain:

* minimum state of charge;
* maximum state of charge;
* maximum charging power;
* maximum discharging power;
* charging efficiency;
* discharging efficiency;
* finite energy capacity.

The energy balance must satisfy the relationship:

Renewable generation + grid import + battery discharge

=

Electricity demand + battery charge + renewable curtailment

at every timestep.

The system must never silently violate this balance.

### 7. Optimization Task

The third task is to determine the battery operating schedule.

The optimization objective will minimise a weighted combination of:

* electricity imported from the external grid;
* peak grid demand;
* electricity cost;
* renewable-energy curtailment;
* unnecessary battery throughput.

The optimization will be implemented as a constrained linear optimization problem.

A configurable objective function will allow the relative importance of cost, peak demand and renewable utilisation to be changed without rewriting the system.

### 8. Comparative Evaluation

The proposed system must not be evaluated in isolation.

It will be compared against at least:

#### Baseline 1 — Grid-Only

Renewable generation serves the load when available and all remaining demand is supplied by the grid. No battery is used.

#### Baseline 2 — Rule-Based Battery

A simple controller:

* charge when renewable surplus is available;
* discharge when renewable generation is insufficient;
* obey battery limits.

#### Baseline 3 — Forecast-Informed Optimization

The proposed system:

Forecast → Battery Optimization → Operating Schedule.

#### Baseline 4 — Perfect-Foresight Oracle

The optimizer receives actual future renewable generation and demand.

This is not a deployable system. It is an upper-bound reference showing how much performance is theoretically available if uncertainty is removed.

### 9. Core Research Question

> **Can machine-learning-based forecasts combined with constrained battery-storage optimization reduce grid dependence and peak demand while increasing renewable-energy utilisation compared with rule-based battery management?**

### 10. Secondary Questions

The project should also investigate:

1. How much does forecasting accuracy affect storage performance?
2. How does increasing renewable penetration affect grid dependence?
3. How does battery duration affect peak shaving and renewable utilisation?
4. What is the performance gap between forecast-informed optimization and perfect foresight?
5. Under what operating conditions does the proposed approach stop producing meaningful benefits?

### 11. Hypothesis

The working hypothesis is:

> **Forecast-informed optimization will improve renewable utilisation and reduce selected grid-operation metrics compared with simple rule-based battery control, while remaining within all battery and energy-balance constraints.**

The hypothesis is not assumed to be true.

The experiment must be allowed to disprove it.

### 12. Scientific Integrity Requirements

The project must:

* use chronological train/validation/test separation;
* prevent future-data leakage;
* distinguish actual future values from values available to a controller at decision time;
* report negative or insignificant results;
* avoid fabricated metrics;
* preserve the exact configuration used for final evaluation;
* make the experiment reproducible from a clean environment.

### 13. Intended Outcome

The final result is not intended to prove that AI can operate a real electrical grid.

It is intended to produce a credible research prototype demonstrating the complete pipeline:

**real energy data**

→ **data quality and temporal feature engineering**

→ **renewable/load forecasting**

→ **battery simulation**

→ **constrained optimization**

→ **baseline comparison**

→ **quantitative evaluation**

→ **interpretable conclusions about grid flexibility.**

### 14. Final Positioning

The resulting prototype should demonstrate the application of AI/ML and software engineering to renewable-energy system flexibility.

The project therefore provides a concrete bridge between:

**AI/ML engineering**

and

**renewable-energy integration, energy storage and grid flexibility.**

It should be presented explicitly as a research prototype and decision-support simulation, not as an operational control system for real electrical infrastructure.
