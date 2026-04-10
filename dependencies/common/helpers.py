from typing import Callable


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def int_to_u8(value: int) -> int:
    return int(value) & 0xFF


def active_temp_display_value(coolant_c: int, units_temp: object, temp_unit_label: Callable[[object], str]) -> int:
    if temp_unit_label(units_temp) == "F":
        return int(round((coolant_c * 9.0 / 5.0) + 32.0))
    return int(coolant_c)


def speed_unit_label(value: object) -> str:
    return "MPH" if value in (1, "1", "MPH", "mph") else "KPH"


def temp_unit_label(value: object) -> str:
    return "F" if value in (1, "1", "F", "f") else "C"
