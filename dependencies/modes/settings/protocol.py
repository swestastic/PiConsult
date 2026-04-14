from __future__ import annotations

import json
import os
from functools import partial
from typing import Any, Callable, Sequence

from dependencies.common.helpers import speed_unit_label
from dependencies.consult.registers import (
    DEFAULT_READ_PARAMETERS,
    MAX_READ_PARAMETERS,
    READ_PARAMETER_OPTIONS,
    get_selected_stream_codes,
    normalize_read_parameters,
    read_parameter_summary,
    read_parameter_title,
)


def _resolve_config_path(file_path: str | os.PathLike[str] | None) -> str:
    raw_path = os.fspath(file_path) if file_path is not None else ""
    raw_path = raw_path.strip().strip('"').strip("'")
    expanded_path = os.path.expanduser(raw_path)
    return os.path.abspath(os.path.normpath(expanded_path))


def Load_Config(FILE: str | os.PathLike[str] | None) -> dict[str, Any]:
    resolved_file = _resolve_config_path(FILE)
    try:
        with open(resolved_file, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        print("Config file not found, using default settings")
        return {
            "Units_Speed": "MPH",
            "Units_Temp": "F",
            "Speed_Correction": 1.0,
            "Gauge_Display_Mode": "Gauge + Value",
            "Default_Display": 0,
            "Coolant_Warning": 200,
            "RPM_Warning": 7000,
            "Read_Parameters": [0x0B, 0x01, 0x08, 0x0C, 0x0D, 0x05, 0x09, 0x13, 0x16, 0x17, 0x1A, 0x1C, 0x1E, 0x1F, 0x21],
            "Log_Index": 0,
        }


def Save_Config(FILE: str | os.PathLike[str] | None, settings: dict[str, Any]) -> None:
    resolved_file = _resolve_config_path(FILE)
    parent_dir = os.path.dirname(resolved_file)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    serializable_settings = dict(settings)
    serializable_settings["Read_Parameters"] = [f"0x{code:02X}" for code in normalize_read_parameters(settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS))]

    try:
        with open(resolved_file, "w", encoding="utf-8") as file:
            json.dump(serializable_settings, file, indent=4)
            file.write("\n")
        return
    except OSError:
        fallback_file = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.basename(resolved_file)))
        if fallback_file == resolved_file:
            raise
        fallback_parent = os.path.dirname(fallback_file)
        if fallback_parent:
            os.makedirs(fallback_parent, exist_ok=True)
        with open(fallback_file, "w", encoding="utf-8") as file:
            json.dump(serializable_settings, file, indent=4)
            file.write("\n")


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


def _bind(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Callable[..., Any]:
    return partial(fn, *args, **kwargs)


def build_settings_callbacks(
    state: Any,
    settings: dict[str, object],
    display_text: list[str],
    units: list[str],
    setting_text: list[str],
    settings_adjustable_indexes: set[int],
    read_parameter_options: Sequence[object],
    gauge: Any,
    show_gauge_fn: Callable[..., None],
    parse_int_fn: Callable[[object, int], int],
    parse_float_fn: Callable[[object, float], float],
    temp_unit_label_fn: Callable[[object], str],
    save_config_fn: Callable[[str, dict[str, object]], None],
    config_file: str,
    update_reader_settings_fn: Callable[[dict[str, object]], None],
) -> dict[str, Callable[..., Any]]:
    from .ui import show_setting_screen

    refresh_setting_values = _bind(
        update_setting_values,
        state,
        settings,
        display_text,
        units,
        temp_unit_label_fn,
        parse_float_fn,
    )
    refresh_units = _bind(update_units, state, units, refresh_setting_values, speed_unit_label, temp_unit_label_fn)

    return {
        "refresh_setting_values": refresh_setting_values,
        "refresh_units": refresh_units,
        "show_setting_screen": _bind(
            show_setting_screen,
            state,
            settings,
            setting_text,
            settings_adjustable_indexes,
            read_parameter_options,
            gauge,
            show_gauge_fn,
        ),
        "apply_settings_to_runtime": _bind(
            apply_settings_to_runtime,
            state,
            settings,
            display_text,
            units,
            parse_int_fn,
            parse_float_fn,
            temp_unit_label_fn,
            refresh_setting_values,
        ),
        "adjust_setting_value": _bind(
            adjust_setting_value,
            state,
            settings,
            parse_float_fn=parse_float_fn,
            temp_unit_label_fn=temp_unit_label_fn,
            save_config_fn=save_config_fn,
            config_file=config_file,
            update_reader_settings_fn=update_reader_settings_fn,
            update_settings_values_fn=refresh_setting_values,
        ),
        "toggle_speed_units": _bind(
            toggle_speed_units,
            state,
            settings,
            save_config_fn,
            config_file,
            refresh_units,
            update_reader_settings_fn,
        ),
        "toggle_temp_units": _bind(
            toggle_temp_units,
            state,
            settings,
            save_config_fn,
            config_file,
            refresh_units,
            update_reader_settings_fn,
            parse_float_fn,
        ),
        "cycle_default_display": _bind(
            cycle_default_display,
            state,
            settings,
            display_text,
            save_config_fn,
            config_file,
        ),
        "toggle_gauge_display_mode": _bind(
            toggle_gauge_display_mode,
            state,
            settings,
            save_config_fn,
            config_file,
            refresh_setting_values,
        ),
        "toggle_read_parameter": _bind(
            toggle_read_parameter,
            state,
            settings,
            save_config_fn,
            config_file,
            refresh_setting_values,
        ),
        "finalize_read_parameters": _bind(
            finalize_read_parameters,
            state,
            settings,
            update_reader_settings_fn,
            refresh_setting_values,
        ),
    }


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
