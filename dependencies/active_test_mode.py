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
        power_balance = state.active_test_power_balance_cylinder_off
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
        new_value = _clamp_int(power_balance + direction, 0, 8)
        data_byte = 0x00 if new_value == 0 else (1 << (new_value - 1))
        ok = send_activation_command_fn(port_obj, 0x88, data_byte, demo_mode)
        if ok:
            with state.acquire_lock():
                state.active_test_power_balance_cylinder_off = new_value
            status = "Power balance normal" if new_value == 0 else f"Cylinder {new_value} OFF"

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

        if not editing:
            with state.acquire_lock():
                state.active_test_editing = True
                state.active_test_power_balance_cursor = state.active_test_power_balance_cylinder_off
            set_active_test_status(state, "Choose cylinder, Select to apply", duration_seconds=1.0)
            return

        with state.acquire_lock():
            selected = state.active_test_power_balance_cursor

        data_byte = 0x00 if selected == 0 else (1 << (selected - 1))
        ok = send_activation_command_fn(port_obj, 0x88, data_byte, demo_mode)
        if not ok:
            set_active_test_status(state, "ECU command failed")
            return

        with state.acquire_lock():
            state.active_test_power_balance_cylinder_off = selected
            if selected == 0:
                state.active_test_editing = False

        if selected == 0:
            set_active_test_status(state, "Power balance normal", duration_seconds=1.0)
        else:
            set_active_test_status(state, f"Cylinder {selected} OFF", duration_seconds=1.0)
        return

    with state.acquire_lock():
        state.active_test_editing = not state.active_test_editing
        editing = state.active_test_editing

    set_active_test_status(state, "Adjust with Up/Down" if editing else "Edit complete", duration_seconds=1.0)


def show_power_balance_menu_screen(gauge: Any, editing: bool, cursor_selection: int, selected_cylinder_off: int) -> None:
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
        is_off = selected_cylinder_off == value and value != 0

        if is_selected:
            draw.rectangle((4, y, width - 4, y + row_height - 2), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_selected else " "
        marker = "X" if is_off else " "
        line = f"{pointer} [{marker}] {label}"
        text_color = (255, 130, 130) if is_off else ((240, 240, 240) if is_selected else (165, 165, 165))
        draw.text((8, y + 2), line, font=body_font, fill=text_color)

    footer = "Select: Edit/Done  Up/Down: Choose" if editing else "Select to edit"
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
        editing = state.active_test_editing
        status_message = state.active_test_status_message
        status_until = state.active_test_status_until
        coolant_c = state.active_test_coolant_c
        fuel_inj_percent = state.active_test_fuel_injection_percent
        timing_offset = state.active_test_timing_offset_deg
        iaac_steps = state.active_test_iaac_offset_steps
        power_balance_cursor = state.active_test_power_balance_cursor
        power_balance = state.active_test_power_balance_cylinder_off
        fuel_pump_off = state.active_test_fuel_pump_off
        units_temp = state.units_temp

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

    mode_suffix = "[EDIT]" if editing else "[NAV]"
    title = f"AT {idx + 1}/{len(ACTIVE_TEST_ITEMS)} {mode_suffix}"
    item_name = ACTIVE_TEST_ITEMS[idx]

    if idx == ACTIVE_TEST_COOLANT:
        value_text = f"{_active_temp_display_value(coolant_c, units_temp, temp_unit_label)}{temp_unit_label(units_temp)}"
    elif idx == ACTIVE_TEST_FUEL_INJ:
        value_text = f"{fuel_inj_percent}%"
    elif idx == ACTIVE_TEST_TIMING:
        value_text = f"{timing_offset:+d}deg"
    elif idx == ACTIVE_TEST_IAAC:
        value_text = f"{iaac_steps * 0.5:+.1f}%"
    elif idx == ACTIVE_TEST_POWER_BALANCE:
        value_text = "Normal" if power_balance == 0 else f"Cyl {power_balance} OFF"
    elif idx == ACTIVE_TEST_FUEL_PUMP:
        value_text = "OFF" if fuel_pump_off else "ON"
    else:
        value_text = "Select to run"

    show_gauge(
        title,
        float(idx + 1),
        f"{item_name}: {value_text}",
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
        power_balance = state.active_test_power_balance_cylinder_off
        fuel_pump_off = state.active_test_fuel_pump_off
        units_temp = state.units_temp

    adjusted = list(values)

    if coolant_override_active:
        adjusted[4] = float(_active_temp_display_value(coolant_c, units_temp, temp_unit_label))

    adjusted[6] = float(max(0.0, min(100.0, adjusted[6] * (fuel_inj_percent / 100.0))))
    adjusted[7] = float(adjusted[7] + timing_offset)
    adjusted[3] = float(max(0.0, min(100.0, adjusted[3] + (iaac_steps * 0.5))))

    if power_balance > 0:
        adjusted[0] = float(max(600.0, adjusted[0] * 0.72))
        adjusted[2] = float(max(0.2, adjusted[2] * 0.65))

    if fuel_pump_off:
        adjusted[0] = float(max(0.0, adjusted[0] * 0.1))
        adjusted[1] = float(max(0.0, adjusted[1] * 0.2))
        adjusted[2] = 0.0
        adjusted[6] = 0.0

    return adjusted
