from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


MAX_READ_PARAMETERS = 20


@dataclass(frozen=True)
class ReadParameterOption:
    code: int
    label: str
    title: str
    unit: str


READ_PARAMETER_OPTIONS: list[ReadParameterOption] = [
    ReadParameterOption(0x01, "CAS RPM", "RPM", "RPM"),

    ReadParameterOption(0x05, "MAF Voltage", "MAF", "V"),
    ReadParameterOption(0x07, "RH MAF Voltage", "RH MAF", "V"),

    ReadParameterOption(0x08, "Coolant Temp", "TEMP", "TEMP"),

    ReadParameterOption(0x09, "LH O2 Voltage", "O2", "%"),
    ReadParameterOption(0x0A, "RH O2 Voltage", "RH O2", "%"),

    ReadParameterOption(0x0B, "Speed", "SPEED", "SPEED"),
    ReadParameterOption(0x0C, "Battery Voltage", "BATT", "V"),
    ReadParameterOption(0x0D, "Throttle Position", "TPS", "V"),
    ReadParameterOption(0x0F, "Fuel Temp Sensor", "FUEL TEMP", "TEMP"),
    ReadParameterOption(0x11, "Intake Air Temp", "IAT", "TEMP"),
    ReadParameterOption(0x12, "Exhaust Gas Temp", "EGT", "V"),
    ReadParameterOption(0x15, "Injection Time LH", "INJ", "ms"),
    ReadParameterOption(0x23, "Injection Time RH", "RH INJ", "ms"),
    ReadParameterOption(0x16, "Ignition Timing", "TIM", "deg"),
    ReadParameterOption(0x17, "AAC", "AAC", "%"),

    ReadParameterOption(0x1A, "LH AF Alpha", "AF ALPHA", "%"),
    ReadParameterOption(0x1B, "RH AF Alpha", "RH AF ALPHA", "%"),
    ReadParameterOption(0x1C, "AFAlphaLSelfLear", "AF SLFLRN", "%"),
    ReadParameterOption(0x1D, "AFAlphaRSelfLear", "RH AF SLFLRN", "%"),

    ReadParameterOption(0x13, "Digital 0x13", "D13", "raw"), # A/C switch, Power Steering, Neutral/Park, Start signal, closed TPS
    ReadParameterOption(0x1E, "Digital 0x1E", "D1E", "raw"), # A/C Relay, Fuel Pump Relay, VTC solenoid, Coolant Fan Hi, Coolant Fan Lo
    ReadParameterOption(0x1F, "Digital 0x1F", "D1F", "raw"), # P/Reg control, Wastegate Solenoid, IACV/FICD Solenoid, EGR Solenoid
    ReadParameterOption(0x21, "Digital 0x21", "D21", "raw"), # LH Bank Lean, RH Bank Lean

    # These ones below don't have conversions listed in the documentation. Maybe will look into them later.
    # ReadParameterOption(0x28, "Wastegate Solenoid", "WG"),

    # ReadParameterOption(0x14, "Injection Time LH MSB", "INJH"),
    # ReadParameterOption(0x25, "Purge Vol Control Valve Step", "PURG"),
    # ReadParameterOption(0x26, "Tank Fuel Temp", "TNKT"),
    # ReadParameterOption(0x27, "FPCM DR Voltage", "FPCV"),
    # ReadParameterOption(0x29, "Turbo Boost Sensor Voltage", "BOOST"),
    # ReadParameterOption(0x2A, "Engine Mount On/Off", "MNT"),
    # ReadParameterOption(0x2E, "Position Counter", "PCNT"),
    # ReadParameterOption(0x2F, "Fuel Gauge Voltage", "FGV"),
    # ReadParameterOption(0x30, "FR O2 Heater B1", "O2H1"),
    # ReadParameterOption(0x31, "FR O2 Heater B2", "O2H2"),
    # ReadParameterOption(0x32, "Ignition Switch", "IGN"),
    # ReadParameterOption(0x33, "CAL/LD Value", "LOAD"),
    # ReadParameterOption(0x34, "B/Fuel Schedule", "BFS"),
    # ReadParameterOption(0x35, "RR O2 Sensor Voltage", "RRO2"),
    # ReadParameterOption(0x36, "RR O2 Sensor B2 Voltage", "RRO2B2"),
    # ReadParameterOption(0x38, "MAF g/s", "MAFGS"),
    # ReadParameterOption(0x39, "Evap System Pressure Voltage", "EVAP"),
]

