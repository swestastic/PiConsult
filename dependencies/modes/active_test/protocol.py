import time
from typing import Any, Callable, Optional

import serial
from dependencies.common.helpers import active_temp_display_value, clamp_int, int_to_u8

from .ui import (
    ACTIVE_TEST_CLEAR_SELF_LEARN,
    ACTIVE_TEST_COOLANT,
    ACTIVE_TEST_FUEL_INJ,
    ACTIVE_TEST_FUEL_PUMP,
    ACTIVE_TEST_IAAC,
    ACTIVE_TEST_POWER_BALANCE,
    ACTIVE_TEST_TIMING,
)

def set_active_test_status(state: Any, message: str, duration_seconds: float = 1.5) -> None:
    with state.acquire_lock():
        state.active_test_status_message = message
        state.active_test_status_until = time.monotonic() + duration_seconds


def adjust_active_test_value(
    direction: int,
    port_obj: Optional[serial.Serial],
    demo_mode: bool,
    state: Any,
    send_activation_command_fn: Callable[[Optional[serial.Serial], int, int, bool], bool],
    temp_unit_label: Callable[[object], str],
) -> None:
    with state.acquire_lock():
        idx = state.active_test_index
        coolant_c = state.active_test_coolant_c
        fuel_inj_percent = state.active_test_fuel_injection_percent
        timing_offset = state.active_test_timing_offset_deg
        iaac_steps = state.active_test_iaac_offset_steps
        fuel_pump_off = state.active_test_fuel_pump_off

    ok = False
    status = ""

    if idx == ACTIVE_TEST_COOLANT:
        new_value = clamp_int(coolant_c + direction, -20, 130)
        data_byte = clamp_int(new_value + 50, 0, 255)
        ok = send_activation_command_fn(port_obj, 0x80, data_byte, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_coolant_c = new_value
                state.active_test_coolant_override_active = True
                units_temp = state.units_temp
            status = f"Coolant set {active_temp_display_value(new_value, units_temp, temp_unit_label)}{temp_unit_label(units_temp)}"

    elif idx == ACTIVE_TEST_FUEL_INJ:
        new_value = clamp_int(fuel_inj_percent + direction, 70, 130)
        ok = send_activation_command_fn(port_obj, 0x81, new_value, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_fuel_injection_percent = new_value
            status = f"Fuel {new_value}%"

    elif idx == ACTIVE_TEST_TIMING:
        new_value = clamp_int(timing_offset + direction, -20, 20)
        ok = send_activation_command_fn(port_obj, 0x82, int_to_u8(new_value), demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_timing_offset_deg = new_value
            status = f"Timing {new_value:+d}deg"

    elif idx == ACTIVE_TEST_IAAC:
        new_value = clamp_int(iaac_steps + direction, -100, 100)
        ok = send_activation_command_fn(port_obj, 0x84, int_to_u8(new_value), demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_iaac_offset_steps = new_value
            status = f"IAAC {new_value * 0.5:+.1f}%"

    elif idx == ACTIVE_TEST_POWER_BALANCE:
        with state.acquire_lock():
            current = set(state.active_test_power_balance_cylinders_off)
        selected = clamp_int(getattr(state, "active_test_power_balance_cursor", 0) + direction, 0, 8)
        if selected == 0:
            new_selected = set()
        else:
            new_selected = set(current)
            if selected in new_selected:
                new_selected.remove(selected)
            else:
                new_selected.add(selected)

        data_byte = 0x00
        for cylinder in new_selected:
            data_byte |= (1 << (cylinder - 1))

        ok = send_activation_command_fn(port_obj, 0x88, data_byte, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_power_balance_cylinders_off = new_selected
            status = ""

    elif idx == ACTIVE_TEST_FUEL_PUMP:
        new_value = not fuel_pump_off
        data_byte = 0x01 if new_value else 0x00
        ok = send_activation_command_fn(port_obj, 0x89, data_byte, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_fuel_pump_off = new_value
            status = "Fuel pump OFF" if new_value else "Fuel pump ON"

    if not ok:
        status = "ECU command failed"

    set_active_test_status(state, status)


def run_active_test_action(
    port_obj: Optional[serial.Serial],
    demo_mode: bool,
    state: Any,
    send_activation_command_fn: Callable[[Optional[serial.Serial], int, int, bool], bool],
) -> None:
    with state.acquire_lock():
        idx = state.active_test_index

    if idx == ACTIVE_TEST_CLEAR_SELF_LEARN:
        ok = send_activation_command_fn(port_obj, 0x8B, 0x00, demo_mode)
        set_active_test_status(state, "Self learn cleared" if ok else "ECU command failed")
        return

    if idx == ACTIVE_TEST_POWER_BALANCE:
        with state.acquire_lock():
            editing = state.active_test_editing
            cursor = state.active_test_power_balance_cursor
            selected_cylinders_off = set(state.active_test_power_balance_cylinders_off)

        if not editing:
            with state.acquire_lock():
                state.active_test_editing = True
                state.active_test_power_balance_cursor = min(selected_cylinders_off) if selected_cylinders_off else 0
            set_active_test_status(state, "")
            return

        if cursor == 0:
            with state.acquire_lock():
                state.active_test_in_test = False
                state.active_test_editing = False
            set_active_test_status(state, "")
            return

        new_selected = set(selected_cylinders_off)
        if cursor in new_selected:
            new_selected.remove(cursor)
        else:
            new_selected.add(cursor)

        data_byte = 0x00
        for cylinder in new_selected:
            data_byte |= (1 << (cylinder - 1))

        ok = send_activation_command_fn(port_obj, 0x88, data_byte, demo_mode)
        if not ok:
            set_active_test_status(state, "ECU command failed")
            return

        with state.acquire_lock():
            state.active_test_power_balance_cylinders_off = new_selected

        set_active_test_status(state, "")
        return

    with state.acquire_lock():
        state.active_test_editing = not state.active_test_editing
        editing = state.active_test_editing

    set_active_test_status(state, "Adjust with Up/Down" if editing else "Edit complete", duration_seconds=1.0)


def apply_active_test_effects_to_demo_values(
    values: list[float],
    state: Any,
    temp_unit_label: Callable[[object], str],
) -> list[float]:
    with state.acquire_lock():
        coolant_c = state.active_test_coolant_c
        coolant_override_active = state.active_test_coolant_override_active
        fuel_inj_percent = state.active_test_fuel_injection_percent
        timing_offset = state.active_test_timing_offset_deg
        iaac_steps = state.active_test_iaac_offset_steps
        power_balance = set(state.active_test_power_balance_cylinders_off)
        fuel_pump_off = state.active_test_fuel_pump_off
        units_temp = state.units_temp

    adjusted = list(values)

    if coolant_override_active:
        adjusted[4] = float(active_temp_display_value(coolant_c, units_temp, temp_unit_label))

    adjusted[6] = float(max(0.0, min(100.0, adjusted[6] * (fuel_inj_percent / 100.0))))
    adjusted[7] = float(adjusted[7] + timing_offset)
    adjusted[3] = float(max(0.0, min(100.0, adjusted[3] + (iaac_steps * 0.5))))

    if power_balance:
        balance_count = len(power_balance)
        rpm_factor = max(0.35, 0.72 - (0.05 * max(0, balance_count - 1)))
        maf_factor = max(0.25, 0.65 - (0.04 * max(0, balance_count - 1)))
        adjusted[0] = float(max(600.0, adjusted[0] * rpm_factor))
        adjusted[2] = float(max(0.2, adjusted[2] * maf_factor))

    if fuel_pump_off:
        adjusted[0] = float(max(0.0, adjusted[0] * 0.1))
        adjusted[1] = float(max(0.0, adjusted[1] * 0.2))
        adjusted[2] = 0.0
        adjusted[6] = 0.0

    return adjusted
