import os
import argparse
import time
import serial
import threading
from functools import lru_cache
from pathlib import Path
import numpy as np
from typing import Optional, Any
from PIL import Image, ImageDraw, ImageFont

from dependencies.Buttons import process_buttons as process_button_events, setup_button_callbacks
from dependencies.dtc_dict import dtc_codes as DTC_CODE_TITLES
from dependencies.settings import Load_Config, Save_Config
from dependencies.read import ReadStream
from dependencies.logs import Create_Log_File, WriteLog
from dependencies.local_ui import LocalButton, local_ui_requested
from dependencies.active_test_mode import (
    ACTIVE_TEST_ITEMS,
    ACTIVE_TEST_COOLANT,
    ACTIVE_TEST_FUEL_INJ,
    ACTIVE_TEST_TIMING,
    ACTIVE_TEST_IAAC,
    ACTIVE_TEST_POWER_BALANCE,
    ACTIVE_TEST_FUEL_PUMP,
    ACTIVE_TEST_CLEAR_SELF_LEARN,
    apply_active_test_effects_to_demo_values,
    adjust_active_test_value,
    run_active_test_action,
    show_active_test_screen,
)
from dependencies.consult_registers import (
    DEFAULT_READ_PARAMETERS,
    READ_PARAMETER_OPTIONS,
    get_selected_digital_registers,
    get_selected_stream_codes,
    get_stream_unit,
    read_parameter_label,
    read_parameter_title,
)
from dependencies.settings_mode import (
    build_adjust_setting_value_fn,
    build_apply_settings_to_runtime_fn,
    build_cycle_default_display_fn,
    build_finalize_read_parameters_fn,
    build_refresh_setting_values_fn,
    build_refresh_units_fn,
    build_show_setting_screen_fn,
    build_toggle_read_parameter_fn,
    build_toggle_gauge_display_mode_fn,
    build_toggle_speed_units_fn,
    build_toggle_temp_units_fn,
)
from dependencies.consult_protocol import (
    build_clear_dtc_codes_fn,
    build_read_dtc_codes_fn,
    send_activation_command as protocol_send_activation_command,
)
from dependencies.digital_mode import (
    show_digital_bits_screen,
    update_digital_registers_from_demo,
    update_digital_registers_from_reader,
)
from dependencies.dtc_mode import (
    refresh_dtc_codes_for_buttons,
    show_dtc_screen,
)

try:
    from gpiozero import Button as GpioButton  # type: ignore
except Exception:
    GpioButton = None

from dependencies.gauge import GaugeNeedleDisplay


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consult gauge display runner")
    parser.add_argument("--demo", action="store_true", help="Skip ECU connection and render dummy data")
    args, _ = parser.parse_known_args()
    return args


ARGS = parse_args()
DEMO_MODE = bool(ARGS.demo)
USE_LOCAL_UI = local_ui_requested(default=(GpioButton is None))
Button = LocalButton if USE_LOCAL_UI else GpioButton

if Button is None:
    raise RuntimeError("No supported button backend found (gpiozero or local UI)")


READ_PARAMETER_CODES = [option.code for option in READ_PARAMETER_OPTIONS]


def parse_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return default


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (ValueError, TypeError, OverflowError):
        return default


def speed_unit_label(units_speed: object) -> str:
    if units_speed in (1, "1", "MPH", "mph"):
        return "MPH"
    return "KPH"


def temp_unit_label(units_temp: object) -> str:
    if units_temp in (1, "1", "F", "f"):
        return "F"
    return "C"


def format_stream_value_text(code: int, value: float, unit: str) -> str:
    if unit == "raw":
        return f"{int(round(value))}"
    if unit in {"ms", "g/s"}:
        return f"{value:.2f}"
    if code in {0x01, 0x0B, 0x08, 0x16}:
        return f"{int(round(value))}"
    if code in {0x0C, 0x09}:
        return f"{value:.1f}"
    return f"{value:.2f}"


def build_demo_stream_value_map(elapsed_seconds: float) -> dict[int, float]:
    values = get_demo_values(elapsed_seconds)
    return {
        0x01: float(values[0]),

        0x05: float(values[1]),
        0x07: float(values[1]),

        0x08: float(values[2]),

        0x09: float(values[3]),
        0x0A: float(values[3]),

        0x0B: float(values[4]),
        0x0C: float(values[5]),
        0x0D: float(values[6]),
        0x0F: float(values[7]),
        0x0D: float(values[8]),
        0x11: float(values[9]),
        0x12: float(values[10]),
        0x15: float(values[10]),
        0x23: float(values[11]),
        0x16: float(values[12]),
        0x17: float(values[13]),
        0x1A: float(values[13]),
        0x1B: float(values[13]),
        0x1C: float(values[13]),
        0x1D: float(values[13]),
    }


