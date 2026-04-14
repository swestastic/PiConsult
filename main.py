import os
import argparse
import queue
import time
import serial
import threading
from typing import Optional, Any

from dependencies.hardware.buttons import (
    ButtonContext,
    button_event_queue,
    process_buttons as process_button_events,
    setup_button_callbacks,
)
from dependencies.modes.settings import Load_Config, Save_Config
from dependencies.modes.data_stream import ReadStream, get_stream_value_for_code
from dependencies.logs import Create_Log_File, WriteLog
from dependencies.local_ui import LocalButton, local_ui_requested
from dependencies.modes.active_test import (
    ACTIVE_TEST_ITEMS,
    adjust_active_test_value,
    run_active_test_action,
    show_active_test_screen,
)
from dependencies.consult.registers import (
    DEFAULT_READ_PARAMETERS,
    READ_PARAMETER_OPTIONS,
    get_selected_digital_registers,
    get_selected_stream_codes,
    get_stream_unit,
    read_parameter_label,
    read_parameter_title,
)
from dependencies.modes.settings import (
    build_settings_callbacks,
)
from dependencies.consult.protocol import (
    send_activation_command as protocol_send_activation_command,
)
from dependencies.modes.digital_register import (
    show_digital_bits_screen,
    update_digital_registers_from_demo,
    update_digital_registers_from_reader,
)
from dependencies.modes.dtc import (
    DTC_CODE_TITLES,
    build_clear_dtc_codes_fn,
    build_read_dtc_codes_fn,
    refresh_dtc_codes_for_buttons,
    show_dtc_screen,
)
from dependencies.demo import build_demo_stream_snapshot, elapsed_since, initialize_demo_mode
from dependencies.config import (
    MODE_BUTTON_PIN,
    SELECT_BUTTON_PIN,
    UP_BUTTON_PIN,
    DOWN_BUTTON_PIN,
    BUTTON_HOLD_TIME_SECONDS,
    BUTTON_BOUNCE_TIME_SECONDS,
    FOOTER_FONT_SIZE,
    MENU_FONT_SIZE,
    MENU_TITLE_FONT_SIZE,
    GAUGE_RANGE_FONT_SIZE,
    GAUGE_VALUE_FONT_SIZE,
    VALUE_ONLY_FONT_SIZE,
)

try:
    from gpiozero import Button as GpioButton  # type: ignore
except Exception:
    GpioButton = None

try:  # Prefer PiGPIO when available, but do not require it.
    from gpiozero import Device as GpioDevice  # type: ignore
    from gpiozero.pins.pigpio import PiGPIOFactory  # type: ignore

    GpioDevice.pin_factory = PiGPIOFactory()  # type: ignore
except Exception:
    # Fall back to gpiozero's default pin factory (or LocalButton on desktop).
    pass

from dependencies.modes.data_stream import GaugeNeedleDisplay, get_stream_range, show_gauge as render_gauge
from dependencies.common.ui import draw_scrollable_menu_screen
from dependencies.common.helpers import parse_float, parse_int, speed_unit_label, temp_unit_label


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
CONF = os.path.join(os.path.dirname(__file__), "dependencies", "config", "configJSON.json")
Settings = Load_Config(CONF)
Settings.setdefault("Speed_Correction", 1.0)
Settings.setdefault("Gauge_Display_Mode", "Gauge + Value")
Settings.setdefault("Read_Parameters", list(DEFAULT_READ_PARAMETERS))
Settings.pop("Footer_Font_Size", None)
Settings.pop("Menu_Font_Size", None)
Settings.pop("Menu_Title_Font_Size", None)
Settings.pop("Gauge_Range_Font_Size", None)
Settings.pop("Gauge_Value_Font_Size", None)
Settings.pop("Value_Only_Font_Size", None)
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
    footer_font_size=FOOTER_FONT_SIZE,
    menu_font_size=MENU_FONT_SIZE,
    menu_title_font_size=MENU_TITLE_FONT_SIZE,
    gauge_range_font_size=GAUGE_RANGE_FONT_SIZE,
    gauge_value_font_size=GAUGE_VALUE_FONT_SIZE,
    value_only_font_size=VALUE_ONLY_FONT_SIZE,
    backlight_percent=GAUGE_BACKLIGHT,
    spi_freq_hz=GAUGE_SPI_FREQ,
    rotation_degrees=GAUGE_ROTATION,
)


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
    render_gauge(
        gauge,
        title,
        value,
        unit,
        minimum,
        maximum,
        show_needle=show_needle,
        show_dial=show_dial,
        show_value_text=show_value_text,
        value_text=value_text,
        warning_text=warning_text,
        warning_lines=warning_lines,
        footer_text=footer_text,
    )

