import time
from typing import Any, Callable, Optional

import serial
from PIL import Image, ImageDraw, ImageFont

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


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _int_to_u8(value: int) -> int:
    return int(value) & 0xFF


def _active_temp_display_value(coolant_c: int, units_temp: object, temp_unit_label: Callable[[object], str]) -> int:
    if temp_unit_label(units_temp) == "F":
        return int(round((coolant_c * 9.0 / 5.0) + 32.0))
    return int(coolant_c)


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
        new_value = _clamp_int(coolant_c + direction, -20, 130)
        data_byte = _clamp_int(new_value + 50, 0, 255)
        ok = send_activation_command_fn(port_obj, 0x80, data_byte, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_coolant_c = new_value
                state.active_test_coolant_override_active = True
                units_temp = state.units_temp
            status = f"Coolant set {_active_temp_display_value(new_value, units_temp, temp_unit_label)}{temp_unit_label(units_temp)}"

    elif idx == ACTIVE_TEST_FUEL_INJ:
        new_value = _clamp_int(fuel_inj_percent + direction, 70, 130)
        ok = send_activation_command_fn(port_obj, 0x81, new_value, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_fuel_injection_percent = new_value
            status = f"Fuel {new_value}%"

    elif idx == ACTIVE_TEST_TIMING:
        new_value = _clamp_int(timing_offset + direction, -20, 20)
        ok = send_activation_command_fn(port_obj, 0x82, _int_to_u8(new_value), demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_timing_offset_deg = new_value
            status = f"Timing {new_value:+d}deg"

    elif idx == ACTIVE_TEST_IAAC:
        new_value = _clamp_int(iaac_steps + direction, -100, 100)
        ok = send_activation_command_fn(port_obj, 0x84, _int_to_u8(new_value), demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_iaac_offset_steps = new_value
            status = f"IAAC {new_value * 0.5:+.1f}%"

    elif idx == ACTIVE_TEST_POWER_BALANCE:
        with state.acquire_lock():
            current = set(state.active_test_power_balance_cylinders_off)
        selected = _clamp_int(getattr(state, "active_test_power_balance_cursor", 0) + direction, 0, 8)
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


def show_power_balance_menu_screen(gauge: Any, editing: bool, cursor_selection: int, selected_cylinders_off: set[int]) -> None:
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title = "Power Balance [EDIT]" if editing else "Power Balance [NAV]"
    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    body_font = ImageFont.load_default()
    rows = [("Exit", 0)] + [(f"Cylinder {idx}", idx) for idx in range(1, 9)]
    start_y = 36
    bottom_margin = 18
    row_height = max(13, (height - start_y - bottom_margin) // len(rows))

    for row_index, (label, value) in enumerate(rows):
        y = start_y + (row_index * row_height)
        is_selected = value == cursor_selection
        is_off = value in selected_cylinders_off and value != 0

        if is_selected:
            draw.rectangle((4, y, width - 4, y + row_height - 2), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_selected else " "
        marker = "X" if is_off else " "
        line = f"{pointer} [{marker}] {label}"
        text_color = (255, 130, 130) if is_off else ((240, 240, 240) if is_selected else (165, 165, 165))
        draw.text((8, y + 2), line, font=body_font, fill=text_color)

    footer = "Select: Toggle/Exit  Up/Down: Choose" if editing else "Select to edit"
    draw.text((8, height - 14), footer, font=body_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


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
        return f"{_active_temp_display_value(coolant_c, units_temp, temp_unit_label)}{temp_unit_label(units_temp)}"
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


def show_active_test_list_screen(
    state: Any,
    gauge: Any,
    selected_index: int,
    temp_unit_label: Callable[[object], str],
) -> None:
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title = "Active Tests"
    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    body_font = ImageFont.load_default()
    start_y = 36
    bottom_margin = 18
    row_height = max(13, (height - start_y - bottom_margin) // len(ACTIVE_TEST_ITEMS))

    with state.acquire_lock():
        editing = state.active_test_editing

    for row_index, label in enumerate(ACTIVE_TEST_ITEMS):
        y = start_y + (row_index * row_height)
        is_selected = row_index == selected_index
        is_editable = row_index in {
            ACTIVE_TEST_COOLANT,
            ACTIVE_TEST_FUEL_INJ,
            ACTIVE_TEST_TIMING,
            ACTIVE_TEST_IAAC,
            ACTIVE_TEST_FUEL_PUMP,
        }

        if is_selected:
            draw.rectangle((4, y, width - 4, y + row_height - 2), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_selected else " "
        value_text = _active_test_value_text(state, row_index, temp_unit_label)
        edit_tag = " [EDIT]" if (is_selected and editing and is_editable) else ""
        line = f"{pointer} {label}: {value_text}{edit_tag}"
        text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        draw.text((8, y + 2), line, font=body_font, fill=text_color)

    footer = "Up/Down: Adjust  Select: Save" if editing else "Up/Down: Navigate  Select: Edit"
    draw.text((8, height - 14), footer, font=body_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


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
        adjusted[4] = float(_active_temp_display_value(coolant_c, units_temp, temp_unit_label))

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
