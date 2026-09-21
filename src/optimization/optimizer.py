"""Constrained linear programming optimization for battery storage dispatch."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from src.utils.logger import get_logger

logger = get_logger("optimization.optimizer")


@dataclass
class OptimizationResult:
    """Structured result returned by the constrained LP optimizer."""

    success: bool
    status_message: str
    objective_value: float
    charge_kw: np.ndarray
    discharge_kw: np.ndarray
    grid_import_kw: np.ndarray
    curtailment_kw: np.ndarray
    energy_kwh: np.ndarray
    soc: np.ndarray
    peak_grid_kw: float
    max_balance_error_kw: float


class BatteryLPOptimizer:
    """Linear programming optimizer for battery dispatch over horizon H.
    
    Decision Variables vector x of length (5 * H + 1):
        x[0 : H]         -> P_charge (t = 0 .. H-1)
        x[H : 2H]        -> P_discharge (t = 0 .. H-1)
        x[2H : 3H]       -> P_grid_import (t = 0 .. H-1)
        x[3H : 4H]       -> P_curtailment (t = 0 .. H-1)
        x[4H : 5H]       -> Stored Energy E_t (t = 0 .. H-1)
        x[5H]            -> Peak Grid Import P_grid_peak
        
    Objective:
        min  sum_{t} [ alpha * Price_t * P_grid_t + gamma * P_curt_t + delta * (P_c_t + P_d_t) ] * dt
             + beta * P_grid_peak
             
    Subject to:
        1. Node energy balance: P_grid_t + P_d_t - P_c_t - P_curt_t = P_load_t - P_solar_t
        2. Battery energy continuity: E_{t+1} - E_t - eta_c * P_c_t * dt + (1 / eta_d) * P_d_t * dt = 0
        3. Peak grid definition: P_grid_t - P_grid_peak <= 0
        4. Bounds:
            0 <= P_c <= max_charge_kw
            0 <= P_d <= max_discharge_kw
            0 <= P_grid
            0 <= P_curt
            min_soc * E_cap <= E_t <= max_soc * E_cap
            0 <= P_grid_peak
    """

    def __init__(
        self,
        capacity_kwh: float = 5000.0,
        max_charge_kw: float = 1250.0,
        max_discharge_kw: float = 1250.0,
        min_soc: float = 0.10,
        max_soc: float = 0.90,
        charge_efficiency: float = 0.95,
        discharge_efficiency: float = 0.95,
        alpha: float = 1.0,
        beta: float = 0.5,
        gamma: float = 2.0,
        delta: float = 0.01,
        dt_hours: float = 1.0,
    ):
        self.capacity_kwh = float(capacity_kwh)
        self.max_charge_kw = float(max_charge_kw)
        self.max_discharge_kw = float(max_discharge_kw)
        self.min_soc = float(min_soc)
        self.max_soc = float(max_soc)
        self.charge_efficiency = float(charge_efficiency)
        self.discharge_efficiency = float(discharge_efficiency)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.gamma = float(gamma)
        self.delta = float(delta)
        self.dt_hours = float(dt_hours)

    def optimize(
        self,
        load_kw: np.ndarray,
        solar_kw: np.ndarray,
        price_eur_kwh: np.ndarray,
        initial_soc: float,
    ) -> OptimizationResult:
        """Solve constrained LP for given horizon inputs and initial battery state."""
        H = len(load_kw)
        assert len(solar_kw) == H and len(price_eur_kwh) == H, "Input array lengths must match horizon H"
        assert self.min_soc <= initial_soc <= self.max_soc, f"Initial SOC {initial_soc} violates bounds"

        n_vars = 5 * H + 1
        c = np.zeros(n_vars)

        # Indices offsets
        idx_c = 0
        idx_d = H
        idx_g = 2 * H
        idx_curt = 3 * H
        idx_e = 4 * H
        idx_peak = 5 * H

        # 1. Build Objective Vector c
        for t in range(H):
            c[idx_c + t] = self.delta * self.dt_hours
            c[idx_d + t] = self.delta * self.dt_hours
            c[idx_g + t] = self.alpha * price_eur_kwh[t] * self.dt_hours
            c[idx_curt + t] = self.gamma * self.dt_hours
        c[idx_peak] = self.beta

        # 2. Variable Bounds
        min_e = self.min_soc * self.capacity_kwh
        max_e = self.max_soc * self.capacity_kwh

        bounds: list[tuple[float | None, float | None]] = []
        for _ in range(H):
            bounds.append((0.0, self.max_charge_kw))  # P_c
        for _ in range(H):
            bounds.append((0.0, self.max_discharge_kw))  # P_d
        for _ in range(H):
            bounds.append((0.0, None))  # P_grid
        for _ in range(H):
            bounds.append((0.0, None))  # P_curt
        for _ in range(H):
            bounds.append((min_e, max_e))  # E_t
        bounds.append((0.0, None))  # P_grid_peak

        # 3. Equality Constraints (A_eq x = b_eq)
        # We have H node balance equations + H battery energy dynamics equations = 2H equations
        n_eq = 2 * H
        A_eq = np.zeros((n_eq, n_vars))
        b_eq = np.zeros(n_eq)

        # 3a. Node Balance: P_g[t] + P_d[t] - P_c[t] - P_curt[t] = P_load[t] - P_solar[t]
        for t in range(H):
            row = t
            A_eq[row, idx_g + t] = 1.0
            A_eq[row, idx_d + t] = 1.0
            A_eq[row, idx_c + t] = -1.0
            A_eq[row, idx_curt + t] = -1.0
            b_eq[row] = float(load_kw[t] - solar_kw[t])

        # 3b. Battery Energy Continuity
        # At t = 0: E_0 = initial_soc * E_cap
        row_e0 = H
        A_eq[row_e0, idx_e + 0] = 1.0
        b_eq[row_e0] = initial_soc * self.capacity_kwh

        # For t = 0 .. H-2: E_{t+1} - E_t - eta_c * dt * P_c[t] + (dt / eta_d) * P_d[t] = 0
        for t in range(H - 1):
            row = H + 1 + t
            A_eq[row, idx_e + t + 1] = 1.0
            A_eq[row, idx_e + t] = -1.0
            A_eq[row, idx_c + t] = -self.charge_efficiency * self.dt_hours
            A_eq[row, idx_d + t] = (1.0 / self.discharge_efficiency) * self.dt_hours
            b_eq[row] = 0.0

        # 4. Inequality Constraints (A_ub x <= b_ub)
        # Peak grid constraint: P_g[t] - P_grid_peak <= 0 (H constraints)
        A_ub = np.zeros((H, n_vars))
        b_ub = np.zeros(H)
        for t in range(H):
            A_ub[t, idx_g + t] = 1.0
            A_ub[t, idx_peak] = -1.0
            b_ub[t] = 0.0

        # 5. Solve via HiGHS
        res = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )

        if not res.success:
            logger.error("Linear programming solver failed: %s", res.message)
            return OptimizationResult(
                success=False,
                status_message=res.message,
                objective_value=float("inf"),
                charge_kw=np.zeros(H),
                discharge_kw=np.zeros(H),
                grid_import_kw=np.zeros(H),
                curtailment_kw=np.zeros(H),
                energy_kwh=np.zeros(H),
                soc=np.full(H, initial_soc),
                peak_grid_kw=0.0,
                max_balance_error_kw=float("inf"),
            )

        sol = res.x
        c_opt = sol[idx_c : idx_c + H]
        d_opt = sol[idx_d : idx_d + H]
        g_opt = sol[idx_g : idx_g + H]
        curt_opt = sol[idx_curt : idx_curt + H]
        e_opt = sol[idx_e : idx_e + H]
        peak_opt = float(sol[idx_peak])
        soc_opt = e_opt / self.capacity_kwh

        # Verify energy balance error
        reconstructed_load = solar_kw + g_opt + d_opt - c_opt - curt_opt
        balance_err = float(np.max(np.abs(load_kw - reconstructed_load)))

        return OptimizationResult(
            success=True,
            status_message="Optimal schedule found",
            objective_value=float(res.fun),
            charge_kw=c_opt,
            discharge_kw=d_opt,
            grid_import_kw=g_opt,
            curtailment_kw=curt_opt,
            energy_kwh=e_opt,
            soc=soc_opt,
            peak_grid_kw=peak_opt,
            max_balance_error_kw=balance_err,
        )