READ_PARAMETER_LABELS = {option.code: option.label for option in READ_PARAMETER_OPTIONS}
READ_PARAMETER_TITLES = {option.code: option.title for option in READ_PARAMETER_OPTIONS}
READ_PARAMETER_UNITS = {option.code: option.unit for option in READ_PARAMETER_OPTIONS}
# Keep startup defaults aligned to the known-good legacy stream profile.
DEFAULT_READ_PARAMETERS = [0x1E, 0x16, 0x0B, 0x01, 0x08, 0x0C, 0x0D, 0x05, 0x09, 0x13, 0x17, 0x1A, 0x1C, 0x1F, 0x21]
DISPLAY_REGISTER_TO_INDEX = {
    0x01: 0,
    0x0B: 1,
    0x17: 2,
    0x08: 3,
    0x0C: 4,
    0x09: 5,
    0x16: 6,
    0x0D: 7,
}
DIGITAL_REGISTER_ORDER = [0x13, 0x1E, 0x1F, 0x21]
DIGITAL_REGISTER_SET = set(DIGITAL_REGISTER_ORDER)


def coerce_register_code(value: object) -> Optional[int]:
    try:
        if isinstance(value, str):
            return int(value, 0) & 0xFF
        if isinstance(value, (int, float)):
            return int(value) & 0xFF
        return int(str(value), 0) & 0xFF
    except (TypeError, ValueError):
        return None


def normalize_read_parameters(value: object, fallback: Optional[Sequence[int]] = None) -> list[int]:
    fallback_codes = list(fallback) if fallback is not None else list(DEFAULT_READ_PARAMETERS)
    if isinstance(value, dict):
        raw_values: Iterable[object] = value.keys()
    elif isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = fallback_codes

    normalized: list[int] = []
    for raw_value in raw_values:
        code = coerce_register_code(raw_value)
        if code is None or code in normalized:
            continue
        normalized.append(code)
        if len(normalized) >= MAX_READ_PARAMETERS:
            break

    if not normalized:
        return fallback_codes[:MAX_READ_PARAMETERS]

    return normalized[:MAX_READ_PARAMETERS]


def build_stream_request(register_codes: Sequence[int]) -> bytes:
    normalized_codes = normalize_read_parameters(register_codes)
    request_bytes: list[int] = []
    for code in normalized_codes:
        request_bytes.extend([0x5A, code & 0xFF])
    request_bytes.append(0xF0)
    return bytes(request_bytes)


def read_parameter_label(code: int) -> str:
    return READ_PARAMETER_LABELS.get(code, f"0x{code:02X}")


def read_parameter_title(code: int) -> str:
    return READ_PARAMETER_TITLES.get(code, read_parameter_label(code))


def read_parameter_unit(code: int) -> str:
    return READ_PARAMETER_UNITS.get(code, "raw")


def read_parameter_summary(value: object) -> str:
    selected_codes = normalize_read_parameters(value)
    return f"{len(selected_codes)} Selected"


def get_selected_stream_codes(value: object) -> list[int]:
    selected_codes = normalize_read_parameters(value)
    return [code for code in selected_codes if code not in DIGITAL_REGISTER_SET]


def get_selected_digital_registers(value: object) -> list[int]:
    selected_codes = normalize_read_parameters(value)
    return [register for register in DIGITAL_REGISTER_ORDER if register in selected_codes]


def get_stream_unit(code: int, units_speed: object, units_temp: object) -> str:
    unit = read_parameter_unit(code)

    if unit == "SPEED":
        return "MPH" if str(units_speed).upper() == "MPH" else "KPH"

    if unit == "TEMP":
        return "F" if str(units_temp).upper() == "F" else "C"

    return unit