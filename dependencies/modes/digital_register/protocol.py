from typing import Any

import numpy as np


def update_digital_register_values(
    state: Any,
    register_13: int,
    register_1e: int,
    register_1f: int,
    register_21: int,
) -> None:
    with state.acquire_lock():
        state.digital_register_values[0x13] = register_13 & 0xFF
        state.digital_register_values[0x1E] = register_1e & 0xFF
        state.digital_register_values[0x1F] = register_1f & 0xFF
        state.digital_register_values[0x21] = register_21 & 0xFF


def update_digital_registers_from_demo(state: Any, elapsed_seconds: float) -> None:
    with state.acquire_lock():
        power_balance = set(state.active_test_power_balance_cylinders_off)
        fuel_pump_off = state.active_test_fuel_pump_off

    reg13 = 0
    reg1e = 0
    reg1f = 0
    reg21 = 0

    if np.sin(elapsed_seconds * 0.55) > 0.55:
        reg13 |= (1 << 4)
    if np.sin(elapsed_seconds * 0.8 + 1.6) > 0.35:
        reg13 |= (1 << 3)
    if not power_balance:
        reg13 |= (1 << 2)
    if np.sin(elapsed_seconds * 1.4) > 0.75:
        reg13 |= (1 << 1)
    if np.sin(elapsed_seconds * 0.9) < -0.35:
        reg13 |= (1 << 0)

    if np.sin(elapsed_seconds * 0.3 + 0.4) > 0.1:
        reg1e |= (1 << 7)
    if fuel_pump_off:
        reg1e |= (1 << 6)
    if np.sin(elapsed_seconds * 0.85 + 0.2) > 0.3:
        reg1e |= (1 << 5)
    if np.sin(elapsed_seconds * 0.4) > 0.15:
        reg1e |= (1 << 1)
    if np.sin(elapsed_seconds * 0.35 + 0.8) > 0.35:
        reg1e |= (1 << 0)

    if np.sin(elapsed_seconds * 0.75 + 1.0) > 0.45:
        reg1f |= (1 << 6)
    if np.sin(elapsed_seconds * 1.05 + 2.1) > 0.6:
        reg1f |= (1 << 5)
        reg1f |= (1 << 3)
    if np.sin(elapsed_seconds * 0.55) > 0.15:
        reg1f |= (1 << 0)

    if np.sin(elapsed_seconds * 0.6) > 0.25:
        reg21 |= (1 << 7)
    if np.sin(elapsed_seconds * 0.7 + 2.5) < -0.4:
        reg21 |= (1 << 6)

    update_digital_register_values(state, reg13, reg1e, reg1f, reg21)


def update_digital_registers_from_reader(state: Any, reader: Any, parse_int_fn: Any) -> None:
    reg13 = parse_int_fn(getattr(reader, "DIGITAL_13", 0), 0)
    reg1e = parse_int_fn(getattr(reader, "DIGITAL_1E", 0), 0)
    reg1f = parse_int_fn(getattr(reader, "DIGITAL_1F", 0), 0)
    reg21 = parse_int_fn(getattr(reader, "DIGITAL_21", 0), 0)
    update_digital_register_values(state, reg13, reg1e, reg1f, reg21)
