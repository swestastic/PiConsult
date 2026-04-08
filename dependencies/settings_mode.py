from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import serial
from PIL import Image, ImageDraw, ImageFont

from dependencies.consult_registers import (
    DEFAULT_READ_PARAMETERS,
    MAX_READ_PARAMETERS,
    READ_PARAMETER_OPTIONS,
    get_selected_stream_codes,
    normalize_read_parameters,
    read_parameter_label,
    read_parameter_summary,
    read_parameter_title,
)

APP_VERSION = "V1.0.0"
INFO_LINES = [
    "PiConsult by Swestastic",
    f"Software Version: {APP_VERSION}",
    "",
    "This is free software.",
    "You are free to use, modify, and share it.",
    "See the project README for details.",
    "",
    "github.com/swestastic/PiConsult",
]


@lru_cache(maxsize=1)
def _list_body_font() -> Any:
    font_dir = Path(__file__).resolve().parent / "Font"
    for font_name in ("Font02.ttf", "Font01.ttf", "Font00.ttf"):
        font_path = font_dir / font_name
        if not font_path.exists():
            continue
        try:
            return ImageFont.truetype(str(font_path), 18)
        except Exception:
            continue
    return ImageFont.load_default()


def update_units(
    state: Any,
    units: list[str],
    refresh_settings_fn: Callable[[], None],
    speed_unit_label_fn: Callable[[object], str],
    temp_unit_label_fn: Callable[[object], str],
) -> None:
    units[1] = speed_unit_label_fn(state.units_speed)
    units[4] = temp_unit_label_fn(state.units_temp)
    refresh_settings_fn()


def speed_unit_label(value: object) -> str:
    return "MPH" if value in (1, "1", "MPH", "mph") else "KPH"


def build_refresh_setting_values_fn(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    units: list[str],
    temp_unit_label_fn: Callable[[object], str],
    parse_float_fn: Callable[[object, float], float],
) -> Callable[[], None]:
    return partial(update_setting_values, state, settings, display_text, units, temp_unit_label_fn, parse_float_fn)


def build_refresh_units_fn(
    state: Any,
    units: list[str],
    refresh_settings_fn: Callable[[], None],
    temp_unit_label_fn: Callable[[object], str],
) -> Callable[[], None]:
    return partial(update_units, state, units, refresh_settings_fn, speed_unit_label, temp_unit_label_fn)


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


def build_toggle_read_parameter_fn(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_settings_values_fn: Callable[[], None],
) -> Callable[[int], None]:
    return partial(
        toggle_read_parameter,
        state,
        settings,
        save_config_fn,
        config_file,
        update_settings_values_fn,
    )


def build_finalize_read_parameters_fn(
    state: Any,
    settings: dict[str, object],
    update_reader_settings_fn: Callable[[dict[str, object]], None],
    update_settings_values_fn: Callable[[], None],
) -> Callable[[], None]:
    return partial(
        finalize_read_parameters,
        state,
        settings,
        update_reader_settings_fn,
        update_settings_values_fn,
    )