DISPLAY_TARGET_FPS = max(1.0, parse_float(os.getenv("CONSULT_DISPLAY_FPS", "30"), 30.0))
DISPLAY_MIN_DELTA = max(0.0, parse_float(os.getenv("CONSULT_DISPLAY_MIN_DELTA", "0.25"), 0.25))
PORT_CONNECT_MAX_ATTEMPTS = 5
ECU_CONNECT_MAX_ATTEMPTS = 5

# Buttons
ModeButton = Button(MODE_BUTTON_PIN, hold_time=BUTTON_HOLD_TIME_SECONDS, bounce_time=BUTTON_BOUNCE_TIME_SECONDS)
SelectButton = Button(SELECT_BUTTON_PIN, hold_time=BUTTON_HOLD_TIME_SECONDS, bounce_time=BUTTON_BOUNCE_TIME_SECONDS)
UpButton = Button(UP_BUTTON_PIN, hold_time=BUTTON_HOLD_TIME_SECONDS, bounce_time=BUTTON_BOUNCE_TIME_SECONDS)
DownButton = Button(DOWN_BUTTON_PIN, hold_time=BUTTON_HOLD_TIME_SECONDS, bounce_time=BUTTON_BOUNCE_TIME_SECONDS)

# Mode constants
DISPLAY_MODE = 0
DTC_MODE = 1
SETTINGS_MODE = 2
ACTIVE_TEST_MODE = 3
DIGITAL_BITS_MODE = 4
MODE_MENU = 5

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
        self.last_display_text = ""
        self.last_display_unit = ""
        self.last_display_needle_bucket = -1
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


settings_callbacks = build_settings_callbacks(
    state,
    Settings,
    DisplayText,
    Units,
    SettingText,
    SETTINGS_ADJUSTABLE_INDEXES,
    READ_PARAMETER_OPTIONS,
    gauge,
    show_gauge,
    parse_int,
    parse_float,
    temp_unit_label,
    Save_Config,
    CONF,
    update_reader_settings,
)

refresh_setting_values = settings_callbacks["refresh_setting_values"]
refresh_units = settings_callbacks["refresh_units"]
show_setting_screen = settings_callbacks["show_setting_screen"]
apply_settings_to_runtime = settings_callbacks["apply_settings_to_runtime"]
adjust_setting_value = settings_callbacks["adjust_setting_value"]
toggle_speed_units = settings_callbacks["toggle_speed_units"]
toggle_temp_units = settings_callbacks["toggle_temp_units"]
cycle_default_display = settings_callbacks["cycle_default_display"]
toggle_gauge_display_mode = settings_callbacks["toggle_gauge_display_mode"]
toggle_read_parameter = settings_callbacks["toggle_read_parameter"]
finalize_read_parameters_update = settings_callbacks["finalize_read_parameters"]


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


def show_mode_menu_screen(display_mode_enabled: bool, digital_mode_enabled: bool) -> None:
    with state.acquire_lock():
        mode_menu_index = state.mode_menu_index

    mode_enabled = [display_mode_enabled, True, True, digital_mode_enabled, True]

    def _line_builder(label: str, idx: int, is_selected: bool) -> tuple[str, tuple[int, int, int]]:
        is_enabled = mode_enabled[idx]
        pointer = ">" if is_selected else " "
        line = f"{pointer} {label}"
        if is_enabled:
            text_color = (240, 240, 240) if is_selected else (165, 165, 165)
        else:
            text_color = (120, 120, 120)
        return line, text_color

    footer = "Up/Dn: Navigate  Select: Open"
    draw_scrollable_menu_screen(gauge, "Select Mode", MODE_MENU_ITEMS, mode_menu_index, _line_builder, footer)


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


