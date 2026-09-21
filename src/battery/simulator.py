"""Standalone physically constrained Battery Energy Storage System (BESS) simulator."""

from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger("battery.simulator")


@dataclass
class BatteryStepResult:
    """Output data for a single battery simulation step."""

    actual_charge_kw: float
    actual_discharge_kw: float
    prev_soc: float
    new_soc: float
    stored_energy_kwh: float
    energy_loss_kwh: float


@dataclass
class NodeBalanceResult:
    """Complete energy balance result for a grid node timestep."""

    load_kw: float
    solar_kw: float
    actual_charge_kw: float
    actual_discharge_kw: float
    grid_import_kw: float
    curtailment_kw: float
    soc: float
    balance_error_kw: float


class BatterySimulator:
    """Stateful, deterministic, physically constrained battery energy storage model.
    
    Governing Equations:
    For charging (P_c >= 0):
        SOC(t + 1) = SOC(t) + (eta_c * P_c * dt) / E_cap
    For discharging (P_d >= 0):
        SOC(t + 1) = SOC(t) - (P_d * dt) / (eta_d * E_cap)
    Subject to:
        0 <= P_c <= max_charge_kw
        0 <= P_d <= max_discharge_kw
        min_soc <= SOC <= max_soc
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
        initial_soc: float = 0.50,
    ):
        assert capacity_kwh > 0, "Capacity must be strictly positive"
        assert max_charge_kw > 0 and max_discharge_kw > 0, "Power limits must be positive"
        assert 0.0 <= min_soc < max_soc <= 1.0, "SOC limits must satisfy 0 <= min_soc < max_soc <= 1"
        assert 0.0 < charge_efficiency <= 1.0 and 0.0 < discharge_efficiency <= 1.0, "Efficiencies must be in (0, 1]"
        assert min_soc <= initial_soc <= max_soc, "Initial SOC must be within [min_soc, max_soc]"

        self.capacity_kwh = float(capacity_kwh)
        self.max_charge_kw = float(max_charge_kw)
        self.max_discharge_kw = float(max_discharge_kw)
        self.min_soc = float(min_soc)
        self.max_soc = float(max_soc)
        self.charge_efficiency = float(charge_efficiency)
        self.discharge_efficiency = float(discharge_efficiency)
        self.initial_soc = float(initial_soc)

        self.soc = float(initial_soc)

    def reset(self, soc: float | None = None) -> None:
        """Reset the battery state of charge."""
        target_soc = self.initial_soc if soc is None else soc
        assert self.min_soc <= target_soc <= self.max_soc, f"Reset SOC {target_soc} violates bounds"
        self.soc = float(target_soc)

    def step(
        self,
        charge_cmd_kw: float,
        discharge_cmd_kw: float,
        dt_hours: float = 1.0,
    ) -> BatteryStepResult:
        """Advance battery state by one timestep, strictly enforcing all physical constraints."""
        prev_soc = self.soc

        # 1. Non-negativity and mutual exclusivity check
        c_cmd = max(0.0, float(charge_cmd_kw))
        d_cmd = max(0.0, float(discharge_cmd_kw))

        if c_cmd > 0.0 and d_cmd > 0.0:
            # Net commanded power to avoid simultaneous charge and discharge
            if c_cmd >= d_cmd:
                c_cmd -= d_cmd
                d_cmd = 0.0
            else:
                d_cmd -= c_cmd
                c_cmd = 0.0

        # 2. Enforce inverter power ratings
        c_power = min(c_cmd, self.max_charge_kw)
        d_power = min(d_cmd, self.max_discharge_kw)

        # 3. Enforce State of Charge energy boundaries
        if c_power > 0.0:
            energy_room_kwh = (self.max_soc - self.soc) * self.capacity_kwh
            max_c_power_energy = energy_room_kwh / (self.charge_efficiency * dt_hours)
            c_actual = min(c_power, max(0.0, max_c_power_energy))
            d_actual = 0.0

            delta_soc = (c_actual * dt_hours * self.charge_efficiency) / self.capacity_kwh
            new_soc = min(self.max_soc, self.soc + delta_soc)
            loss_kwh = c_actual * dt_hours * (1.0 - self.charge_efficiency)
        elif d_power > 0.0:
            energy_avail_kwh = (self.soc - self.min_soc) * self.capacity_kwh
            max_d_power_energy = (energy_avail_kwh * self.discharge_efficiency) / dt_hours
            d_actual = min(d_power, max(0.0, max_d_power_energy))
            c_actual = 0.0

            delta_soc = (d_actual * dt_hours) / (self.discharge_efficiency * self.capacity_kwh)
            new_soc = max(self.min_soc, self.soc - delta_soc)
            loss_kwh = (d_actual * dt_hours / self.discharge_efficiency) * (1.0 - self.discharge_efficiency)
        else:
            c_actual = 0.0
            d_actual = 0.0
            new_soc = self.soc
            loss_kwh = 0.0

        # Strict SOC bounds assertion
        if new_soc < self.min_soc - 1e-6 or new_soc > self.max_soc + 1e-6:
            raise ValueError(f"SOC boundary violation: {new_soc:.6f} not in [{self.min_soc}, {self.max_soc}]")

        self.soc = float(max(self.min_soc, min(self.max_soc, new_soc)))
        stored_energy = self.soc * self.capacity_kwh

        return BatteryStepResult(
            actual_charge_kw=c_actual,
            actual_discharge_kw=d_actual,
            prev_soc=prev_soc,
            new_soc=self.soc,
            stored_energy_kwh=stored_energy,
            energy_loss_kwh=loss_kwh,
        )

    def simulate_node_step(
        self,
        load_kw: float,
        solar_kw: float,
        charge_cmd_kw: float,
        discharge_cmd_kw: float,
        dt_hours: float = 1.0,
    ) -> NodeBalanceResult:
        """Simulate a single timestep at the grid node and verify energy conservation.
        
        Conservation Identity:
            P_load = P_solar + P_grid + P_discharge - P_charge - P_curtailment
        """
        b_res = self.step(charge_cmd_kw, discharge_cmd_kw, dt_hours=dt_hours)

        p_load = float(load_kw)
        p_solar = float(solar_kw)
        p_c = b_res.actual_charge_kw
        p_d = b_res.actual_discharge_kw

        # Net balance to be resolved by grid import or curtailment
        net_required = p_load + p_c - p_solar - p_d

        if net_required >= 0.0:
            p_grid = net_required
            p_curt = 0.0
        else:
            p_grid = 0.0
            p_curt = -net_required

        # Validate exact balance equation
        balanced_load = p_solar + p_grid + p_d - p_c - p_curt
        err = abs(p_load - balanced_load)
        if err > 1e-5:
            raise ValueError(f"Node energy balance violated! Error: {err:.6e} kW")

        return NodeBalanceResult(
            load_kw=p_load,
            solar_kw=p_solar,
            actual_charge_kw=p_c,
            actual_discharge_kw=p_d,
            grid_import_kw=p_grid,
            curtailment_kw=p_curt,
            soc=b_res.new_soc,
            balance_error_kw=err,
        )