def get_stream_value_for_code(code: int, reader: Optional[object], demo_value_map: dict[int, float], speed_correction: float) -> float:
    if code == 0x0B:
        return float(demo_value_map.get(code, 0.0) * speed_correction) if reader is None else float(getattr(reader, "SPEED_Value", 0.0)) * speed_correction
    if code == 0x01:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "RPM_Value", 0.0))
    if code == 0x08:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "TEMP_Value", 0.0))
    if code == 0x0C:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "BATT_Value", 0.0))
    if code == 0x0D:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "TPS_Value", 0.0))
    if code == 0x03:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "MAF_Value", 0.0))
    if code == 0x09:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "INJ_Value", 0.0))
    if code == 0x16:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "TIM_Value", 0.0))
    if code == 0x17:
        return float(demo_value_map.get(code, 0.0)) if reader is None else float(getattr(reader, "AAC_Value", 0.0))

    if reader is None:
        return float(demo_value_map.get(code, 0.0))

    with_units_temp = Units_Temp
    raw_values = getattr(reader, "register_values", {})
    raw_value = float(raw_values.get(code, 0.0))

    if code in {0x03, 0x04, 0x05, 0x06, 0x07, 0x12, 0x27, 0x29, 0x2F, 0x35, 0x36, 0x39}:
        return raw_value * 5.0 / 1000.0

    if code in {0x0A}:
        return raw_value * 10.0 / 1000.0

    if code in {0x0F, 0x11, 0x26}:
        temp_c = raw_value - 50.0
        if str(with_units_temp).upper() == "F":
            return (temp_c * 9.0 / 5.0) + 32.0
        return temp_c

    if code in {0x15}:
        msb = int(raw_values.get(0x14, 0)) & 0xFF
        lsb = int(raw_values.get(0x15, 0)) & 0xFF
        return float(((msb << 8) | lsb) / 100.0)

    if code in {0x23}:
        msb = int(raw_values.get(0x22, 0)) & 0xFF
        lsb = int(raw_values.get(0x23, 0)) & 0xFF
        return float(((msb << 8) | lsb) / 100.0)

    if code in {0x1A, 0x1B, 0x1C, 0x1D}:
        return raw_value

    if code in {0x28}:
        return raw_value / 2.0

    if code in {0x33}:
        return raw_value / 2.55

    if code in {0x38}:
        return raw_value

    return float(raw_values.get(code, 0.0))


def get_stream_range(code: int, units_speed: object, units_temp: object) -> tuple[float, float]:
    speed_max = 150.0 if str(units_speed).upper() == "MPH" else 240.0
    temp_max = 260.0 if str(units_temp).upper() == "F" else 130.0

    ranges = {
        0x01: (0.0, 8000.0), # RPM

        0x05: (0.0, 5.0), # MAF (LH)
        0x07: (0.0, 5.0), # MAF (RH)

        0x08: (20.0, temp_max), # Coolant Temp

        0x09: (0.0, 100.0), # LH O2 
        0x0A: (0.0, 100.0), # RH O2

        0x0B: (0.0, speed_max), # Speed
        0x0C: (8.0, 15.0), # Battery Voltage
        0x0D: (0.0, 5.0), # TPS
        0x0F: (20.0, temp_max), # Fuel Temp
        0x11: (20.0, temp_max), # IAT
        0x12: (20.0, temp_max), # EGT
        0x15: (0.0, 20.0), # Injection Time (LH)
        0x23: (0.0, 20.0), # Injection Time (RH)
        0x16: (0.0, 70.0), # Ignition Timing
        0x17: (0.0, 100.0), # AAC Duty Cycle

        0x1A: (60.0, 140.0), # AF Alpha (LH)
        0x1B: (60.0, 140.0), # AF Alpha (RH)
        0x1C: (60.0, 140.0), # AF Alpha Self learn (LH)
        0x1D: (60.0, 140.0), # AF Alpha Self learn (RH)
    }
    return ranges.get(code, (0.0, 255.0))