def pump_local_ui_events() -> bool:
    pump_fn = getattr(gauge.disp, "pump_events", None)
    if callable(pump_fn):
        try:
            return bool(pump_fn())
        except Exception:
            return False
    return True


def PortConnect(max_attempts: int = PORT_CONNECT_MAX_ATTEMPTS) -> Optional[serial.Serial]:
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        WriteText("Connecting...", f"Cable {attempt}/{attempts}")
        try:
            return serial.Serial("/dev/ttyUSB0", 9600, timeout=None)
            # return serial.Serial("COM6", 9600, timeout=None) # For windows change COM6 to your port

        except serial.SerialException as exc:
            WriteLog(Log_Index, exc, "PortConnect - Serial port error")
        except Exception as exc:
            WriteLog(Log_Index, exc, "PortConnect - Unexpected error")

        time.sleep(0.35)

    WriteText("Serial Cable", "Not Found")
    return None


def ECU_Connect(port_obj: serial.Serial, max_attempts: int = ECU_CONNECT_MAX_ATTEMPTS) -> bool:
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        WriteText("Connecting...", f"ECU {attempt}/{attempts}")
        try:
            if hasattr(port_obj, "reset_input_buffer"):
                port_obj.reset_input_buffer()
            else:
                flush_input = getattr(port_obj, "flushInput", None)
                if callable(flush_input):
                    flush_input()
            port_obj.write(bytes([0xFF, 0xFF, 0xEF]))
            time.sleep(0.1)
            response = port_obj.read_all() or b""
            if b"\x00\x00\x10" in response:
                WriteText("Connected", "")
                return True
        except serial.SerialException as exc:
            WriteLog(Log_Index, exc, "ECU_Connect - Serial port error")
        except (OSError, TimeoutError) as exc:
            WriteLog(Log_Index, exc, "ECU_Connect - Read/write error")

        time.sleep(0.35)

    WriteText("ECU Connect", "Failed")
    return False


def _clear_button_event_queue() -> None:
    while True:
        try:
            button_event_queue.get_nowait()
        except queue.Empty:
            break


def prompt_connect_retry_or_demo(title: str) -> str:
    _clear_button_event_queue()
    show_gauge(
        title,
        0.0,
        "Select: Retry",
        0.0,
        1.0,
        show_needle=False,
        show_dial=False,
        show_value_text=False,
        footer_text="Down: Demo Mode",
    )

    while True:
        if not pump_local_ui_events():
            return "exit"

        try:
            event = button_event_queue.get_nowait()
        except queue.Empty:
            time.sleep(0.02)
            continue

        if event == "select":
            return "retry"
        if event == "down":
            return "demo"


def _get_selected_parameters() -> tuple[list[int], list[str], list[int]]:
    selected_read_parameters = Settings.get("Read_Parameters", DEFAULT_READ_PARAMETERS)
    selected_stream_codes = get_selected_stream_codes(selected_read_parameters)
    selected_stream_labels = [read_parameter_label(code) for code in selected_stream_codes]
    selected_digital_registers = get_selected_digital_registers(selected_read_parameters)
    return selected_stream_codes, selected_stream_labels, selected_digital_registers


R: Optional[Any] = None
PORT: Optional[serial.Serial] = None
demo_start_time = 0.0
read_thread_active = False

apply_settings_to_runtime()

# Set up event-based button callbacks (must be done once before main loop)
setup_button_callbacks(ModeButton, SelectButton, UpButton, DownButton)

if DEMO_MODE:
    demo_start_time = initialize_demo_mode(WriteText)
    read_thread_active = True
else:
    # Connect serial and ECU, then allow user to choose retry/demo after repeated failures.
    while True:
        PORT = PortConnect(max_attempts=PORT_CONNECT_MAX_ATTEMPTS)
        if PORT is None:
            retry_action = prompt_connect_retry_or_demo("Cable Not Found")
            if retry_action == "retry":
                continue
            if retry_action == "demo":
                DEMO_MODE = True
                demo_start_time = initialize_demo_mode(WriteText)
                read_thread_active = True
            break

        ecu_connected = ECU_Connect(PORT, max_attempts=ECU_CONNECT_MAX_ATTEMPTS)
        if ecu_connected:
            R = ReadStream(port=PORT, daemon=True, settings=Settings)
            read_thread_active = True
            break

        retry_action = prompt_connect_retry_or_demo("ECU Not Found")

        try:
            PORT.close()
        except Exception:
            pass
        PORT = None

        if retry_action == "retry":
            continue
        if retry_action == "demo":
            DEMO_MODE = True
            demo_start_time = initialize_demo_mode(WriteText)
            read_thread_active = True
        break

