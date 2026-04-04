from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DIGITAL_REGISTER_ORDER = [0x13, 0x1E, 0x1F, 0x21]
DIGITAL_BIT_NAME_MAP: dict[int, dict[int, str]] = {
    0x13: {
        0: "Start Signal",
        1: "Closed Throttle",
        2: "Coolant Fan Hi",
        3: "Coolant Fan Lo",
        4: "EGR Solenoid",
    },
    0x1E: {
        7: "A/C On Switch",
        6: "Aircon Relay",
    },
    0x1F: {
        7: "LH Bank Lean",
        6: "Fuel Pump Relay",
        5: "VTC Solenoid",
        4: "P/Reg Control",
        3: "Wastegate Sol",
        2: "RH Bank Lean",
    },
    0x21: {
        7: "Power Steering",
        6: "IACV/FICD Sol",
        5: "Park/Neutral",
    },
}


def _bit_is_set(value: int, bit_index: int) -> bool:
    return bool(value & (1 << bit_index))


def _digital_bit_name(register: int, bit_index: int) -> str:
    return DIGITAL_BIT_NAME_MAP.get(register, {}).get(bit_index, f"Bit {bit_index}")


def _truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


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

    if np.sin(elapsed_seconds * 1.4) > 0.75:
        reg13 |= (1 << 0)
    if np.sin(elapsed_seconds * 0.9) < -0.35:
        reg13 |= (1 << 1)
    if np.sin(elapsed_seconds * 0.4) > 0.15:
        reg13 |= (1 << 2)
    if np.sin(elapsed_seconds * 0.35 + 0.8) > 0.35:
        reg13 |= (1 << 3)
    if np.sin(elapsed_seconds * 0.55) > 0.55:
        reg13 |= (1 << 4)

    if np.sin(elapsed_seconds * 0.3 + 1.2) > 0.0:
        reg1e |= (1 << 7)
    if np.sin(elapsed_seconds * 0.3 + 0.4) > 0.1:
        reg1e |= (1 << 6)

    if np.sin(elapsed_seconds * 0.6) > 0.25:
        reg1f |= (1 << 7)
    if fuel_pump_off:
        reg1f |= (1 << 6)
    if np.sin(elapsed_seconds * 0.85 + 0.2) > 0.3:
        reg1f |= (1 << 5)
    if np.sin(elapsed_seconds * 0.75 + 1.0) > 0.45:
        reg1f |= (1 << 4)
    if np.sin(elapsed_seconds * 1.05 + 2.1) > 0.6:
        reg1f |= (1 << 3)
    if np.sin(elapsed_seconds * 0.7 + 2.5) < -0.4:
        reg1f |= (1 << 2)

    if np.sin(elapsed_seconds * 0.8 + 1.6) > 0.35:
        reg21 |= (1 << 7)
    if np.sin(elapsed_seconds * 1.1 + 0.3) > 0.55:
        reg21 |= (1 << 6)
    if not power_balance:
        reg21 |= (1 << 5)

    update_digital_register_values(state, reg13, reg1e, reg1f, reg21)


def update_digital_registers_from_reader(state: Any, reader: Any, parse_int_fn: Any) -> None:
    reg13 = parse_int_fn(getattr(reader, "DIGITAL_13", 0), 0)
    reg1e = parse_int_fn(getattr(reader, "DIGITAL_1E", 0), 0)
    reg1f = parse_int_fn(getattr(reader, "DIGITAL_1F", 0), 0)
    reg21 = parse_int_fn(getattr(reader, "DIGITAL_21", 0), 0)
    update_digital_register_values(state, reg13, reg1e, reg1f, reg21)


def show_digital_bits_screen(state: Any, gauge: Any) -> None:
    with state.acquire_lock():
        page_index = state.digital_page_index % len(DIGITAL_REGISTER_ORDER)
        register_values = dict(state.digital_register_values)

    register = DIGITAL_REGISTER_ORDER[page_index]
    register_value = register_values.get(register, 0)

    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_font = gauge.label_font
    body_font = ImageFont.load_default()

    title = f"Digital 0x{register:02X} {page_index + 1}/4"
    title_width, _ = gauge._text_size(draw, title, title_font)
    title_x = (width - title_width) // 2
    draw.text((title_x, 6), title, font=title_font, fill=(255, 255, 255))

    top_y = 42
    bottom_margin = 8
    col_gap = 8
    col_width = (width - col_gap - 12) // 2
    row_height = max(18, (height - top_y - bottom_margin) // 4)
    left_x = 4
    right_x = left_x + col_width + col_gap

    display_bits = [7, 6, 5, 4, 3, 2, 1, 0]
    for idx, bit_index in enumerate(display_bits):
        column = 0 if idx < 4 else 1
        row = idx if idx < 4 else idx - 4
        x = left_x if column == 0 else right_x
        y = top_y + (row * row_height)
        is_on = _bit_is_set(register_value, bit_index)

        bg_color = (30, 90, 30) if is_on else (20, 20, 20)
        border_color = (100, 220, 100) if is_on else (70, 70, 70)
        text_color = (230, 255, 230) if is_on else (170, 170, 170)

        draw.rectangle((x, y, x + col_width, y + row_height - 3), fill=bg_color, outline=border_color)

        label = _truncate_text(_digital_bit_name(register, bit_index), 16)
        state_text = "ON" if is_on else "off"
        line = f"{label} {state_text}"
        draw.text((x + 4, y + 4), line, font=body_font, fill=text_color)

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)
