from typing import Any

from PIL import Image, ImageDraw, ImageFont

DIGITAL_BIT_NAME_MAP: dict[int, dict[int, str]] = {
    0x13: {
        4: "A/C On Switch",
        3: "Power Steering Switch",
        2: "Park/Neutral Switch",
        1: "Start Signal",
        0: "TPS Closed",
    },
    0x1E: {
        7: "Aircon Relay",
        6: "Fuel Pump Relay",
        5: "VTC Solenoid",
        1: "Coolant Fan Hi",
        0: "Coolant Fan Lo",
    },
    0x1F: {
        6: "P/Reg Control Valve",
        5: "Wastegate Sol",
        3: "IACV/FICD Sol",
        0: "EGR Solenoid",
    },
    0x21: {
        7: "LH-BANK Lean",
        6: "RH-BANK Lean",
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


def show_digital_bits_screen(state: Any, gauge: Any, selected_registers: list[int]) -> None:
    with state.acquire_lock():
        register_values = dict(state.digital_register_values)

    if not selected_registers:
        width = gauge.disp.height
        height = gauge.disp.width
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        title_font = gauge.label_font
        body_font = ImageFont.load_default()

        title = "Digital Registers"
        title_width, _ = gauge._text_size(draw, title, title_font)
        draw.text(((width - title_width) // 2, 6), title, font=title_font, fill=(255, 255, 255))

        message = "No digital registers selected"
        message_width, _ = gauge._text_size(draw, message, body_font)
        draw.text(((width - message_width) // 2, height // 2), message, font=body_font, fill=(150, 150, 150))

        if gauge.rotation_degrees:
            image = image.rotate(gauge.rotation_degrees)

        gauge.disp.ShowImage(image)
        return

    with state.acquire_lock():
        page_index = state.digital_page_index % len(selected_registers)

    register = selected_registers[page_index]
    register_value = register_values.get(register, 0)

    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_font = gauge.label_font
    body_font = ImageFont.load_default()

    title = f"Digital 0x{register:02X} {page_index + 1}/{len(selected_registers)}"
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
