import time
from functools import partial
from typing import Callable, Optional

import serial


def extract_first_consult_frame(raw_bytes: bytes) -> Optional[bytes]:
    """Extract first consult frame payload: 0xFF, <len>, <payload...>."""
    if not raw_bytes:
        return None

    data = list(raw_bytes)
    for i, value in enumerate(data):
        if value != 0xFF:
            continue
        if i + 1 >= len(data):
            return None
        payload_len = int(data[i + 1])
        frame_end = i + 2 + payload_len
        if frame_end <= len(data):
            return bytes(data[i + 2:frame_end])
        return None
    return None


def send_activation_command(
    port_obj: Optional[serial.Serial],
    command_type: int,
    data_byte: int,
    *,
    demo_mode: bool,
    log_index: int,
    write_log: Callable[[int, object, str], None],
) -> bool:
    """Send consult active test command: 0x0A <type> <data> 0xF0."""
    if demo_mode:
        return True

    if port_obj is None:
        return False

    try:
        port_obj.write(bytes([0x0A, command_type & 0xFF, data_byte & 0xFF, 0xF0]))
        time.sleep(0.05)
        return True
    except (serial.SerialException, OSError, ValueError) as exc:
        write_log(log_index, exc, f"Active test command 0x{command_type:02X}")
        return False


def read_dtc_codes(
    port_obj: serial.Serial,
    *,
    timeout_seconds: float,
    log_index: int,
    write_log: Callable[[int, object, str], None],
) -> list[int]:
    """Read DTCs using documented consult protocol."""
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

        # Stop any continuing stream per protocol docs.
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
    """Clear DTCs using consult clear command (0xC1)."""
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
