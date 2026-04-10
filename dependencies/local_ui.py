from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional

from PIL import Image

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None


_BUTTON_REGISTRY: dict[int, "LocalButton"] = {}


def local_ui_requested(default: bool = False) -> bool:
    raw = os.getenv("CONSULT_LOCAL_UI")
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class LocalButton:
    """Minimal gpiozero.Button-like class used by the desktop simulator."""

    def __init__(self, pin: int, hold_time: float = 0.5, bounce_time: float | None = None) -> None:
        self.pin = int(pin)
        self.hold_time = float(hold_time)
        self.bounce_time = None if bounce_time is None else float(bounce_time)
        self.when_pressed: Optional[Callable[[], None]] = None
        _BUTTON_REGISTRY[self.pin] = self

    def press(self) -> None:
        callback = self.when_pressed
        if callable(callback):
            callback()


def emit_button_press(pin: int) -> None:
    button = _BUTTON_REGISTRY.get(int(pin))
    if button is not None:
        button.press()


class DesktopDisplay:
    """Desktop popup that emulates the 1.9 inch LCD and four hardware buttons."""

    width = 170
    height = 320

    def __init__(self, scale: int = 2, title: str = "Consult Box - Local Display") -> None:
        import tkinter as tk

        if ImageTk is None:
            raise ImportError("PIL.ImageTk is unavailable; install Tk support to use DesktopDisplay")

        self._tk = tk
        self._root = tk.Tk()
        self._root.title(title)
        self._root.resizable(False, False)
        self._closed = False
        self._lock = threading.Lock()

        self._scale = max(1, int(scale))
        self._display_width = self.height * self._scale
        self._display_height = self.width * self._scale

        self._root.configure(bg="#101214")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        container = tk.Frame(self._root, bg="#101214", padx=12, pady=12)
        container.grid(row=0, column=0)

        self._mode_btn = self._make_button(container, "Mode", 26)
        self._mode_btn.grid(row=0, column=0, sticky="w")

        self._select_btn = self._make_button(container, "Select", 16)
        self._select_btn.grid(row=2, column=0, sticky="e")

        self._display_label = tk.Label(
            container,
            bg="#000000",
            width=self._display_width,
            height=self._display_height,
            bd=2,
            relief="sunken",
        )
        self._display_label.grid(row=1, column=0, columnspan=3, padx=8, pady=8)

        # Local UI is not physically rotated like the in-car button layout, so map
        # labels to opposite pins to keep navigation direction intuitive.
        self._up_btn = self._make_button(container, "Up", 23)
        self._up_btn.grid(row=0, column=2, sticky="w")

        self._down_btn = self._make_button(container, "Down", 17)
        self._down_btn.grid(row=2, column=2, sticky="e")

        container.grid_columnconfigure(1, minsize=max(20, self._display_width - 200))

        self._photo: Optional[ImageTk.PhotoImage] = None
        self.clear()
        self.pump_events()

    def _on_close(self) -> None:
        self._closed = True

    def _make_button(self, parent: Any, text: str, pin: int) -> Any:
        tk = self._tk
        return tk.Button(
            parent,
            text=text,
            width=9,
            height=2,
            bg="#20242A",
            fg="#F2F2F2",
            activebackground="#2E3540",
            activeforeground="#FFFFFF",
            command=lambda p=pin: emit_button_press(p),
        )

    def _set_image(self, image: Image.Image) -> None:
        if self._closed:
            return
        if image.mode != "RGB":
            image = image.convert("RGB")

        if image.size != (self.height, self.width):
            image = image.resize((self.height, self.width), Image.Resampling.BILINEAR)

        scaled = image.resize((self._display_width, self._display_height), Image.Resampling.NEAREST)
        self._photo = ImageTk.PhotoImage(scaled)
        self._display_label.configure(image=self._photo)

    def Init(self) -> None:
        return None

    def bl_Frequency(self, _freq: int) -> None:
        return None

    def bl_DutyCycle(self, _duty: int) -> None:
        return None

    def ShowImage(self, image: Image.Image) -> None:
        with self._lock:
            self._set_image(image)
        self.pump_events()

    def clear(self) -> None:
        self.ShowImage(Image.new("RGB", (self.height, self.width), (0, 0, 0)))

    def pump_events(self) -> bool:
        if self._closed:
            return False
        try:
            self._root.update_idletasks()
            self._root.update()
            return not self._closed
        except Exception:
            self._closed = True
            return False

    def module_exit(self) -> None:
        self._closed = True
        try:
            self._root.destroy()
        except Exception:
            pass