def show_gauge(
    title: str,
    value: float,
    unit: str,
    minimum: float,
    maximum: float,
    *,
    show_needle: bool = True,
    show_dial: bool = True,
    show_value_text: bool = True,
    value_text: Optional[str] = None,
    warning_text: Optional[str] = None,
    warning_lines: Optional[list[str]] = None,
    footer_text: Optional[str] = None,
) -> None:
    gauge.set_range(minimum, maximum)
    gauge.show_value(
        value,
        title=title,
        unit=unit,
        show_needle=show_needle,
        show_dial=show_dial,
        show_value_text=show_value_text,
        value_text=value_text,
        warning_text=warning_text,
        warning_lines=warning_lines,
        footer_text=footer_text,
    )


def WriteText(upper: object, lower: object) -> None:
    title = str(upper) if upper is not None else ""
    lower_text = str(lower) if lower is not None else ""

    if not lower_text:
        show_gauge(title, 0.0, "", 0.0, 1.0)
        return

    parts = lower_text.split()
    numeric = parse_float(parts[0], default=0.0)
    unit = " ".join(parts[1:]) if len(parts) > 1 else ""
    show_gauge(title, numeric, unit, 0.0, max(1.0, abs(numeric) * 1.2))


# Load configs
CONF = os.path.join(os.path.dirname(__file__), "dependencies", "configJSON.json")
Settings = Load_Config(CONF)
Settings.setdefault("Speed_Correction", 1.0)
Settings.setdefault("Gauge_Display_Mode", "Gauge + Value")
Settings.setdefault("Read_Parameters", list(DEFAULT_READ_PARAMETERS))
Settings["Log_Index"] += 1
Save_Config(CONF, Settings)
Log_Index = int(Settings["Log_Index"])
Create_Log_File(Log_Index)

READ_DTC_CODES = build_read_dtc_codes_fn(Log_Index, WriteLog)
CLEAR_DTC_CODES = build_clear_dtc_codes_fn(Log_Index, WriteLog)

Units_Speed = Settings["Units_Speed"]
Units_Temp = Settings["Units_Temp"]
Default_Display = int(Settings["Default_Display"])
RPM_Warning = parse_float(Settings["RPM_Warning"], 6500.0)
Coolant_Warning = parse_float(Settings["Coolant_Warning"], 220.0)
Speed_Correction = parse_float(Settings.get("Speed_Correction", 1.0), 1.0)
Gauge_Display_Mode = str(Settings.get("Gauge_Display_Mode", "Gauge + Value"))

# Gauge display init
GAUGE_ROTATION = int(os.getenv("CONSULT_GAUGE_ROTATION", "0"))
GAUGE_BACKLIGHT = int(os.getenv("CONSULT_GAUGE_BACKLIGHT", "55"))
GAUGE_SPI_FREQ = int(os.getenv("CONSULT_GAUGE_SPI_FREQ", "24000000"))

gauge = GaugeNeedleDisplay(
    min_value=0,
    max_value=100,
    backlight_percent=GAUGE_BACKLIGHT,
    spi_freq_hz=GAUGE_SPI_FREQ,
    rotation_degrees=GAUGE_ROTATION,
)

DISPLAY_TARGET_FPS = max(1.0, parse_float(os.getenv("CONSULT_DISPLAY_FPS", "30"), 30.0))
DISPLAY_MIN_DELTA = max(0.0, parse_float(os.getenv("CONSULT_DISPLAY_MIN_DELTA", "0.25"), 0.25))

# Buttons
ModeButton = Button(26, hold_time=0.5) #17
SelectButton = Button(16, hold_time=0.5) #26
UpButton = Button(23, hold_time=0.5) #23
DownButton = Button(17, hold_time=0.5) #16

# Mode constants
DISPLAY_MODE = 0
DTC_MODE = 1
SETTINGS_MODE = 2
ACTIVE_TEST_MODE = 3
DIGITAL_BITS_MODE = 4
MODE_MENU = 5
MODE_COUNT = 6

MODE_MENU_ITEMS = [
    "Data Stream",
    "DTC",
    "Active Test",
    "Digital Registers",
    "Settings",
]
MODE_MENU_TARGETS = [
    DISPLAY_MODE,
    DTC_MODE,
    ACTIVE_TEST_MODE,
    DIGITAL_BITS_MODE,
    SETTINGS_MODE,
]

