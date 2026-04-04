from functools import partial
from typing import Any, Callable, Optional

import serial
from PIL import Image, ImageDraw, ImageFont


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
    setting_text: list[str],
    settings_adjustable_indexes: set[int],
    gauge: Any,
    show_gauge_fn: Callable[..., None],
) -> Callable[[], None]:
    return partial(show_setting_screen, state, setting_text, settings_adjustable_indexes, gauge, show_gauge_fn)


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

    body_font = ImageFont.load_default()
    start_y = 36
    bottom_margin = 18
    row_height = max(13, (height - start_y - bottom_margin) // len(setting_text))

    for row_index, label in enumerate(setting_text):
        y = start_y + (row_index * row_height)
        is_selected = row_index == selected_index

        if is_selected:
            draw.rectangle((4, y, width - 4, y + row_height - 2), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_selected else " "
        value_text = str(setting_values[row_index]) if row_index < len(setting_values) else ""
        edit_tag = " [EDIT]" if (is_selected and setting_editing and row_index in settings_adjustable_indexes) else ""
        line = f"{pointer} {label}: {value_text}{edit_tag}"
        text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        draw.text((8, y + 2), line, font=body_font, fill=text_color)

    footer = "Up/Down: Adjust  Select: Save" if setting_editing else "Up/Down: Navigate  Select: Edit"
    draw.text((8, height - 14), footer, font=body_font, fill=(180, 180, 180))

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
    setting_text: list[str],
    settings_adjustable_indexes: set[int],
    gauge: Any,
    show_gauge_fn: Callable[..., None],
) -> None:
    with state.acquire_lock():
        setting_index = state.setting_index
        setting_editing = state.setting_editing
        setting_values = state.setting_values.copy()

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
    with state.acquire_lock():
        state.setting_values[0] = units[1]
        state.setting_values[1] = units[4]
        state.setting_values[2] = f"{state.speed_correction:.2f}"
        state.setting_values[3] = display_text[state.default_display]
        state.setting_values[4] = f"{int(round(state.rpm_warning))} RPM"
        state.setting_values[5] = f"{int(round(state.coolant_warning))} {temp_unit_label_fn(state.units_temp)}"


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

    with state.acquire_lock():
        state.default_display = parse_int_fn(settings.get("Default_Display", state.default_display), state.default_display) % len(display_text)
        state.rpm_warning = parse_float_fn(settings.get("RPM_Warning", state.rpm_warning), state.rpm_warning)
        state.coolant_warning = parse_float_fn(settings.get("Coolant_Warning", state.coolant_warning), state.coolant_warning)

    update_units(state, units, refresh_settings_fn, speed_unit_label, temp_unit_label_fn)
    update_setting_values(state, settings, display_text, units, temp_unit_label_fn, parse_float_fn)


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

    elif setting_index == 4:
        with state.acquire_lock():
            current = state.rpm_warning
        new_value = float(max(1000, min(10000, int(round(current)) + (direction * 100))))
        with state.acquire_lock():
            state.rpm_warning = new_value
        settings["RPM_Warning"] = int(round(new_value))

    elif setting_index == 5:
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
    with state.acquire_lock():
        state.default_display = (state.default_display + 1) % len(display_text)
        default_display = state.default_display
        state.setting_values[3] = display_text[default_display]
    settings["Default_Display"] = default_display
    save_config_fn(config_file, settings)
