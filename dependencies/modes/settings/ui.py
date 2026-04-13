from functools import partial
from typing import Any, Callable, Sequence

from PIL import Image, ImageDraw, ImageFont

from dependencies.common.ui import draw_scrollable_menu_screen
from dependencies.consult.registers import (
    DEFAULT_READ_PARAMETERS,
    normalize_read_parameters,
    read_parameter_label,
)
from dependencies.config import SOFTWARE_VERSION

INFO_LINES = [
    "PiConsult by Swestastic",
    f"Software Version: {SOFTWARE_VERSION}",
    "",
    "This is free software.",
    "You are free to use, modify, and share it.",
    "See the project README for details.",
    "",
    "github.com/swestastic/PiConsult",
]


def build_show_setting_screen_fn(
    state: Any,
    settings: dict[str, object],
    setting_text: list[str],
    settings_adjustable_indexes: set[int],
    read_parameter_options: Sequence[object],
    gauge: Any,
    show_gauge_fn: Callable[..., None],
) -> Callable[[], None]:
    return partial(
        show_setting_screen,
        state,
        settings,
        setting_text,
        settings_adjustable_indexes,
        read_parameter_options,
        gauge,
        show_gauge_fn,
    )


def show_settings_list_screen(
    gauge: Any,
    setting_text: list[str],
    setting_values: list[Any],
    selected_index: int,
    setting_editing: bool,
    settings_adjustable_indexes: set[int],
) -> None:
    def _line_builder(label: str, row_index: int, is_selected: bool) -> tuple[str, tuple[int, int, int]]:
        pointer = ">" if is_selected else " "
        value_text = str(setting_values[row_index]) if row_index < len(setting_values) else ""
        edit_tag = " [EDIT]" if (is_selected and setting_editing and row_index in settings_adjustable_indexes) else ""
        line = f"{pointer} {label}: {value_text}{edit_tag}"
        text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        return line, text_color

    footer = "Up/Dn: Adjust  Select: Save Mode: Back" if setting_editing else "Up/Dn: Navigate  Select: Edit Mode: Back"
    draw_scrollable_menu_screen(gauge, "Settings", setting_text, selected_index, _line_builder, footer)


def _truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return text[: max_length - 3] + "..."


def show_read_parameters_screen(
    gauge: Any,
    read_parameter_options: Sequence[object],
    selected_codes: list[int],
    cursor_index: int,
) -> None:
    body_font = getattr(gauge, "menu_font", ImageFont.load_default())

    def _line_builder(option: object, _row_index: int, is_cursor: bool) -> tuple[str, tuple[int, int, int]]:
        option_code = int(getattr(option, "code", 0))
        option_label = str(getattr(option, "label", read_parameter_label(option_code)))
        is_selected = option_code in selected_codes
        pointer = ">" if is_cursor else " "
        check = "[x]" if is_selected else "[ ]"
        label = _truncate_text(f"0x{option_code:02X} {option_label}", 16)
        text_color = (240, 240, 240) if is_cursor else (165, 165, 165)
        return f"{pointer} {check} {label}", text_color

    footer = "Up/Dn: Navigate  Select: Toggle  Mode: Back"
    draw_scrollable_menu_screen(
        gauge,
        "Read Parameters",
        list(read_parameter_options),
        cursor_index,
        _line_builder,
        footer,
        font=body_font,
        start_y=30,
        bottom_margin=18,
    )


def show_info_screen(gauge: Any) -> None:
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title = "Info"
    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    body_font = ImageFont.load_default()
    line_gap = 4
    line_sizes = [gauge._text_size(draw, line, body_font) for line in INFO_LINES]
    total_height = sum(line_height for _, line_height in line_sizes) + (line_gap * (len(INFO_LINES) - 1))
    y_cursor = max(32, (height - total_height) // 2)

    for line, (line_width, line_height) in zip(INFO_LINES, line_sizes):
        if not line:
            y_cursor += line_height + line_gap
            continue
        draw.text(((width - line_width) // 2, y_cursor), line, font=body_font, fill=(220, 220, 220))
        y_cursor += line_height + line_gap

    footer = "Mode/Select: Back"
    footer_font = getattr(gauge, "footer_font", body_font)
    draw.text((8, height - 19), footer, font=footer_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


def show_setting_screen(
    state: Any,
    settings: dict[str, object],
    setting_text: list[str],
    settings_adjustable_indexes: set[int],
    read_parameter_options: Sequence[object],
    gauge: Any,
    show_gauge_fn: Callable[..., None],
) -> None:
    with state.acquire_lock():
        setting_index = state.setting_index
        setting_editing = state.setting_editing
        setting_info_view = state.setting_info_view
        setting_in_item = state.setting_in_item
        setting_values = state.setting_values.copy()

    if setting_info_view:
        show_info_screen(gauge)
        return

    if setting_in_item and setting_text[setting_index] == "Read Parameters":
        with state.acquire_lock():
            cursor_index = state.read_parameter_index
        selected_codes = normalize_read_parameters(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))
        show_read_parameters_screen(gauge, read_parameter_options, selected_codes, cursor_index)
        return

    show_settings_list_screen(
        gauge,
        setting_text,
        setting_values,
        setting_index,
        setting_editing,
        settings_adjustable_indexes,
    )
