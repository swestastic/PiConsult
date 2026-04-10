from __future__ import annotations

from functools import lru_cache
from pathlib import Path
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
    start_y: int = 36,
    bottom_margin: int = 18,
    max_visible_rows: int = 5,
) -> None:
    width = gauge.disp.height
    height = gauge.disp.width
    image = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    title_width, _ = gauge._text_size(draw, title, gauge.label_font)
    draw.text(((width - title_width) // 2, 4), title, font=gauge.label_font, fill=(255, 255, 255))

    if font is None:
        font = get_list_body_font()

    total_rows = len(rows)
    if total_rows <= 0:
        draw.text((8, height - 23), footer_text, font=font, fill=(180, 180, 180))
        if gauge.rotation_degrees:
            image = image.rotate(gauge.rotation_degrees)
        gauge.disp.ShowImage(image)
        return

    selected_index = clamp_int(selected_index, 0, total_rows - 1)
    visible_rows = min(max_visible_rows, total_rows)
    row_height = max(13, (height - start_y - bottom_margin) // max(1, visible_rows))
    visible_start = max(0, min(selected_index - (visible_rows // 2), max(total_rows - visible_rows, 0)))
    visible_end = min(total_rows, visible_start + visible_rows)

    for visible_row, row_index in enumerate(range(visible_start, visible_end)):
        y = start_y + (visible_row * row_height)
        is_selected = row_index == selected_index

        if is_selected:
            draw.rectangle((4, y + 3, width - 4, y + row_height + 1), fill=(24, 36, 52), outline=(90, 140, 190))

        line_text, text_color = line_builder(rows[row_index], row_index, is_selected)
        draw.text((8, y + 2), line_text, font=font, fill=text_color)

    draw.text((8, height - 23), footer_text, font=font, fill=(180, 180, 180))

    if gauge.rotation_degrees:
        image = image.rotate(gauge.rotation_degrees)

    gauge.disp.ShowImage(image)