def show_settings_list_screen(
    gauge: Any,
    setting_text: list[str],
    setting_values: list[Any],
    selected_index: int,
    setting_editing: bool,
    settings_adjustable_indexes: set[int],
) -> None:
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title = "Settings"
    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    body_font = _list_body_font()
    start_y = 36
    bottom_margin = 18
    max_visible_rows = 5
    total_rows = len(setting_text)
    visible_rows = min(max_visible_rows, total_rows)
    row_height = max(13, (height - start_y - bottom_margin) // max(1, visible_rows))
    visible_start = max(0, min(selected_index - (visible_rows // 2), max(total_rows - visible_rows, 0)))
    visible_end = min(total_rows, visible_start + visible_rows)

    for visible_row, row_index in enumerate(range(visible_start, visible_end)):
        label = setting_text[row_index]
        y = start_y + (visible_row * row_height)
        is_selected = row_index == selected_index

        if is_selected:
            draw.rectangle((4, y + 3, width - 4, y + row_height + 1), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_selected else " "
        value_text = str(setting_values[row_index]) if row_index < len(setting_values) else ""
        edit_tag = " [EDIT]" if (is_selected and setting_editing and row_index in settings_adjustable_indexes) else ""
        line = f"{pointer} {label}: {value_text}{edit_tag}"
        text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        draw.text((8, y + 2), line, font=body_font, fill=text_color)

    footer = "Up/Down: Adjust  Select: Save" if setting_editing else "Up/Down: Navigate  Select: Edit"
    draw.text((8, height - 20), footer, font=body_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


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
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title = "Read Parameters"
    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    body_font = _list_body_font()
    top_y = 30
    footer_y = height - 18
    max_visible_rows = 5

    option_count = len(read_parameter_options)
    visible_rows = min(max_visible_rows, max(1, option_count))
    row_height = max(13, (footer_y - top_y) // max(1, visible_rows))
    cursor_index = max(0, min(cursor_index, max(option_count - 1, 0)))
    visible_start = max(0, min(cursor_index - (visible_rows // 2), max(option_count - visible_rows, 0)))
    visible_end = min(option_count, visible_start + visible_rows)

    for visible_row, option in enumerate(read_parameter_options[visible_start:visible_end]):
        row_index = visible_start + visible_row
        option_code = int(getattr(option, "code", 0))
        option_label = str(getattr(option, "label", read_parameter_label(option_code)))
        y = top_y + (visible_row * row_height)
        is_selected = option_code in selected_codes
        is_cursor = row_index == cursor_index

        if is_cursor:
            draw.rectangle((4, y + 3, width - 4, y + row_height + 1), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_cursor else " "
        check = "[x]" if is_selected else "[ ]"
        label = _truncate_text(f"0x{option_code:02X} {option_label}", 16)
        text_color = (240, 240, 240) if is_cursor else (165, 165, 165)
        draw.text((8, y + 2), f"{pointer} {check} {label}", font=body_font, fill=text_color)

    footer = "Up/Down: Navigate  Select: Toggle  Mode: Back"
    draw.text((8, footer_y), footer, font=body_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


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
    total_height = sum(height for _, height in line_sizes) + (line_gap * (len(INFO_LINES) - 1))
    y_cursor = max(32, (height - total_height) // 2)

    for line, (line_width, line_height) in zip(INFO_LINES, line_sizes):
        if not line:
            y_cursor += line_height + line_gap
            continue
        draw.text(((width - line_width) // 2, y_cursor), line, font=body_font, fill=(220, 220, 220))
        y_cursor += line_height + line_gap

    footer = "Select to return"
    footer_width, _ = gauge._text_size(draw, footer, body_font)
    draw.text(((width - footer_width) // 2, height - 14), footer, font=body_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


def build_apply_settings_to_runtime_fn(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    units: list[str],
    parse_int_fn: Callable[[object, int], int],
    parse_float_fn: Callable[[object, float], float],
    temp_unit_label_fn: Callable[[object], str],
    refresh_settings_fn: Callable[[], None],
) -> Callable[[], None]:
    return partial(
        apply_settings_to_runtime,
        state,
        settings,
        display_text,
        units,
        parse_int_fn,
        parse_float_fn,
        temp_unit_label_fn,
        refresh_settings_fn,
    )


def build_adjust_setting_value_fn(
    state: Any,
    settings: dict[str, object],
    parse_float_fn: Callable[[object, float], float],
    temp_unit_label_fn: Callable[[object], str],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_reader_settings_fn: Callable[[dict[str, object]], None],
    update_settings_values_fn: Callable[[], None],
) -> Callable[[int, int], None]:
    return partial(
        adjust_setting_value,
        state,
        settings,
        parse_float_fn=parse_float_fn,
        temp_unit_label_fn=temp_unit_label_fn,
        save_config_fn=save_config_fn,
        config_file=config_file,
        update_reader_settings_fn=update_reader_settings_fn,
        update_settings_values_fn=update_settings_values_fn,
    )


def build_toggle_speed_units_fn(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_units_fn: Callable[[], None],
    update_reader_settings_fn: Callable[[dict[str, object]], None],
) -> Callable[[], None]:
    return partial(toggle_speed_units, state, settings, save_config_fn, config_file, update_units_fn, update_reader_settings_fn)


def build_toggle_temp_units_fn(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_units_fn: Callable[[], None],
    update_reader_settings_fn: Callable[[dict[str, object]], None],
    parse_float_fn: Callable[[object, float], float],
) -> Callable[[], None]:
    return partial(
        toggle_temp_units,
        state,
        settings,
        save_config_fn,
        config_file,
        update_units_fn,
        update_reader_settings_fn,
        parse_float_fn,
    )


def build_toggle_gauge_display_mode_fn(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_settings_values_fn: Callable[[], None],
) -> Callable[[], None]:
    return partial(toggle_gauge_display_mode, state, settings, save_config_fn, config_file, update_settings_values_fn)


def build_cycle_default_display_fn(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
) -> Callable[[], None]:
    return partial(cycle_default_display, state, settings, display_text, save_config_fn, config_file)


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


def update_setting_values(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    units: list[str],
    temp_unit_label_fn: Callable[[object], str],
    parse_float_fn: Callable[[object, float], float],
) -> None:
    selected_stream_codes = get_selected_stream_codes(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))
    selected_stream_titles = [read_parameter_title(code) for code in selected_stream_codes]

    with state.acquire_lock():
        state.setting_values[0] = units[1]
        state.setting_values[1] = units[4]
        state.setting_values[2] = f"{state.speed_correction:.2f}"
        state.setting_values[3] = normalize_gauge_display_mode(state.gauge_display_mode)
        if selected_stream_titles:
            state.default_display = state.default_display % len(selected_stream_titles)
            state.setting_values[4] = selected_stream_titles[state.default_display]
        else:
            state.default_display = 0
            state.setting_values[4] = "None"
        state.setting_values[5] = f"{int(round(state.rpm_warning))} RPM"
        state.setting_values[6] = f"{int(round(state.coolant_warning))} {temp_unit_label_fn(state.units_temp)}"
        if len(state.setting_values) > 7:
            state.setting_values[7] = read_parameter_summary(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))
        if len(state.setting_values) > 8:
            state.setting_values[8] = "About"


def apply_settings_to_runtime(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    units: list[str],
    parse_int_fn: Callable[[object, int], int],
    parse_float_fn: Callable[[object, float], float],
    temp_unit_label_fn: Callable[[object], str],
    refresh_settings_fn: Callable[[], None],
) -> None:
    state.units_speed = settings.get("Units_Speed", state.units_speed)
    state.units_temp = settings.get("Units_Temp", state.units_temp)
    state.speed_correction = parse_float_fn(settings.get("Speed_Correction", state.speed_correction), state.speed_correction)
    state.gauge_display_mode = normalize_gauge_display_mode(settings.get("Gauge_Display_Mode", state.gauge_display_mode))

    selected_stream_codes = get_selected_stream_codes(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))
    default_count = max(1, len(selected_stream_codes))

    with state.acquire_lock():
        state.default_display = parse_int_fn(settings.get("Default_Display", state.default_display), state.default_display) % default_count
        state.display_index = state.default_display
        state.rpm_warning = parse_float_fn(settings.get("RPM_Warning", state.rpm_warning), state.rpm_warning)
        state.coolant_warning = parse_float_fn(settings.get("Coolant_Warning", state.coolant_warning), state.coolant_warning)

    update_units(state, units, refresh_settings_fn, speed_unit_label, temp_unit_label_fn)
    update_setting_values(state, settings, display_text, units, temp_unit_label_fn, parse_float_fn)


def toggle_read_parameter(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_settings_values_fn: Callable[[], None],
    parameter_index: int,
) -> None:
    if parameter_index < 0 or parameter_index >= len(READ_PARAMETER_OPTIONS):
        return

    parameter_code = int(READ_PARAMETER_OPTIONS[parameter_index].code)
    selected_codes = normalize_read_parameters(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))

    if parameter_code in selected_codes:
        if len(selected_codes) <= 1:
            return
        selected_codes = [code for code in selected_codes if code != parameter_code]
    else:
        if len(selected_codes) >= MAX_READ_PARAMETERS:
            return
        selected_codes.append(parameter_code)

    settings["Read_Parameters"] = selected_codes
    save_config_fn(config_file, settings)
    with state.acquire_lock():
        state.read_parameters_dirty = True
    update_settings_values_fn()


def finalize_read_parameters(
    state: Any,
    settings: dict[str, object],
    update_reader_settings_fn: Callable[[dict[str, object]], None],
    update_settings_values_fn: Callable[[], None],
) -> None:
    with state.acquire_lock():
        should_apply = bool(getattr(state, "read_parameters_dirty", False))
        state.read_parameters_dirty = False

    if not should_apply:
        return

    update_reader_settings_fn(settings)
    update_settings_values_fn()


def adjust_setting_value(
    state: Any,
    settings: dict[str, object],
    setting_index: int,
    direction: int,
    parse_float_fn: Callable[[object, float], float],
    temp_unit_label_fn: Callable[[object], str],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_reader_settings_fn: Callable[[dict[str, object]], None],
    update_settings_values_fn: Callable[[], None],
) -> None:
    if setting_index == 2:
        with state.acquire_lock():
            current = state.speed_correction
        new_value = round(max(0.50, min(2.00, current + (direction * 0.01))), 2)
        with state.acquire_lock():
            state.speed_correction = new_value
        settings["Speed_Correction"] = new_value

    elif setting_index == 5:
        with state.acquire_lock():
            current = state.rpm_warning
        new_value = float(max(1000, min(10000, int(round(current)) + (direction * 100))))
        with state.acquire_lock():
            state.rpm_warning = new_value
        settings["RPM_Warning"] = int(round(new_value))

    elif setting_index == 6:
        with state.acquire_lock():
            current = state.coolant_warning
            units_temp = state.units_temp
        is_fahrenheit = temp_unit_label_fn(units_temp) == "F"
        minimum = 50 if is_fahrenheit else 10
        maximum = 300 if is_fahrenheit else 150
        new_value = float(max(minimum, min(maximum, int(round(current)) + direction)))
        with state.acquire_lock():
            state.coolant_warning = new_value
        settings["Coolant_Warning"] = int(round(new_value))

    else:
        return

    save_config_fn(config_file, settings)
    update_reader_settings_fn(settings)
    update_settings_values_fn()


def toggle_speed_units(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_units_fn: Callable[[], None],
    update_reader_settings_fn: Callable[[dict[str, object]], None],
) -> None:
    with state.acquire_lock():
        units_speed = state.units_speed

    new_units_speed = "KPH" if str(units_speed).upper() == "MPH" else "MPH"
    settings["Units_Speed"] = new_units_speed
    with state.acquire_lock():
        state.units_speed = new_units_speed
    save_config_fn(config_file, settings)
    update_units_fn()
    update_reader_settings_fn(settings)


def toggle_temp_units(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_units_fn: Callable[[], None],
    update_reader_settings_fn: Callable[[dict[str, object]], None],
    parse_float_fn: Callable[[object, float], float],
) -> None:
    with state.acquire_lock():
        units_temp = state.units_temp
        coolant_warning = state.coolant_warning

    old_unit = "F" if str(units_temp).upper() == "F" else "C"
    new_units_temp = "C" if old_unit == "F" else "F"

    if old_unit == "F" and new_units_temp == "C":
        coolant_warning = (coolant_warning - 32.0) * (5.0 / 9.0)
    elif old_unit == "C" and new_units_temp == "F":
        coolant_warning = (coolant_warning * (9.0 / 5.0)) + 32.0

    settings["Units_Temp"] = new_units_temp
    settings["Coolant_Warning"] = int(round(coolant_warning))
    with state.acquire_lock():
        state.units_temp = new_units_temp
        state.coolant_warning = float(int(round(coolant_warning)))
    save_config_fn(config_file, settings)
    update_units_fn()
    update_reader_settings_fn(settings)


def cycle_default_display(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
) -> None:
    selected_stream_codes = get_selected_stream_codes(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))
    selected_stream_titles = [read_parameter_title(code) for code in selected_stream_codes]

    if not selected_stream_titles:
        with state.acquire_lock():
            state.default_display = 0
            state.display_index = 0
            state.setting_values[4] = "None"
        settings["Default_Display"] = 0
        save_config_fn(config_file, settings)
        return

    with state.acquire_lock():
        state.default_display = (state.default_display + 1) % len(selected_stream_titles)
        default_display = state.default_display
        state.display_index = default_display
        state.setting_values[4] = selected_stream_titles[default_display]
    settings["Default_Display"] = default_display
    save_config_fn(config_file, settings)


def normalize_gauge_display_mode(value: object) -> str:
    raw = str(value).strip().lower()
    if raw in {"value", "value only", "value-only", "value_only"}:
        return "Value Only"
    return "Gauge + Value"


def toggle_gauge_display_mode(
    state: Any,
    settings: dict[str, object],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_settings_values_fn: Callable[[], None],
) -> None:
    with state.acquire_lock():
        current = normalize_gauge_display_mode(state.gauge_display_mode)

    new_mode = "Value Only" if current == "Gauge + Value" else "Gauge + Value"
    with state.acquire_lock():
        state.gauge_display_mode = new_mode
    settings["Gauge_Display_Mode"] = new_mode
    save_config_fn(config_file, settings)
    update_settings_values_fn()