# Display and settings metadata (read-only)
DisplayText = ["RPM", "SPEED", "MAF", "AAC", "TEMP", "BATT", "INJ", "TIM", "TPS"]
Units = [
    "RPM",
    speed_unit_label(Units_Speed),
    "V",
    "%",
    temp_unit_label(Units_Temp),
    "V",
    "%",
    "deg",
    "V",
]
SettingText = [
    "Speed Units",
    "Temp Units",
    "Speed Correction",
    "Gauge Display Mode",
    "Default Display",
    "RPM Warning",
    "Coolant Warning",
    "Read Parameters",
    "Info",
]

SETTING_SPEED_UNITS = 0
SETTING_TEMP_UNITS = 1
SETTING_SPEED_CORRECTION = 2
SETTING_GAUGE_DISPLAY_MODE = 3
SETTING_DEFAULT_DISPLAY = 4
SETTING_RPM_WARNING = 5
SETTING_COOLANT_WARNING = 6
SETTING_READ_PARAMETERS = 7
SETTING_INFO = 8
SETTINGS_ADJUSTABLE_INDEXES = {
    SETTING_SPEED_CORRECTION,
    SETTING_RPM_WARNING,
    SETTING_COOLANT_WARNING,
}

class AppState:
    """Thread-safe application state manager. All mutable state is protected by a lock."""

    def __init__(self, default_display: int, units_speed: object, units_temp: object,
                 rpm_warning: float, coolant_warning: float) -> None:
        self._lock = threading.Lock()
        
        # Display and UI state
        self.current_mode = DISPLAY_MODE
        self.display_index = default_display
        self.stream_peak_values: dict[int, float] = {}
        
        # Settings state
        self.units_speed = units_speed
        self.units_temp = units_temp
        self.default_display = default_display
        self.speed_correction = Speed_Correction
        self.gauge_display_mode = Gauge_Display_Mode
        self.rpm_warning = rpm_warning
        self.coolant_warning = coolant_warning
        
        # DTC state
        self.dtc_index = 0
        self.dtc_codes: list[int] = []
        self.dtc_status_message = ""
        self.dtc_status_until = 0.0
        self.dtc_clear_confirm_active = False
        self.dtc_clear_confirm_yes = False

        safe_display_idx = default_display % max(1, len(DisplayText))
        
        # Settings menu state
        self.setting_index = 0
        self.setting_values = [
            speed_unit_label(units_speed),
            temp_unit_label(units_temp),
            f"{Speed_Correction:.2f}",
            Gauge_Display_Mode,
            DisplayText[safe_display_idx],
            f"{int(round(rpm_warning))} RPM",
            f"{int(round(coolant_warning))} {temp_unit_label(units_temp)}",
            f"{len(DEFAULT_READ_PARAMETERS)} Selected",
            "About",
        ]
        self.setting_in_item = False
        self.setting_info_view = False
        self.setting_editing = False
        self.read_parameters_dirty = False
        self.read_parameter_index = 0
        self.stream_display_codes: list[int] = []
        self.stream_display_labels: list[str] = []
        self.stream_display_values: dict[int, float] = {}

        # Mode menu state
        self.mode_menu_index = 0

        # Active test mode state
        self.active_test_index = 0
        self.active_test_in_test = False
        self.active_test_editing = False
        self.active_test_status_message = ""
        self.active_test_status_until = 0.0
        self.active_test_coolant_c = 85
        self.active_test_coolant_override_active = False
        self.active_test_fuel_injection_percent = 100
        self.active_test_timing_offset_deg = 0
        self.active_test_iaac_offset_steps = 0
        self.active_test_power_balance_cursor = 0
        self.active_test_power_balance_cylinders_off = set()
        self.active_test_fuel_pump_off = False

        # Digital bit mode state
        self.digital_register_values = {
            0x13: 0,
            0x1E: 0,
            0x1F: 0,
            0x21: 0,
        }
        self.digital_page_index = 0
        self.digital_bit_index = 0
        
        # Render tracking state
        self.last_display_render_time = 0.0
        self.last_display_index = -1
        self.last_display_code = -1
        self.last_display_value = 0.0
        self.last_display_unit = ""
        self.last_warning_render_time = 0.0
        self.last_warning_overlay_text = ""
        
        # Thread control state
        self.read_thread_active = False
        self.showing_peak = False

    def update_stream_peaks(self, values: dict[int, float]) -> None:
        """Track max observed value per register code."""
        with self._lock:
            for code, value in values.items():
                previous_peak = self.stream_peak_values.get(code)
                if previous_peak is None or value > previous_peak:
                    self.stream_peak_values[code] = value

    def get_display_index(self) -> int:
        """Get current display index."""
        with self._lock:
            return self.display_index

    def set_display_index(self, index: int) -> None:
        """Set current display index."""
        with self._lock:
            self.display_index = index

    def get_current_mode(self) -> int:
        """Get current UI mode."""
        with self._lock:
            return self.current_mode

    def set_current_mode(self, mode: int) -> None:
        """Set current UI mode."""
        with self._lock:
            self.current_mode = mode

    def acquire_lock(self) -> threading.Lock:
        """Return the state lock for use in context managers."""
        return self._lock


