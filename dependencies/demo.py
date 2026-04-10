from __future__ import annotations

import math
import time
from typing import Callable

from dependencies.gauge import get_stream_range


def elapsed_since(start_time: float) -> float:
    return time.monotonic() - start_time


def initialize_demo_mode(write_text_fn: Callable[[object, object], None]) -> float:
    write_text_fn("DEMO MODE", "No ECU")
    return time.monotonic()


def _demo_formula(lower: float, upper: float, x_value: float) -> float:
    span = upper - lower
    midpoint = lower + (span / 2.0)
    return (span / 2.0) * math.sin(3.0 * x_value) + midpoint


def build_demo_stream_value_map(elapsed_seconds: float, units_speed: object, units_temp: object) -> dict[int, float]:
    stream_codes = (
        0x01,
        0x05,
        0x07,
        0x08,
        0x09,
        0x0A,
        0x0B,
        0x0C,
        0x0D,
        0x0F,
        0x11,
        0x12,
        0x15,
        0x23,
        0x16,
        0x17,
        0x1A,
        0x1B,
        0x1C,
        0x1D,
    )
    return {
        code: _demo_formula(*get_stream_range(code, units_speed, units_temp), elapsed_seconds)
        for code in stream_codes
    }


def build_demo_stream_snapshot(start_time: float, units_speed: object, units_temp: object) -> tuple[float, dict[int, float]]:
    elapsed = elapsed_since(start_time)
    return elapsed, build_demo_stream_value_map(elapsed, units_speed, units_temp)
