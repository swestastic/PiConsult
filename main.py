import os
import argparse
import time
import datetime
from functools import partial
import serial
import threading
import socket
import subprocess
import numpy as np
from typing import Optional, Any

from dependencies import config
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
from dependencies.settings_mode import (
    build_adjust_setting_value_fn,
    build_apply_settings_to_runtime_fn,
    build_cycle_default_display_fn,
    build_refresh_setting_values_fn,
    build_refresh_units_fn,
    build_show_setting_screen_fn,
    build_toggle_speed_units_fn,
    build_toggle_temp_units_fn,
)
from dependencies.consult_protocol import (
    build_clear_dtc_codes_fn,
    build_read_dtc_codes_fn,
    send_activation_command as protocol_send_activation_command,
)
from dependencies.digital_mode import (
    DIGITAL_REGISTER_ORDER,
    show_digital_bits_screen,
    update_digital_registers_from_demo,
    update_digital_registers_from_reader,
)
from dependencies.dtc_mode import (
    refresh_dtc_codes_for_buttons,
    show_dtc_screen,
    update_dtc_codes_from_ecu,
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


def get_local_ip() -> str:
    # 1) Prefer interface IPs (works even without internet route).
    for interface_name in (os.getenv("CONSULT_BOX_WLAN", "wlan0"), "eth0"):
        try:
            result = subprocess.run(
                ["ip", "-4", "-o", "addr", "show", "dev", interface_name],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if "inet" in parts:
                    ip_with_mask = parts[parts.index("inet") + 1]
                    ip_addr = ip_with_mask.split("/", 1)[0]
                    if ip_addr:
                        return ip_addr
        except (subprocess.TimeoutExpired, ValueError, OSError):
            # Interface may not exist, timeout, or parsing error - try next one
            pass

    # 2) Fallback to route-based discovery (requires reachable route).
    for probe_host in ("8.8.8.8", "1.1.1.1"):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.0)
            sock.connect((probe_host, 80))
            return sock.getsockname()[0]
        except OSError:
            # Offline/no route is valid in AP mode.
            pass
        except Exception as exc:
            WriteLog(Log_Index, exc, "Getting local IP address")
        finally:
            try:
                if sock is not None:
                    sock.close()
            except OSError:
                # Socket already closed or other socket error
                pass

    return "N/A"


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


def get_metric_range(index: int) -> tuple[float, float]:
    speed_max = 150.0 if speed_unit_label(Units_Speed) == "MPH" else 240.0
    temp_max = 260.0 if temp_unit_label(Units_Temp) == "F" else 130.0

    ranges = [
        (0.0, 8000.0), # RPM
        (0.0, speed_max), # SPEED
        (0.0, 5.0), # MAF
        (0.0, 100.0), # AAC
        (20.0, temp_max), # TEMP
        (6.0, 16.0), # BATT
        (0.0, 100.0), # INJ
        (0.0, 70.0), # TIM
        (0.0, 5.0), # TPS
    ]
    return ranges[index]


INT_METRIC_INDEXES = {0, 1, 3, 4, 7}  # RPM, SPEED, AAC, TEMP, TIM
DEC_1_METRIC_INDEXES = {5, 6}  # BATT, INJ


def format_metric_value(index: int, value: float) -> float:
    """Format metric values for display: selected metrics as ints, others to 2 decimals."""
    if index in INT_METRIC_INDEXES:
        return float(int(round(value)))
    if index in DEC_1_METRIC_INDEXES:
        return float(round(value, 1))
    return float(round(value, 2))


def format_metric_text(index: int, value: float) -> str:
    if index in INT_METRIC_INDEXES:
        return f"{int(round(value))}"
    if index in DEC_1_METRIC_INDEXES:
        return f"{value:.1f}"
    return f"{value:.2f}"


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
    )


def debug_log(context: str, message: object) -> None:
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    formatted = f"[{timestamp}] {context}: {message}"
    print(formatted)
    try:
        WriteLog(Log_Index, formatted, "debug")
    except (IOError, OSError):
        # Log file write failed, but don't crash - message already on stdout
        pass


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
CONF = "dependencies/configJSON.json"
Settings = Load_Config(CONF)
Settings.setdefault("Speed_Correction", 1.0)
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
Injector_Size = parse_float(Settings.get("Injector_Size", 0), 0)

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
ModeButton = Button(17, hold_time=0.5)
SelectButton = Button(26, hold_time=0.5)
UpButton = Button(23, hold_time=0.5)
DownButton = Button(16, hold_time=0.5)

# Mode constants
DISPLAY_MODE = 0
DTC_MODE = 1
SETTINGS_MODE = 2
ACTIVE_TEST_MODE = 3
DIGITAL_BITS_MODE = 4
MODE_COUNT = 5

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
    "Injector Size",
    "Default Display",
    "RPM Warning",
    "Coolant Warning",
]