# Global state instance
state = AppState(
    default_display=Default_Display,
    units_speed=Units_Speed,
    units_temp=Units_Temp,
    rpm_warning=RPM_Warning,
    coolant_warning=Coolant_Warning,
)


def update_reader_settings(settings: dict[str, object]) -> None:
    if R is not None:
        R.update_settings(settings)


refresh_setting_values = build_refresh_setting_values_fn(
    state,
    Settings,
    DisplayText,
    Units,
    temp_unit_label,
    parse_float,
)
refresh_units = build_refresh_units_fn(
    state,
    Units,
    refresh_setting_values,
    temp_unit_label,
)
show_setting_screen = build_show_setting_screen_fn(
    state,
    Settings,
    SettingText,
    SETTINGS_ADJUSTABLE_INDEXES,
    READ_PARAMETER_OPTIONS,
    gauge,
    show_gauge,
)
apply_settings_to_runtime = build_apply_settings_to_runtime_fn(
    state,
    Settings,
    DisplayText,
    Units,
    parse_int,
    parse_float,
    temp_unit_label,
    refresh_setting_values,
)
adjust_setting_value = build_adjust_setting_value_fn(
    state,
    Settings,
    parse_float,
    temp_unit_label,
    Save_Config,
    CONF,
    update_reader_settings,
    refresh_setting_values,
)
toggle_speed_units = build_toggle_speed_units_fn(
    state,
    Settings,
    Save_Config,
    CONF,
    refresh_units,
    update_reader_settings,
)
toggle_temp_units = build_toggle_temp_units_fn(
    state,
    Settings,
    Save_Config,
    CONF,
    refresh_units,
    update_reader_settings,
    parse_float,
)
cycle_default_display = build_cycle_default_display_fn(
    state,
    Settings,
    DisplayText,
    Save_Config,
    CONF,
)
toggle_gauge_display_mode = build_toggle_gauge_display_mode_fn(
    state,
    Settings,
    Save_Config,
    CONF,
    refresh_setting_values,
)
toggle_read_parameter = build_toggle_read_parameter_fn(
    state,
    Settings,
    Save_Config,
    CONF,
    refresh_setting_values,
)
finalize_read_parameters_update = build_finalize_read_parameters_fn(
    state,
    Settings,
    update_reader_settings,
    refresh_setting_values,
)


def Show_Peak(idx: int) -> None:
    with state.acquire_lock():
        state.showing_peak = True
        stream_codes = list(state.stream_display_codes)
        stream_values = dict(state.stream_display_values)
        stream_peaks = dict(state.stream_peak_values)
        units_speed = state.units_speed
        units_temp = state.units_temp

    if idx < 0 or idx >= len(stream_codes):
        with state.acquire_lock():
            state.showing_peak = False
        return

    code = stream_codes[idx]
    label = read_parameter_title(code)
    unit = get_stream_unit(code, units_speed, units_temp)
    peak_value = float(stream_peaks.get(code, stream_values.get(code, 0.0)))
    minimum, maximum = get_stream_range(code, units_speed, units_temp)
    value_text = format_stream_value_text(code, peak_value, unit)
    show_gauge(
        f"{label} PEAK",
        peak_value,
        unit,
        minimum,
        maximum,
        value_text=value_text,
    )

    time.sleep(1.5)

    with state.acquire_lock():
        state.showing_peak = False


@lru_cache(maxsize=1)
def _list_body_font() -> Any:
    font_dir = Path(__file__).resolve().parent / "dependencies" / "Font"
    for font_name in ("Font02.ttf", "Font01.ttf", "Font00.ttf"):
        font_path = font_dir / font_name
        if not font_path.exists():
            continue
        try:
            return ImageFont.truetype(str(font_path), 18)
        except Exception:
            continue
    return ImageFont.load_default()


