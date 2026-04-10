import time
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