SETTING_SPEED_UNITS = 0
SETTING_TEMP_UNITS = 1
SETTING_SPEED_CORRECTION = 2
SETTING_INJECTOR_SIZE = 3
SETTING_DEFAULT_DISPLAY = 4
SETTING_RPM_WARNING = 5
SETTING_COOLANT_WARNING = 6
SETTINGS_ADJUSTABLE_INDEXES = {
    SETTING_SPEED_CORRECTION,
    SETTING_INJECTOR_SIZE,
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
        self.display_values = np.zeros(len(DisplayText))
        self.peak_values = np.zeros(len(DisplayText))
        
        # Settings state
        self.units_speed = units_speed
        self.units_temp = units_temp
        self.default_display = default_display
        self.speed_correction = Speed_Correction
        self.rpm_warning = rpm_warning
        self.coolant_warning = coolant_warning
        
        # DTC state
        self.dtc_index = 0
        self.dtc_codes: list[int] = []
        self.dtc_status_message = ""
        self.dtc_status_until = 0.0
        self.dtc_clear_confirm_active = False
        self.dtc_clear_confirm_yes = False
        
        # Settings menu state
        self.setting_index = 0
        self.setting_values = [
            speed_unit_label(units_speed),
            temp_unit_label(units_temp),
            f"{Speed_Correction:.2f}",
            Injector_Size,
            DisplayText[default_display],
            f"{int(round(rpm_warning))} RPM",
            f"{int(round(coolant_warning))} {temp_unit_label(units_temp)}",
        ]
        self.setting_editing = False

        # Active test mode state
        self.active_test_index = 0
        self.active_test_editing = False
        self.active_test_status_message = ""
        self.active_test_status_until = 0.0
        self.active_test_coolant_c = 85
        self.active_test_coolant_override_active = False
        self.active_test_fuel_injection_percent = 100
        self.active_test_timing_offset_deg = 0
        self.active_test_iaac_offset_steps = 0
        self.active_test_power_balance_cursor = 0
        self.active_test_power_balance_cylinder_off = 0
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
        self.last_display_value = 0.0
        self.last_display_unit = ""
        self.last_warning_render_time = 0.0
        self.last_warning_overlay_text = ""
        
        # Thread control state
        self.read_thread_active = False
        self.showing_peak = False

    def update_display_values(self, values: np.ndarray) -> None:
        """Thread-safe update of display values and peaks."""
        with self._lock:
            self.display_values[:] = values
            self.peak_values[:] = np.maximum(self.peak_values, self.display_values)

    def get_display_values(self) -> np.ndarray:
        """Thread-safe read of display values."""
        with self._lock:
            return self.display_values.copy()

    def get_peak_values(self) -> np.ndarray:
        """Thread-safe read of peak values."""
        with self._lock:
            return self.peak_values.copy()

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
    SettingText,
    SETTINGS_ADJUSTABLE_INDEXES,
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


def Show_Peak(idx: int) -> None:
    with state.acquire_lock():
        state.showing_peak = True
        peak_val = float(state.peak_values[idx])
    
    minimum, maximum = get_metric_range(idx)
    show_gauge(
        f"{DisplayText[idx]} PEAK",
        format_metric_value(idx, peak_val),
        Units[idx],
        minimum,
        maximum,
    )
    time.sleep(1.5)
    
    with state.acquire_lock():
        state.showing_peak = False


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
    speed = 10.0 + 95.0 * (0.7 + 0.7 * np.sin(elapsed_seconds * 0.9))
    maf = 0.6 + 3.6 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.1 + 1.2))
    aac = 8.0 + 62.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.3 + 2.3))
    temp = 120.0 + 45.0 * (0.5 + 2 * np.sin(elapsed_seconds + 1.4))
    batt = 12.8 + 1.2 * (0.5 + 0.5 * np.sin(elapsed_seconds * 0.55 + 1.4))
    inj = 2.0 + 48.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.4 + 0.4))
    tim = 5.0 + 32.0 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.0 + 2.0))
    tps = 0.4 + 3.9 * (0.5 + 0.5 * np.sin(elapsed_seconds * 1.5 + 1.8))

    return [rpm, speed, maf, aac, temp, batt, inj, tim, tps]


def pump_local_ui_events() -> bool:
    pump_fn = getattr(gauge.disp, "pump_events", None)
    if callable(pump_fn):
        try:
            return bool(pump_fn())
        except Exception:
            return False
    return True


def PortConnect(port_obj: object, ip_addr: str) -> tuple[Optional[serial.Serial], str]:
    WriteText("Connecting...", ip_addr)
    try:
        return serial.Serial("/dev/ttyUSB0", 9600, timeout=None), ip_addr
    except serial.SerialException as exc:
        WriteLog(Log_Index, exc, "PortConnect - Serial port error")
        return None, ip_addr
    except Exception as exc:
        WriteLog(Log_Index, exc, "PortConnect - Unexpected error")
        return None, ip_addr


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

