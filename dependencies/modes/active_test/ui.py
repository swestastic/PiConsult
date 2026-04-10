import time
from typing import Any, Callable

from dependencies.common.ui import clamp_int, draw_scrollable_menu_screen
from dependencies.common.helpers import active_temp_display_value

ACTIVE_TEST_ITEMS = [
    "Coolant Temp",
    "Fuel Injection",
    "Static Timing",
    "IAAC Opening",
    "Power Balance",
    "Fuel Pump Relay",
    "Clear Self Learn",
]

ACTIVE_TEST_COOLANT = 0
ACTIVE_TEST_FUEL_INJ = 1
ACTIVE_TEST_TIMING = 2
ACTIVE_TEST_IAAC = 3
ACTIVE_TEST_POWER_BALANCE = 4
ACTIVE_TEST_FUEL_PUMP = 5
ACTIVE_TEST_CLEAR_SELF_LEARN = 6


def _active_test_value_text(
    state: Any,
    idx: int,
    temp_unit_label: Callable[[object], str],
) -> str:
    with state.acquire_lock():
        coolant_c = state.active_test_coolant_c
        fuel_inj_percent = state.active_test_fuel_injection_percent
        timing_offset = state.active_test_timing_offset_deg
        iaac_steps = state.active_test_iaac_offset_steps
        power_balance = set(state.active_test_power_balance_cylinders_off)
        fuel_pump_off = state.active_test_fuel_pump_off
        units_temp = state.units_temp

    if idx == ACTIVE_TEST_COOLANT:
        return f"{active_temp_display_value(coolant_c, units_temp, temp_unit_label)}{temp_unit_label(units_temp)}"
    if idx == ACTIVE_TEST_FUEL_INJ:
        return f"{fuel_inj_percent}%"
    if idx == ACTIVE_TEST_TIMING:
        return f"{timing_offset:+d}deg"
    if idx == ACTIVE_TEST_IAAC:
        return f"{iaac_steps * 0.5:+.1f}%"
    if idx == ACTIVE_TEST_POWER_BALANCE:
        if not power_balance:
            return "Normal"
        cylinders = ", ".join(str(cylinder) for cylinder in sorted(power_balance))
        return f"Cyl {cylinders} OFF"
    if idx == ACTIVE_TEST_FUEL_PUMP:
        return "OFF" if fuel_pump_off else "ON"
    return "Select to run"


def show_power_balance_menu_screen(gauge: Any, editing: bool, cursor_selection: int, selected_cylinders_off: set[int]) -> None:
    title = "Power Balance [EDIT]" if editing else "Power Balance [NAV]"
    rows = [("Exit", 0)] + [(f"Cylinder {idx}", idx) for idx in range(1, 9)]
    selected_index = clamp_int(cursor_selection, 0, max(len(rows) - 1, 0))

    def _line_builder(item: tuple[str, int], _row_index: int, is_selected: bool) -> tuple[str, tuple[int, int, int]]:
        label, value = item
        is_off = value in selected_cylinders_off and value != 0
        pointer = ">" if is_selected else " "
        marker = "X" if is_off else " "
        line = f"{pointer} [{marker}] {label}"
        text_color = (255, 130, 130) if is_off else ((240, 240, 240) if is_selected else (165, 165, 165))
        return line, text_color

    footer = "Select: Toggle/Exit  Up/Down: Choose" if editing else "Select to edit"
    draw_scrollable_menu_screen(gauge, title, rows, selected_index, _line_builder, footer)


def show_active_test_list_screen(
    state: Any,
    gauge: Any,
    selected_index: int,
    temp_unit_label: Callable[[object], str],
) -> None:
    with state.acquire_lock():
        editing = state.active_test_editing

    def _line_builder(label: str, row_index: int, is_selected: bool) -> tuple[str, tuple[int, int, int]]:
        is_editable = row_index in {
            ACTIVE_TEST_COOLANT,
            ACTIVE_TEST_FUEL_INJ,
            ACTIVE_TEST_TIMING,
            ACTIVE_TEST_IAAC,
            ACTIVE_TEST_FUEL_PUMP,
        }
        pointer = ">" if is_selected else " "
        value_text = _active_test_value_text(state, row_index, temp_unit_label)
        edit_tag = " [EDIT]" if (is_selected and editing and is_editable) else ""
        line = f"{pointer} {label}: {value_text}{edit_tag}"
        text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        return line, text_color

    footer = "Up/Down: Adjust  Select: Save" if editing else "Up/Down: Navigate  Select: Edit"
    draw_scrollable_menu_screen(gauge, "Active Tests", ACTIVE_TEST_ITEMS, selected_index, _line_builder, footer)


def show_active_test_screen(
    state: Any,
    gauge: Any,
    show_gauge: Callable[..., None],
    temp_unit_label: Callable[[object], str],
) -> None:
    with state.acquire_lock():
        idx = state.active_test_index
        in_test = state.active_test_in_test
        editing = state.active_test_editing
        status_message = state.active_test_status_message
        status_until = state.active_test_status_until
        power_balance_cursor = state.active_test_power_balance_cursor
        power_balance = set(state.active_test_power_balance_cylinders_off)

    if not in_test:
        show_active_test_list_screen(state, gauge, idx, temp_unit_label)
        return

    if status_message and time.monotonic() < status_until:
        show_gauge(
            "Active Test",
            0.0,
            status_message,
            0.0,
            1.0,
            show_needle=False,
            show_dial=False,
            show_value_text=False,
        )
        return

    if idx == ACTIVE_TEST_POWER_BALANCE:
        show_power_balance_menu_screen(gauge, editing, power_balance_cursor, power_balance)
        return

    show_gauge(
        "Active Test",
        float(idx + 1),
        _active_test_value_text(state, idx, temp_unit_label),
        1.0,
        float(len(ACTIVE_TEST_ITEMS)),
        show_needle=False,
        show_dial=False,
        show_value_text=False,
    )