def show_mode_menu_screen(display_mode_enabled: bool, digital_mode_enabled: bool) -> None:
    with state.acquire_lock():
        mode_menu_index = state.mode_menu_index

    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title = "Select Mode"
    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    body_font = _list_body_font()
    start_y = 36
    bottom_margin = 18
    max_visible_rows = 5
    total_rows = len(MODE_MENU_ITEMS)
    visible_rows = min(max_visible_rows, total_rows)
    row_height = max(13, (height - start_y - bottom_margin) // max(1, visible_rows))
    visible_start = max(0, min(mode_menu_index - (visible_rows // 2), max(total_rows - visible_rows, 0)))
    visible_end = min(total_rows, visible_start + visible_rows)

    mode_enabled = [display_mode_enabled, True, True, digital_mode_enabled, True]

    for visible_row, idx in enumerate(range(visible_start, visible_end)):
        label = MODE_MENU_ITEMS[idx]
        y = start_y + (visible_row * row_height)
        is_selected = idx == mode_menu_index
        is_enabled = mode_enabled[idx]

        if is_selected:
            draw.rectangle((4, y + 3, width - 4, y + row_height + 1), fill=(24, 36, 52), outline=(90, 140, 190))

        pointer = ">" if is_selected else " "
        line = f"{pointer} {label}"
        if is_enabled:
            text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        else:
            text_color = (120, 120, 120)
        draw.text((8, y + 2), line, font=body_font, fill=text_color)

    footer = "Up/Down: Navigate  Select: Open"
    draw.text((8, height - 20), footer, font=body_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)


def send_activation_command(
    port_obj: Optional[serial.Serial],
    command_type: int,
    data_byte: int,
    demo_mode: bool = False,
) -> bool:
    return protocol_send_activation_command(
        port_obj,
        command_type,
        data_byte,
        demo_mode=demo_mode,
        log_index=Log_Index,
        write_log=WriteLog,
    )


def get_demo_values(elapsed_seconds: float) -> list[float]:
    rpm = 900.0 + 5000.0 * (0.6 + 0.6 * np.sin(elapsed_seconds * 1.6))
    maf = 0.6 + 3.6 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.1 + 1.2))
    temp = 120.0 + 45.0 * (0.5 + 2 * np.sin(elapsed_seconds + 1.4))
    o2 = 0.1 + 0.9 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.3 + 0.7))
    speed = 10.0 + 95.0 * (0.7 + 0.7 * np.sin(elapsed_seconds * 0.9))
    batt = 12.8 + 1.2 * (0.5 + 0.5 * np.sin(elapsed_seconds * 0.55 + 1.4))
    tps = 0.4 + 3.9 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.5 + 1.8))
    fueltemp = 100.0 + 20.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.2 + 1.6))
    iat = 0.5 + 0.45 * np.sin(elapsed_seconds * 1.4 + 0.9)
    egt = 300.0 + 400.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 0.8 + 2.1))
    inj = 2.0 + 48.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.4 + 0.4))
    tim = 5.0 + 32.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.0 + 2.0))
    aac = 8.0 + 62.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.3 + 2.3))
    afalpha = 0.5 + 0.45 * np.sin(elapsed_seconds * 1.2 + 0.3)

    return [rpm, maf, temp, o2, speed, batt, tps, fueltemp, iat, egt, inj, tim, aac, afalpha]


def pump_local_ui_events() -> bool:
    pump_fn = getattr(gauge.disp, "pump_events", None)
    if callable(pump_fn):
        try:
            return bool(pump_fn())
        except Exception:
            return False
    return True


def PortConnect(port_obj: object) -> Optional[serial.Serial]:
    WriteText("Connecting...", "Serial")
    try:
        return serial.Serial("/dev/ttyUSB0", 9600, timeout=None)
        # return serial.Serial("COM6", 9600, timeout=None) # For windows change COM6 to your port

    except serial.SerialException as exc:
        WriteLog(Log_Index, exc, "PortConnect - Serial port error")
        return None
    except Exception as exc:
        WriteLog(Log_Index, exc, "PortConnect - Unexpected error")
        return None