update_dtc_codes_from_ecu(
    state,
    None,
    demo_mode=DEMO_MODE,
    read_dtc_codes_fn=READ_DTC_CODES,
)

# Set up event-based button callbacks (must be done once before main loop)
setup_button_callbacks(ModeButton, SelectButton, UpButton, DownButton)

if DEMO_MODE:
    WriteText("DEMO MODE", "No ECU")
    read_thread_active = True
else:
    # Connect serial and ECU
    IPAddr = get_local_ip()
    while PORT is None:
        PORT, IPAddr = PortConnect(PORT, IPAddr)
        time.sleep(0.1)

    ECU_Connected = ECU_Connect(PORT) if PORT is not None else False

    # Start background threads
    if ECU_Connected:
        R = ReadStream(port=PORT, daemon=True, settings=Settings)
        update_dtc_codes_from_ecu(
            state,
            PORT,
            demo_mode=False,
            read_dtc_codes_fn=READ_DTC_CODES,
        )
        read_thread_active = True

# Main loop
try:
    while read_thread_active:
        if not pump_local_ui_events():
            read_thread_active = False
            break
        process_button_events(
            state,
            PORT,
            DEMO_MODE,
            DisplayText,
            SettingText,
            ACTIVE_TEST_ITEMS,
            DIGITAL_REGISTER_ORDER,
            SETTINGS_ADJUSTABLE_INDEXES,
            DISPLAY_MODE,
            DTC_MODE,
            SETTINGS_MODE,
            ACTIVE_TEST_MODE,
            DIGITAL_BITS_MODE,
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
        )

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
        
        # Update sensor data if in DISPLAY_MODE
        if current_mode == DISPLAY_MODE and not showing_peak and (DEMO_MODE or R is not None):
            if DEMO_MODE:
                elapsed = time.monotonic() - demo_start_time
                display_values = get_demo_values(elapsed)
                display_values = apply_active_test_effects_to_demo_values(display_values, state, temp_unit_label)
                with state.acquire_lock():
                    speed_correction = state.speed_correction
                display_values[1] = float(display_values[1] * speed_correction)
                state.update_display_values(np.array(display_values))
                rpm_value = float(display_values[0])
                temp_value = float(display_values[4])
            else:
                reader = R
                if reader is None:
                    time.sleep(0.05)
                    continue
                with state.acquire_lock():
                    speed_correction = state.speed_correction
                display_values = np.array([
                    int(reader.RPM_Value),
                    float(reader.SPEED_Value) * speed_correction,
                    reader.MAF_Value,
                    reader.AAC_Value,
                    int(reader.TEMP_Value),
                    reader.BATT_Value,
                    reader.INJ_Value,
                    int(reader.TIM_Value),
                    reader.TPS_Value,
                ])
                state.update_display_values(display_values)
                rpm_value = float(reader.RPM_Value)
                temp_value = float(reader.TEMP_Value)

            with state.acquire_lock():
                current_display_index = state.display_index
                current_display_value = float(state.display_values[current_display_index])

            current_display_value = format_metric_value(current_display_index, current_display_value)
            current_display_text = format_metric_text(current_display_index, current_display_value)
            
            current_title = DisplayText[current_display_index]
            current_unit = Units[current_display_index]
            minimum, maximum = get_metric_range(current_display_index)
            now = time.monotonic()

            with state.acquire_lock():
                rpm_warning = state.rpm_warning
                coolant_warning = state.coolant_warning
                units_temp = state.units_temp

            warning_lines: list[str] = []
            if temp_value > coolant_warning:
                warning_lines.append("OVERHEAT!")
            if rpm_value > rpm_warning:
                warning_lines.append("REV LIMIT!")

            warning_overlay_text = "\n".join(warning_lines)

            render_interval = 1.0 / DISPLAY_TARGET_FPS
            needs_render = (
                current_display_index != state.last_display_index
                or current_unit != state.last_display_unit
                or abs(current_display_value - state.last_display_value) >= DISPLAY_MIN_DELTA
                or warning_overlay_text != state.last_warning_overlay_text
                or (now - state.last_display_render_time) >= render_interval
            )

            if needs_render:
                show_gauge(
                    current_title,
                    current_display_value,
                    current_unit,
                    minimum,
                    maximum,
                    value_text=current_display_text,
                    warning_lines=warning_lines,
                )
                with state.acquire_lock():
                    state.last_display_render_time = now
                    state.last_display_index = current_display_index
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
            show_digital_bits_screen(state, gauge)

        if not pump_local_ui_events():
            read_thread_active = False
            break
        time.sleep(0.01)
finally:
    gauge.close()