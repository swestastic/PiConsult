import time
from functools import partial
from typing import Any, Callable, Optional
from dependencies.consult.protocol import extract_first_consult_frame

import serial


DTC_CODE_TITLES = {
    11: "Crankshaft Position Circuit",
    12: "MAF Circuit",
    13: "Engine Temp Circuit ",
    14: "VSS Circuit",
    21: "Ignition Signal Circuit",
    22: "Fuel Pump Circuit",
    23: "Idle Switch",
    24: "Throttle Valve Switch",
    25: "ISC Valve",
    28: "Cooling Fan Circuit",
    31: "ECM",
    32: "EGR Function",
    33: "LH O2 Circuit",
    34: "Knock Sensor Circuit",
    35: "EGR Temp Sensor Circuit",
    36: "EGRC-BPT Valve",
    37: "Knock Sensor Circuit",
    38: "LH Bank Closed Loop (Bank 2)",
    41: "Intake Air Temp Sensor",
    42: "Fuel Temp Sensor Circuit",
    43: "TPS Circuit",
    45: "Injector Leak",
    47: "Crankshaft Position Sensor",
    51: "Injector Circuit",
    53: "RH O2 Circuit",
    54: "AT ECU Signal",
    55: "No Faults",
    63: "No. 6 Misfire",
    64: "No. 5 Misfire",
    65: "No. 4 Misfire",
    66: "No. 3 Misfire",
    67: "No. 2 Misfire",
    68: "No. 1 Misfire",
    71: "Random Misfire",
    72: "TWC Function RH Bank",
    73: "TWC Function LH Bank",
    76: "Fuel Injection System RH Bank",
    77: "Rear Oxygen Sensor Circuit",
    82: "CKP Sensor",
    84: "A/T Diagnosis Communication Line",
    85: "VTC Solenoid Valve Circuit",
    86: "Fuel Injection System Function LH Bank",
    87: "Canister Control Solenoid Valve Circuit",
    91: "Front Oxygen Sensor Heater Circuit RH Bank",
    94: "TCC Solenoid Valve",
    95: "CKP Sensor",
    98: "ECT Sensor",
    101: "Front Oxygen Sensor Heater Circuit LH Bank",
    103: "PNP Switch Circuit",
    105: "EGR And EGR Canister Control Solenoid Valve Circuit",
    108: "Canister Purge Control Valve Circuit",
}


def read_dtc_codes(
    port_obj: serial.Serial,
    *,
    timeout_seconds: float,
    log_index: int,
    write_log: Callable[[int, object, str], None],
) -> list[int]:
    try:
        if hasattr(port_obj, "reset_input_buffer"):
            port_obj.reset_input_buffer()

        port_obj.write(bytes([0xD1, 0xF0]))
        deadline = time.monotonic() + timeout_seconds
        buffer = bytearray()
        payload = None

        while time.monotonic() < deadline:
            chunk = port_obj.read_all()
            if chunk:
                buffer.extend(chunk)
                payload = extract_first_consult_frame(bytes(buffer))
                if payload is not None:
                    break
            time.sleep(0.01)

        port_obj.write(bytes([0x30]))

        if payload is None:
            return []

        parsed_codes: list[int] = []
        for i in range(0, len(payload) - 1, 2):
            code = int(payload[i])
            if 1 <= code <= 55 and code not in parsed_codes:
                parsed_codes.append(code)

        return parsed_codes
    except (serial.SerialException, OSError, ValueError) as exc:
        write_log(log_index, exc, "Reading DTC codes")
        return []


def clear_dtc_codes(
    port_obj: Optional[serial.Serial],
    *,
    demo_mode: bool,
    log_index: int,
    write_log: Callable[[int, object, str], None],
) -> bool:
    if demo_mode:
        return True

    if port_obj is None:
        return False

    try:
        if hasattr(port_obj, "reset_input_buffer"):
            port_obj.reset_input_buffer()

        port_obj.write(bytes([0xC1]))
        time.sleep(0.15)
        return True
    except (serial.SerialException, OSError, ValueError) as exc:
        write_log(log_index, exc, "Clearing DTC codes")
        return False


def build_read_dtc_codes_fn(log_index: int, write_log: Callable[[int, object, str], None]) -> Callable[[serial.Serial], list[int]]:
    return partial(read_dtc_codes, timeout_seconds=1.0, log_index=log_index, write_log=write_log)


def build_clear_dtc_codes_fn(log_index: int, write_log: Callable[[int, object, str], None]) -> Callable[[Optional[serial.Serial], bool], bool]:
    return partial(clear_dtc_codes, log_index=log_index, write_log=write_log)


def update_dtc_codes_from_ecu(
    state: Any,
    port_obj: Optional[serial.Serial],
    *,
    demo_mode: bool,
    read_dtc_codes_fn: Callable[[serial.Serial], list[int]],
) -> None:
    if demo_mode:
        sample_codes = [13, 34, 43]
        with state.acquire_lock():
            state.dtc_codes = sample_codes
            state.dtc_index = min(state.dtc_index, max(len(sample_codes) - 1, 0))
        return

    if port_obj is None:
        with state.acquire_lock():
            state.dtc_codes = []
            state.dtc_index = 0
        return

    codes = read_dtc_codes_fn(port_obj)
    with state.acquire_lock():
        state.dtc_codes = codes
        state.dtc_index = min(state.dtc_index, max(len(codes) - 1, 0))


def refresh_dtc_codes_for_buttons(
    state_obj: Any,
    port_obj: Optional[serial.Serial],
    demo_mode: bool,
    read_dtc_codes_fn: Callable[[serial.Serial], list[int]],
) -> None:
    update_dtc_codes_from_ecu(
        state_obj,
        port_obj,
        demo_mode=demo_mode,
        read_dtc_codes_fn=read_dtc_codes_fn,
    )