def ECU_Connect(port_obj: serial.Serial) -> bool:
    while True:
        try:
            if hasattr(port_obj, "reset_input_buffer"):
                port_obj.reset_input_buffer()
            else:
                flush_input = getattr(port_obj, "flushInput", None)
                if callable(flush_input):
                    flush_input()
            port_obj.write(bytes([0xFF, 0xFF, 0xEF]))
            time.sleep(0.1)
            if port_obj.read_all() == b"\x00\x00\x10":
                WriteText("Connected", "")
                return True
        except serial.SerialException as exc:
            WriteLog(Log_Index, exc, "ECU_Connect - Serial port error")
            time.sleep(0.5)
        except (OSError, TimeoutError) as exc:
            WriteLog(Log_Index, exc, "ECU_Connect - Read/write error")
            time.sleep(0.5)


R: Optional[Any] = None
PORT: Optional[serial.Serial] = None
demo_start_time = time.monotonic()
read_thread_active = False

apply_settings_to_runtime()

# Set up event-based button callbacks (must be done once before main loop)
setup_button_callbacks(ModeButton, SelectButton, UpButton, DownButton)

if DEMO_MODE:
    WriteText("DEMO MODE", "No ECU")
    read_thread_active = True
else:
    # Connect serial and ECU
    while PORT is None:
        PORT = PortConnect(PORT)
        time.sleep(0.1)

    ECU_Connected = ECU_Connect(PORT) if PORT is not None else False

    # Start background threads
    if ECU_Connected:
        R = ReadStream(port=PORT, daemon=True, settings=Settings)
        read_thread_active = True