# Main loop
try:
    selected_stream_codes, selected_stream_labels, selected_digital_registers = _get_selected_parameters()

    while read_thread_active:
        with state.acquire_lock():
            state.stream_display_codes = list(selected_stream_codes)
            state.stream_display_labels = list(selected_stream_labels)

        if not pump_local_ui_events():
            read_thread_active = False
            break
        button_context = ButtonContext(
            selected_display_indices=selected_stream_codes,
            setting_text=SettingText,
            read_parameter_codes=READ_PARAMETER_CODES,
            active_test_items=ACTIVE_TEST_ITEMS,
            selected_digital_registers=selected_digital_registers,
            settings_adjustable_indexes=SETTINGS_ADJUSTABLE_INDEXES,
            display_mode=DISPLAY_MODE,
            dtc_mode=DTC_MODE,
            settings_mode=SETTINGS_MODE,
            active_test_mode=ACTIVE_TEST_MODE,
            digital_bits_mode=DIGITAL_BITS_MODE,
            mode_menu_mode=MODE_MENU,
            mode_menu_targets=MODE_MENU_TARGETS,
            show_peak_fn=Show_Peak,
            adjust_setting_value_fn=adjust_setting_value,
            adjust_active_test_value_fn=adjust_active_test_value,
            run_active_test_action_fn=run_active_test_action,
            update_dtc_codes_from_ecu_fn=refresh_dtc_codes_for_buttons,
            clear_dtc_codes_fn=CLEAR_DTC_CODES,
            send_activation_command_fn=send_activation_command,
            temp_unit_label_fn=temp_unit_label,
            read_dtc_codes_fn=READ_DTC_CODES,
            on_speed_units_toggle_fn=toggle_speed_units,
            on_temp_units_toggle_fn=toggle_temp_units,
            on_default_display_cycle_fn=cycle_default_display,
            on_gauge_display_mode_toggle_fn=toggle_gauge_display_mode,
            on_read_parameter_toggle_fn=toggle_read_parameter,
            on_read_parameters_finalize_fn=finalize_read_parameters_update,
        )
        had_button_events = not button_event_queue.empty()
        if had_button_events:
            process_button_events(state, PORT, DEMO_MODE, button_context)
            selected_stream_codes, selected_stream_labels, selected_digital_registers = _get_selected_parameters()

        with state.acquire_lock():
            state.stream_display_codes = list(selected_stream_codes)
            state.stream_display_labels = list(selected_stream_labels)

        # Refresh digital register values for digital bit pages.
        if DEMO_MODE:
            elapsed = elapsed_since(demo_start_time)
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
                    with state.acquire_lock():
                        units_speed = state.units_speed
                        units_temp = state.units_temp
                        elapsed, demo_value_map = build_demo_stream_snapshot(demo_start_time, units_speed, units_temp)
                        speed_correction = state.speed_correction
                    current_value_map = {
                        code: get_stream_value_for_code(code, None, demo_value_map, speed_correction, units_temp)
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
                        units_temp = state.units_temp
                    current_value_map = {
                        code: get_stream_value_for_code(code, reader, {}, speed_correction, units_temp)
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

                needle_bucket = int(round(gauge.value_to_angle(current_display_value) * 2.0)) if gauge_display_mode != "Value Only" else -1
                needs_render = (
                    current_display_code != getattr(state, "last_display_code", None)
                    or current_unit != state.last_display_unit
                    or current_display_text != state.last_display_text
                    or abs(current_display_value - state.last_display_value) >= DISPLAY_MIN_DELTA
                    or needle_bucket != state.last_display_needle_bucket
                    or warning_overlay_text != state.last_warning_overlay_text
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
                        state.last_display_text = current_display_text
                        state.last_display_unit = current_unit
                        state.last_display_needle_bucket = needle_bucket
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