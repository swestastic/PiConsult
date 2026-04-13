from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import time
from typing import Any, Callable, Sequence

from PIL import Image, ImageDraw, ImageFont
from dependencies.common.helpers import clamp_int


@lru_cache(maxsize=4)
def get_list_body_font(size: int = 18) -> Any:
    common_dir = Path(__file__).resolve().parent
    candidates = [
        common_dir / "Font.ttf",
    ]
    for font_path in candidates:
        if not font_path.exists():
            continue
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_scrollable_menu_screen(
    gauge: Any,
    title: str,
    rows: Sequence[Any],
    selected_index: int,
    line_builder: Callable[[Any, int, bool], tuple[str, tuple[int, int, int]]],
    footer_text: str,
    *,
    font: Any | None = None,
    start_y: int = 32,
    bottom_margin: int = 18,
    max_visible_rows: int = 5,
) -> None:
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title_font = getattr(gauge, "menu_title_font", None) or gauge.label_font
    title_width, _ = gauge._text_size(draw, title, title_font)
    draw.text(((width - title_width) // 2, 4), title, font=title_font, fill=(255, 255, 255))

    if font is None:
        font = getattr(gauge, "menu_font", None) or get_list_body_font()
    footer_font = getattr(gauge, "footer_font", None) or font

    total_rows = len(rows)
    if total_rows <= 0:
        draw.text((8, height - 19), footer_text, font=footer_font, fill=(180, 180, 180))
        if gauge.rotation_degrees:
            image = image.rotate(gauge.rotation_degrees)
        gauge.disp.ShowImage(image)
        return

    selected_index = clamp_int(selected_index, 0, total_rows - 1)
    visible_rows = min(max_visible_rows, total_rows)
    row_height = max(13, (height - start_y - bottom_margin) // max(1, visible_rows))
    visible_start = max(0, min(selected_index - (visible_rows // 2), max(total_rows - visible_rows, 0)))
    visible_end = min(total_rows, visible_start + visible_rows)
    now = time.monotonic()
    menu_key = (title, total_rows, footer_text)

    for visible_row, row_index in enumerate(range(visible_start, visible_end)):
        y = start_y + (visible_row * row_height)
        is_selected = row_index == selected_index

        if is_selected:
            draw.rectangle((4, y + 3, width - 4, y + row_height + 1), fill=(24, 36, 52), outline=(90, 140, 190))

        line_text, text_color = line_builder(rows[row_index], row_index, is_selected)
        text_x = 8
        text_y = y + 2
        text_width, text_height = gauge._text_size(draw, line_text, font)
        available_width = max(1, width - 16)

        if is_selected and text_width > available_width:
            ticker_key = (menu_key, row_index, line_text)
            last_ticker_key = getattr(gauge, "_menu_ticker_key", None)
            if ticker_key != last_ticker_key:
                setattr(gauge, "_menu_ticker_key", ticker_key)
                setattr(gauge, "_menu_ticker_started", now)

            ticker_started = getattr(gauge, "_menu_ticker_started", now)
            elapsed = max(0.0, now - ticker_started)
            pause_seconds = 0.75
            scroll_speed_px_per_sec = 26.0
            gap_pixels = 20
            scroll_cycle = text_width + gap_pixels
            offset = 0
            if elapsed > pause_seconds:
                offset = int(((elapsed - pause_seconds) * scroll_speed_px_per_sec) % max(1, scroll_cycle))

            clip_height = max(text_height + 2, row_height)
            marquee_layer = Image.new("RGBA", (available_width, clip_height), (0, 0, 0, 0))
            marquee_draw = ImageDraw.Draw(marquee_layer)
            marquee_draw.text((-offset, 0), line_text, font=font, fill=text_color)
            marquee_draw.text((text_width + gap_pixels - offset, 0), line_text, font=font, fill=text_color)
            image.paste(marquee_layer, (text_x, text_y), marquee_layer)
        else:
            draw.text((text_x, text_y), line_text, font=font, fill=text_color)

    draw.text((8, height - 19), footer_text, font=footer_font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)