# Main loop
try:
    while read_thread_active:
        selected_read_parameters = Settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS)
        selected_stream_codes = get_selected_stream_codes(selected_read_parameters)
        selected_stream_labels = [read_parameter_label(code) for code in selected_stream_codes]
        selected_digital_registers = get_selected_digital_registers(selected_read_parameters)

        with state.acquire_lock():
            state.stream_display_codes = list(selected_stream_codes)
            state.stream_display_labels = list(selected_stream_labels)

        if not pump_local_ui_events():
            read_thread_active = False
            break
        process_button_events(
            state,
            PORT,
            DEMO_MODE,
            selected_stream_codes,
            selected_stream_labels,
            SettingText,
            READ_PARAMETER_CODES,
            ACTIVE_TEST_ITEMS,
            selected_digital_registers,
            SETTINGS_ADJUSTABLE_INDEXES,
            DISPLAY_MODE,
            DTC_MODE,
            SETTINGS_MODE,
            ACTIVE_TEST_MODE,
            DIGITAL_BITS_MODE,
            MODE_MENU,
            MODE_MENU_TARGETS,
            MODE_COUNT,
            Show_Peak,
            adjust_setting_value,
            adjust_active_test_value,
            run_active_test_action,
            refresh_dtc_codes_for_buttons,
            CLEAR_DTC_CODES,
            send_activation_command,
            temp_unit_label,
            READ_DTC_CODES,
            toggle_speed_units,
            toggle_temp_units,
            cycle_default_display,
            toggle_gauge_display_mode,
            toggle_read_parameter,
            finalize_read_parameters_update,
        )

        selected_read_parameters = Settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS)
        selected_stream_codes = get_selected_stream_codes(selected_read_parameters)
        selected_stream_labels = [read_parameter_label(code) for code in selected_stream_codes]
        selected_digital_registers = get_selected_digital_registers(selected_read_parameters)

        with state.acquire_lock():
            state.stream_display_codes = list(selected_stream_codes)
            state.stream_display_labels = list(selected_stream_labels)

        # Refresh digital register values for digital bit pages.
        if DEMO_MODE:
            elapsed = time.monotonic() - demo_start_time
            update_digital_registers_from_demo(state, elapsed)
        elif R is not None:
            update_digital_registers_from_reader(state, R, parse_int)

        # Get current state for this iteration
        with state.acquire_lock():
            current_mode = state.current_mode
            display_index = state.display_index
            showing_peak = state.showing_peak

        if current_mode == DISPLAY_MODE and selected_stream_codes:
            if display_index not in range(len(selected_stream_codes)):
                with state.acquire_lock():
                    state.display_index = 0
                    display_index = state.display_index

        if current_mode == DIGITAL_BITS_MODE and selected_digital_registers:
            with state.acquire_lock():
                if state.digital_page_index >= len(selected_digital_registers):
                    state.digital_page_index %= len(selected_digital_registers)
        
        # Update sensor data if in DISPLAY_MODE
        if current_mode == DISPLAY_MODE and not showing_peak and (DEMO_MODE or R is not None):
            if not selected_stream_codes:
                show_gauge(
                    "Data Stream",
                    0.0,
                    "",
                    0.0,
                    1.0,
                    show_needle=False,
                    show_dial=False,
                    value_text="No Read Parameters Selected",
                )
            else:
                if DEMO_MODE:
                    elapsed = time.monotonic() - demo_start_time
                    demo_value_map = build_demo_stream_value_map(elapsed)
                    with state.acquire_lock():
                        speed_correction = state.speed_correction
                    current_value_map = {
                        code: get_stream_value_for_code(code, None, demo_value_map, speed_correction)
                        for code in selected_stream_codes
                    }
                    rpm_value = float(current_value_map.get(0x01, 0.0))
                    temp_value = float(current_value_map.get(0x08, 0.0))
                else:
                    reader = R
                    if reader is None:
                        time.sleep(0.05)
                        continue
                    with state.acquire_lock():
                        speed_correction = state.speed_correction
                    current_value_map = {
                        code: get_stream_value_for_code(code, reader, {}, speed_correction)
                        for code in selected_stream_codes
                    }
                    rpm_value = float(current_value_map.get(0x01, 0.0)) # used for RPM warning check
                    temp_value = float(current_value_map.get(0x08, 0.0)) # used for coolant temp warning check

                state.update_stream_peaks(current_value_map)

                with state.acquire_lock():
                    state.stream_display_values = dict(current_value_map)
                    current_display_index = state.display_index
                    if current_display_index >= len(selected_stream_codes):
                        current_display_index = 0
                        state.display_index = 0
                    current_display_code = selected_stream_codes[current_display_index]
                    current_display_value = float(current_value_map.get(current_display_code, 0.0))

                current_title = read_parameter_title(current_display_code)
                current_unit = get_stream_unit(current_display_code, Units_Speed, Units_Temp)
                minimum, maximum = get_stream_range(current_display_code, Units_Speed, Units_Temp)
                current_display_text = format_stream_value_text(current_display_code, current_display_value, current_unit)
                now = time.monotonic()

                with state.acquire_lock():
                    rpm_warning = state.rpm_warning
                    coolant_warning = state.coolant_warning
                    gauge_display_mode = str(state.gauge_display_mode)

                warning_lines: list[str] = []
                if rpm_value > rpm_warning:
                    warning_lines.append("REV LIMIT!")
                if temp_value > coolant_warning:
                    warning_lines.append("OVERHEAT!")

                warning_overlay_text = "\n".join(warning_lines)

                render_interval = 1.0 / DISPLAY_TARGET_FPS
                needs_render = (
                    current_display_code != getattr(state, "last_display_code", None)
                    or current_unit != state.last_display_unit
                    or abs(current_display_value - state.last_display_value) >= DISPLAY_MIN_DELTA
                    or warning_overlay_text != state.last_warning_overlay_text
                    or (now - state.last_display_render_time) >= render_interval
                )

                if needs_render:
                    show_dial = gauge_display_mode != "Value Only"
                    show_gauge(
                        current_title,
                        current_display_value,
                        current_unit,
                        minimum,
                        maximum,
                        show_needle=show_dial,
                        show_dial=show_dial,
                        value_text=current_display_text,
                        warning_lines=warning_lines,
                    )
                    with state.acquire_lock():
                        state.last_display_render_time = now
                        state.last_display_index = current_display_index
                        state.last_display_code = current_display_code
                        state.last_display_value = current_display_value
                        state.last_display_unit = current_unit
                        state.last_warning_overlay_text = warning_overlay_text

        elif current_mode == DTC_MODE:
            show_dtc_screen(state, show_gauge, DTC_CODE_TITLES)

        elif current_mode == SETTINGS_MODE:
            show_setting_screen()

        elif current_mode == ACTIVE_TEST_MODE:
            show_active_test_screen(state, gauge, show_gauge, temp_unit_label)

        elif current_mode == DIGITAL_BITS_MODE:
            show_digital_bits_screen(state, gauge, selected_digital_registers)

        elif current_mode == MODE_MENU:
            show_mode_menu_screen(bool(selected_stream_codes), bool(selected_digital_registers))

        if not pump_local_ui_events():
            read_thread_active = False
            break
        time.sleep(0.01)
finally:
    gauge.close()