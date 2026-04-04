#!/usr/bin/env python3
"""Render a configurable gauge needle on the Waveshare 1.9" LCD.

Usage example:
    python3 gauge_needle_display.py --min 0 --max 8000 --value 3200 --title RPM --unit rpm
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
DISPLAY_DIR_CANDIDATES = (BASE_DIR / "NewDisplay", BASE_DIR / "New Display")
DISPLAY_DIR = next((path for path in DISPLAY_DIR_CANDIDATES if path.exists()), DISPLAY_DIR_CANDIDATES[0])

if str(DISPLAY_DIR) not in sys.path:
    sys.path.insert(0, str(DISPLAY_DIR))

from dependencies.local_ui import DesktopDisplay, local_ui_requested  # noqa: E402

try:
    import spidev as SPI  # type: ignore
except Exception:  # pragma: no cover
    SPI = None


class GaugeNeedleDisplay:
    def __init__(
        self,
        min_value: float,
        max_value: float,
        *,
        backlight_percent: int = 55,
        spi_freq_hz: int = 24_000_000,
        rotation_degrees: int = 0,
        start_angle_deg: float = -30.0,
        end_angle_deg: float = 210.0,
    ) -> None:
        if max_value <= min_value:
            raise ValueError("max_value must be greater than min_value")

        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.rotation_degrees = rotation_degrees % 360
        self.start_angle_deg = float(start_angle_deg)
        self.end_angle_deg = float(end_angle_deg)
        self.spi_freq_hz = int(spi_freq_hz)

        self._gauge_angle_offset = 180.0
        self._center_x = 0
        self._center_y = 0
        self._outer_radius = 0
        self._inner_radius = 0
        self._static_bg: Image.Image | None = None
        self._static_title: str = ""
        self._value_layout_key: tuple[float, float] | None = None
        self._reserved_value_size: tuple[int, int] = (0, 0)

        self.title_font = ImageFont.load_default()
        self.label_font = ImageFont.load_default()
        self.value_font = ImageFont.load_default()
        self.unit_font = ImageFont.load_default()

        font_dir_candidates = [DISPLAY_DIR / "Font", BASE_DIR / "Font"]
        fallback_font_path = BASE_DIR / "Font.ttc"

        title_font_candidates = [
            directory / "Font01.ttf" for directory in font_dir_candidates
        ] + [
            directory / "Font00.ttf" for directory in font_dir_candidates
        ] + [
            fallback_font_path,
        ]
        body_font_candidates = [
            directory / "Font02.ttf" for directory in font_dir_candidates
        ] + title_font_candidates
        self.title_font = self._load_font(
            title_font_candidates,
            30,
            role="title",
        )
        self.value_font = self._load_font(
            title_font_candidates,
            40,
            role="value",
        )
        self.unit_font = self._load_font(
            title_font_candidates,
            24,
            role="unit",
        )
        self.label_font = self._load_font(
            body_font_candidates,
            30,
            role="label",
        )

        prefer_local_ui = local_ui_requested(default=(os.name == "nt"))
        self.disp = self._create_display_backend(prefer_local_ui)

        self.disp.Init()
        time.sleep(0.2)
        self.disp.clear()
        time.sleep(0.1)
        if hasattr(self.disp, "bl_Frequency"):
            self.disp.bl_Frequency(20_000)
        self.disp.bl_DutyCycle(max(0, min(100, int(backlight_percent))))

    def _create_display_backend(self, prefer_local_ui: bool) -> Any:
        if prefer_local_ui:
            scale = int(os.getenv("CONSULT_LOCAL_SCALE", "2"))
            return DesktopDisplay(scale=scale)

        try:
            from dependencies.lib import LCD_1inch9  # type: ignore

            if SPI is not None:
                return LCD_1inch9.LCD_1inch9(
                    spi=SPI.SpiDev(0, 0),
                    spi_freq=self.spi_freq_hz,
                    rst=27,
                    dc=25,
                    bl=18,
                )

            return LCD_1inch9.LCD_1inch9()
        except Exception as exc:
            print(f"[gauge] Hardware display unavailable, using desktop popup: {exc}", file=sys.stderr)
            scale = int(os.getenv("CONSULT_LOCAL_SCALE", "2"))
            return DesktopDisplay(scale=scale)

    @staticmethod
    def _load_font(candidates: list[Path], size: int, *, role: str) -> Any:
        for path in candidates:
            if not path.exists():
                continue
            try:
                return ImageFont.truetype(str(path), size)
            except Exception as exc:
                print(f"[gauge] Failed loading {role} font '{path}': {exc}", file=sys.stderr)

        print(f"[gauge] Falling back to default PIL font for {role}; text size may be small.", file=sys.stderr)
        return ImageFont.load_default()

    def _build_static_background(self, title: str) -> Image.Image:
        image = Image.new("RGB", (self.disp.height, self.disp.width), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        width, height = image.size

        self._center_x = width // 2
        self._center_y = int(height * 0.4)
        self._outer_radius = int(min(width * 0.30, height * 0.40))
        self._inner_radius = self._outer_radius - 14

        tick_count = 8
        for i in range(tick_count + 1):
            ratio = i / tick_count
            angle = self.start_angle_deg + ratio * (self.end_angle_deg - self.start_angle_deg) + self._gauge_angle_offset
            x1, y1 = self._point_on_circle(self._center_x, self._center_y, self._outer_radius, angle)
            x2, y2 = self._point_on_circle(self._center_x, self._center_y, self._inner_radius, angle)
            draw.line((x1, y1, x2, y2), fill=(180, 180, 180), width=2)

        min_x, min_y = self._point_on_circle(self._center_x, self._center_y, self._outer_radius + 12, self.start_angle_deg + self._gauge_angle_offset)
        max_x, max_y = self._point_on_circle(self._center_x, self._center_y, self._outer_radius + 12, self.end_angle_deg + self._gauge_angle_offset)
        draw.text((min_x - 16, min_y - 8), f"{self.min_value:g}", font=self.label_font, fill=(160, 160, 160))
        draw.text((max_x - 16, max_y - 8), f"{self.max_value:g}", font=self.label_font, fill=(160, 160, 160))

        title_width, title_height = self._text_size(draw, title, self.title_font)
        title_x = (width - title_width) // 2
        title_y = (height // 2) - (title_height // 2)
        draw.text((title_x, title_y), title, font=self.title_font, fill=(255, 255, 255))

        self._static_title = title
        return image

    def _get_static_background(self, title: str) -> Image.Image:
        if self._static_bg is None or self._static_title != title:
            self._static_bg = self._build_static_background(title)
        return self._static_bg

    def set_range(self, min_value: float, max_value: float) -> None:
        if max_value <= min_value:
            raise ValueError("max_value must be greater than min_value")
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self._value_layout_key = None

    def _get_reserved_value_size(self, draw: ImageDraw.ImageDraw) -> tuple[int, int]:
        layout_key = (self.min_value, self.max_value)
        if self._value_layout_key == layout_key and self._reserved_value_size != (0, 0):
            return self._reserved_value_size

        min_text = f"{self.min_value:g}"
        max_text = f"{self.max_value:g}"
        max_chars = max(len(min_text), len(max_text), 1)
        # Use wide glyphs for conservative fixed layout width.
        reserve_text = "8" * max_chars
        self._reserved_value_size = self._text_size(draw, reserve_text, self.value_font)
        self._value_layout_key = layout_key
        return self._reserved_value_size

    def value_to_angle(self, value: float) -> float:
        clamped = max(self.min_value, min(self.max_value, value))
        span = self.max_value - self.min_value
        ratio = (clamped - self.min_value) / span
        return self.start_angle_deg + ratio * (self.end_angle_deg - self.start_angle_deg)

    @staticmethod
    def _point_on_circle(center_x: int, center_y: int, radius: float, angle_deg: float) -> tuple[int, int]:
        theta = math.radians(angle_deg)
        x = center_x + int(math.cos(theta) * radius)
        y = center_y + int(math.sin(theta) * radius)
        return x, y

    @staticmethod
    def _text_size(draw: ImageDraw.ImageDraw, text: str, font: object) -> tuple[int, int]:
        textbbox_fn = getattr(draw, "textbbox", None)
        if callable(textbbox_fn):
            try:
                bbox: Any = textbbox_fn((0, 0), text, font=font)
                if isinstance(bbox, tuple) and len(bbox) >= 4:
                    left, top, right, bottom = bbox[:4]
                    return int(right - left), int(bottom - top)
            except Exception:
                pass

        textsize_fn = getattr(draw, "textsize", None)
        if callable(textsize_fn):
            try:
                size: Any = textsize_fn(text, font=font)
                if isinstance(size, tuple) and len(size) >= 2:
                    width, height = size[:2]
                    return int(width), int(height)
            except Exception:
                pass

        getsize_fn = getattr(font, "getsize", None)
        if callable(getsize_fn):
            try:
                size: Any = getsize_fn(text)
                if isinstance(size, tuple) and len(size) >= 2:
                    width, height = size[:2]
                    return int(width), int(height)
            except Exception:
                pass

        return len(text) * 10, 18

    def _wrap_text_lines(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: object,
        max_width: int,
        *,
        max_lines: int = 3,
    ) -> list[str]:
        """Wrap text to fit within max_width using word and fallback character wrapping."""
        normalized = " ".join(str(text).split())
        if not normalized:
            return [""]

        words = normalized.split(" ")
        lines: list[str] = []
        current = ""

        def _fits(candidate: str) -> bool:
            width, _ = self._text_size(draw, candidate, font)
            return width <= max_width

        for word in words:
            candidate = word if not current else f"{current} {word}"
            if _fits(candidate):
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            if _fits(word):
                current = word
                continue

            # Fallback: hard-wrap very long tokens that cannot fit in one line.
            chunk = ""
            for ch in word:
                next_chunk = f"{chunk}{ch}"
                if chunk and not _fits(next_chunk):
                    lines.append(chunk)
                    chunk = ch
                else:
                    chunk = next_chunk
            current = chunk

            if len(lines) >= max_lines:
                break

        if current and len(lines) < max_lines:
            lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]

        if len(lines) == max_lines and words:
            last = lines[-1]
            if len(last) > 3:
                lines[-1] = f"{last[:-3]}..."

        return lines or [""]

    def render_image(
        self,
        value: float,
        *,
        title: str = "Gauge",
        unit: str = "",
        show_needle: bool = True,
        show_dial: bool = True,
        show_value_text: bool = True,
        value_text: str | None = None,
        warning_text: str | None = None,
        warning_lines: list[str] | None = None,
    ) -> Image.Image:
        if show_dial:
            image = self._get_static_background(title).copy()
        else:
            image = Image.new("RGB", (self.disp.height, self.disp.width), (0, 0, 0))

        draw = ImageDraw.Draw(image)
        width, height = image.size

        if show_dial and show_needle:
            needle_angle = self.value_to_angle(value) + self._gauge_angle_offset
            needle_end_x, needle_end_y = self._point_on_circle(self._center_x, self._center_y, self._outer_radius - 24, needle_angle)
            draw.line((self._center_x, self._center_y, needle_end_x, needle_end_y), fill=(255, 70, 70), width=3)
            draw.ellipse((self._center_x - 4, self._center_y - 4, self._center_x + 4, self._center_y + 4), fill=(255, 255, 255))

        if show_value_text:
            value_str = value_text if value_text is not None else f"{value:g}"
            value_width, value_height = self._text_size(draw, value_str, self.value_font)
            unit_str = unit if unit else ""
            unit_width, unit_height = self._text_size(draw, unit_str, self.unit_font) if unit_str else (0, 0)
        else:
            value_str = ""
            value_width, value_height = 0, 0
            unit_str = unit if unit else ""
            unit_width, unit_height = self._text_size(draw, unit_str, self.unit_font) if unit_str else (0, 0)

        no_dial_content_top = 0

        if show_dial:
            reserved_value_width, reserved_value_height = self._get_reserved_value_size(draw)
            value_y = self._center_y + 56
            title_center_x = self._center_x
            value_x = title_center_x - (value_width // 2)
            unit_x_anchor = title_center_x + (value_width // 2) + 8
            unit_y_anchor = value_y + max(0, (reserved_value_height - unit_height) // 2)
        else:
            wrapped_title_lines = self._wrap_text_lines(
                draw,
                title,
                self.title_font,
                max(20, width - 12),
                max_lines=3,
            )

            line_gap = 2
            title_line_sizes = [self._text_size(draw, line, self.title_font) for line in wrapped_title_lines]
            title_block_height = sum(h for _, h in title_line_sizes) + (line_gap * (len(title_line_sizes) - 1))
            title_y = max(6, (height // 2) - title_block_height - 10)

            y_cursor = title_y
            for line, (line_w, line_h) in zip(wrapped_title_lines, title_line_sizes):
                line_x = (width - line_w) // 2
                draw.text((line_x, y_cursor), line, font=self.title_font, fill=(255, 255, 255))
                y_cursor += line_h + line_gap
            no_dial_content_top = y_cursor + 4

            if show_value_text:
                combined_width = value_width + (8 + unit_width if unit_str else 0)
            else:
                combined_width = unit_width
            title_center_x = width // 2
            value_x = title_center_x - (value_width // 2)
            value_y = (height // 2) + 4
            unit_x_anchor = title_center_x + (value_width // 2) + 8
            unit_y_anchor = value_y + (value_height - unit_height) // 2

        if value_y + value_height > height - 2:
            value_y = max(0, height - value_height - 2)

        if show_value_text and value_str:
            draw.text((value_x, value_y), value_str, font=self.value_font, fill=(255, 220, 120))

        if unit_str:
            if not show_dial and not show_value_text:
                wrapped_unit_lines = self._wrap_text_lines(
                    draw,
                    unit_str,
                    self.unit_font,
                    max(20, width - 12),
                    max_lines=6,
                )
                unit_line_gap = 2
                unit_line_sizes = [self._text_size(draw, line, self.unit_font) for line in wrapped_unit_lines]
                unit_block_height = sum(h for _, h in unit_line_sizes) + (unit_line_gap * (len(unit_line_sizes) - 1))
                unit_y = max(no_dial_content_top, value_y)
                if unit_y + unit_block_height > height - 2:
                    unit_y = max(no_dial_content_top, height - unit_block_height - 2)

                y_cursor = unit_y
                for line, (line_w, line_h) in zip(wrapped_unit_lines, unit_line_sizes):
                    line_x = (width - line_w) // 2
                    draw.text((line_x, y_cursor), line, font=self.unit_font, fill=(200, 200, 200))
                    y_cursor += line_h + unit_line_gap
            elif show_value_text:
                unit_x = unit_x_anchor
                unit_y = unit_y_anchor
                draw.text((unit_x, unit_y), unit_str, font=self.unit_font, fill=(200, 200, 200))
            else:
                unit_x = title_center_x - (unit_width // 2)
                unit_y = unit_y_anchor
                draw.text((unit_x, unit_y), unit_str, font=self.unit_font, fill=(200, 200, 200))

        active_warning_lines: list[str] = []
        if warning_lines:
            active_warning_lines = [line for line in warning_lines if line]
        elif warning_text:
            active_warning_lines = [warning_text]

        if active_warning_lines:
            textbbox_fn = getattr(draw, "textbbox", None)
            line_metrics: list[tuple[str, int, int, int, int, int]] = []
            # Metrics tuple: (line, left, top, right, bottom, height)
            for line in active_warning_lines:
                if callable(textbbox_fn):
                    bbox = textbbox_fn((0, 0), line, font=self.unit_font)
                    if isinstance(bbox, tuple) and len(bbox) >= 4:
                        left, top, right, bottom = [int(v) for v in bbox[:4]]
                        height = max(1, bottom - top)
                    else:
                        width, height = self._text_size(draw, line, self.unit_font)
                        left, top, right, bottom = 0, 0, int(width), int(height)
                        height = max(1, int(height))
                else:
                    width, height = self._text_size(draw, line, self.unit_font)
                    left, top, right, bottom = 0, 0, int(width), int(height)
                    height = max(1, int(height))
                line_metrics.append((line, left, top, right, bottom, height))

            warn_w = max((right - left) for _, left, _, right, _, _ in line_metrics)
            line_gap = 3
            warn_h = sum(height for _, _, _, _, _, height in line_metrics) + (line_gap * (len(active_warning_lines) - 1))
            pad_x = 6
            pad_y = 6
            box_right = width - 6
            box_left = box_right - warn_w - (pad_x * 2)
            box_top = 6
            box_bottom = box_top + warn_h + (pad_y * 2)
            draw.rectangle((box_left, box_top, box_right, box_bottom), fill=(90, 0, 0), outline=(220, 40, 40))

            y_cursor = box_top + pad_y
            for line, left, top, _right, _bottom, height in line_metrics:
                draw_x = box_left + pad_x - left
                draw_y = y_cursor - top
                draw.text((draw_x, draw_y), line, font=self.unit_font, fill=(255, 170, 170))
                y_cursor += height + line_gap

        if self.rotation_degrees:
            image = image.rotate(self.rotation_degrees)

        return image

    def show_value(
        self,
        value: float,
        *,
        title: str = "Gauge",
        unit: str = "",
        show_needle: bool = True,
        show_dial: bool = True,
        show_value_text: bool = True,
        value_text: str | None = None,
        warning_text: str | None = None,
        warning_lines: list[str] | None = None,
    ) -> None:
        image = self.render_image(
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
        self.disp.ShowImage(image)

    def close(self) -> None:
        try:
            self.disp.module_exit()
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a gauge needle on Waveshare 1.9 LCD")
    parser.add_argument("--min", dest="minimum", type=float, required=True, help="Lower bound")
    parser.add_argument("--max", dest="maximum", type=float, required=True, help="Upper bound")
    parser.add_argument("--value", type=float, help="Needle value")
    parser.add_argument("--demo", action="store_true", help="Continuously sweep needle between min and max")
    parser.add_argument(
        "--sweep-duration",
        type=float,
        default=10.0,
        help="Seconds for one-way sweep from min to max in demo mode",
    )
    parser.add_argument(
        "--demo-steps",
        type=int,
        default=600,
        help="Number of value subdivisions per one-way sweep in demo mode",
    )
    parser.add_argument("--title", type=str, default="Gauge", help="Gauge title")
    parser.add_argument("--unit", type=str, default="", help="Unit label")
    parser.add_argument("--backlight", type=int, default=55, help="Backlight percent (0-100)")
    parser.add_argument("--spi-freq", type=int, default=24000000, help="SPI clock in Hz (higher is faster; reduce if unstable)")
    parser.add_argument("--rotation", type=int, default=0, choices=(0, 90, 180, 270), help="Final image rotation")
    args = parser.parse_args()
    if not args.demo and args.value is None:
        parser.error("--value is required unless --demo is used")
    if args.sweep_duration <= 0:
        parser.error("--sweep-duration must be greater than 0")
    if args.demo_steps < 2:
        parser.error("--demo-steps must be at least 2")
    return args


def demo_sweep_value(minimum: float, maximum: float, ratio: float) -> float:
    span = maximum - minimum
    return minimum + ratio * span


def main() -> int:
    args = parse_args()
    display = GaugeNeedleDisplay(
        min_value=args.minimum,
        max_value=args.maximum,
        backlight_percent=args.backlight,
        spi_freq_hz=args.spi_freq,
        rotation_degrees=args.rotation,
    )
    try:
        if args.demo:
            step_interval = args.sweep_duration / float(args.demo_steps)
            cycle_duration = args.sweep_duration * 2.0
            start_time = time.monotonic()
            while True:
                elapsed = time.monotonic() - start_time
                phase = elapsed % cycle_duration
                if phase <= args.sweep_duration:
                    raw_ratio = phase / args.sweep_duration
                else:
                    raw_ratio = 1.0 - ((phase - args.sweep_duration) / args.sweep_duration)

                step_index = int(round(raw_ratio * args.demo_steps))
                step_index = max(0, min(args.demo_steps, step_index))
                ratio = step_index / float(args.demo_steps)
                value = demo_sweep_value(args.minimum, args.maximum, ratio)
                display.show_value(value, title=args.title, unit=args.unit)

                elapsed_after_draw = time.monotonic() - start_time
                next_tick = (math.floor(elapsed_after_draw / step_interval) + 1) * step_interval
                sleep_for = next_tick - elapsed_after_draw
                if sleep_for > 0:
                    time.sleep(sleep_for)
        display.show_value(float(args.value), title=args.title, unit=args.unit)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        display.close()


if __name__ == "__main__":
    raise SystemExit(main())
