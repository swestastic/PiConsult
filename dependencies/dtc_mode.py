import time
from typing import Any, Callable, Optional

import serial


def show_dtc_screen(state: Any, show_gauge: Callable[..., None], dtc_titles: dict[int, str]) -> None:
    with state.acquire_lock():
        dtc_codes = state.dtc_codes.copy()
        dtc_index = state.dtc_index
        dtc_status_message = state.dtc_status_message
        dtc_status_until = state.dtc_status_until
        dtc_clear_confirm_active = state.dtc_clear_confirm_active
        dtc_clear_confirm_yes = state.dtc_clear_confirm_yes

    if dtc_status_message and time.monotonic() < dtc_status_until:
        show_gauge("DTC", 0.0, dtc_status_message, 0.0, 1.0, show_needle=False, show_dial=False, show_value_text=False)
        return

    if dtc_clear_confirm_active:
        selected = "YES" if dtc_clear_confirm_yes else "NO"
        show_gauge(
            "Clear DTCs?",
            0.0,
            selected,
            0.0,
            1.0,
            show_needle=False,
            show_dial=False,
            show_value_text=False,
        )
        return

    if not dtc_codes:
        show_gauge("DTCs", 0.0, "None Found", 0.0, 1.0, show_needle=False, show_dial=False, show_value_text=False)
        return

    dtc_code = int(dtc_codes[dtc_index]) if dtc_index < len(dtc_codes) else -1
    dtc_title = dtc_titles.get(dtc_code, "Unknown DTC")
    show_gauge(
        f"DTC {dtc_index + 1}/{len(dtc_codes)}",
        float(dtc_code),
        dtc_title,
        1.0,
        55.0,
        show_needle=False,
        show_dial=False,
    )


def update_dtc_codes_from_ecu(
    state: Any,
    port_obj: Optional[serial.Serial],
    *,
    demo_mode: bool,
    read_dtc_codes_fn: Callable[[serial.Serial], list[int]],
) -> None:
    """Refresh state DTC list from ECU or demo values."""
    if demo_mode:
        # Example sample codes for menu/navigation testing.
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
