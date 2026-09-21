"""Unit tests for standalone Battery Energy Storage System (BESS) simulator."""

import pytest

from src.battery.simulator import BatterySimulator


def test_battery_initialization_and_bounds():
    """Verify initialization checks and state boundaries."""
    bess = BatterySimulator(
        capacity_kwh=1000.0,
        max_charge_kw=250.0,
        max_discharge_kw=250.0,
        min_soc=0.20,
        max_soc=0.80,
        initial_soc=0.50,
    )
    assert bess.soc == 0.50

    # Invalid initial SOC
    with pytest.raises(AssertionError):
        BatterySimulator(min_soc=0.20, max_soc=0.80, initial_soc=0.10)

    # Invalid efficiency
    with pytest.raises(AssertionError):
        BatterySimulator(charge_efficiency=0.0)


def test_empty_battery_cannot_discharge():
    """When battery is at min_soc, discharge power must be clamped to 0.0 kW."""
    bess = BatterySimulator(
        capacity_kwh=1000.0,
        min_soc=0.20,
        max_soc=0.80,
        initial_soc=0.20,
    )
    res = bess.step(charge_cmd_kw=0.0, discharge_cmd_kw=200.0)
    assert res.actual_discharge_kw == 0.0
    assert res.new_soc == 0.20


def test_full_battery_cannot_charge():
    """When battery is at max_soc, charge power must be clamped to 0.0 kW."""
    bess = BatterySimulator(
        capacity_kwh=1000.0,
        min_soc=0.20,
        max_soc=0.80,
        initial_soc=0.80,
    )
    res = bess.step(charge_cmd_kw=200.0, discharge_cmd_kw=0.0)
    assert res.actual_charge_kw == 0.0
    assert res.new_soc == 0.80


def test_max_power_ratings():
    """Verify inverter power clipping."""
    bess = BatterySimulator(
        capacity_kwh=10000.0,
        max_charge_kw=250.0,
        max_discharge_kw=250.0,
        min_soc=0.10,
        max_soc=0.90,
        initial_soc=0.50,
    )
    res_c = bess.step(charge_cmd_kw=9999.0, discharge_cmd_kw=0.0)
    assert res_c.actual_charge_kw == 250.0

    res_d = bess.step(charge_cmd_kw=0.0, discharge_cmd_kw=9999.0)
    assert res_d.actual_discharge_kw == 250.0


def test_efficiency_and_round_trip():
    """Verify energy accounting with 90% charge and 90% discharge efficiency."""
    capacity = 1000.0
    eta_c = 0.90
    eta_d = 0.90
    bess = BatterySimulator(
        capacity_kwh=capacity,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        charge_efficiency=eta_c,
        discharge_efficiency=eta_d,
        initial_soc=0.50,
    )

    # 1. Charge 100 kW for 1 hour: absorbed power = 100 kW, energy into battery = 100 * 0.9 = 90 kWh
    step_c = bess.step(charge_cmd_kw=100.0, discharge_cmd_kw=0.0, dt_hours=1.0)
    expected_delta_soc = 90.0 / capacity  # 0.09
    assert pytest.approx(step_c.new_soc) == 0.50 + expected_delta_soc
    assert pytest.approx(step_c.energy_loss_kwh) == 10.0

    # 2. Discharge until previous SOC: need 90 kWh from battery storage -> output = 90 * eta_d = 81 kW
    step_d = bess.step(charge_cmd_kw=0.0, discharge_cmd_kw=81.0, dt_hours=1.0)
    assert pytest.approx(step_d.new_soc) == 0.50
    # Round-trip efficiency check: input 100 kWh -> output 81 kWh -> 81% round trip (0.9 * 0.9)
    assert pytest.approx(step_d.actual_discharge_kw / step_c.actual_charge_kw) == eta_c * eta_d


def test_simultaneous_charge_discharge_netting():
    """Simultaneous commands must be cleanly netted without violation."""
    bess = BatterySimulator(
        capacity_kwh=1000.0,
        min_soc=0.10,
        max_soc=0.90,
        initial_soc=0.50,
    )
    # Net: 300 charge - 100 discharge = 200 charge
    res = bess.step(charge_cmd_kw=300.0, discharge_cmd_kw=100.0)
    assert res.actual_discharge_kw == 0.0
    assert res.actual_charge_kw > 0.0


def test_node_energy_balance_invariant():
    """Verify node energy balance across various combinations of load and solar."""
    bess = BatterySimulator(
        capacity_kwh=2000.0,
        max_charge_kw=500.0,
        max_discharge_kw=500.0,
        min_soc=0.10,
        max_soc=0.90,
        initial_soc=0.50,
    )

    scenarios = [
        # (load, solar, c_cmd, d_cmd)
        (100.0, 500.0, 400.0, 0.0),   # Solar surplus with full charge
        (500.0, 100.0, 0.0, 300.0),   # Solar deficit with discharge
        (200.0, 800.0, 100.0, 0.0),   # Solar surplus exceeding max charge -> curtailment
        (800.0, 0.0, 0.0, 1000.0),    # Heavy deficit exceeding max discharge -> grid import
        (0.0, 0.0, 0.0, 0.0),         # Idle
    ]

    for load, solar, c_cmd, d_cmd in scenarios:
        res = bess.simulate_node_step(
            load_kw=load,
            solar_kw=solar,
            charge_cmd_kw=c_cmd,
            discharge_cmd_kw=d_cmd,
        )
        assert res.balance_error_kw < 1e-6
        # Node balance identity: load = solar + grid + discharge - charge - curtailment
        reconstructed_load = (
            res.solar_kw + res.grid_import_kw + res.actual_discharge_kw - res.actual_charge_kw - res.curtailment_kw
        )
        assert pytest.approx(res.load_kw) == reconstructed_load
