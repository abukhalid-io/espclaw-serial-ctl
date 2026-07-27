import math
import os
import tkinter as tk

from PIL import Image, ImageTk

from espclaw_ctl.gui.theme import Theme

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
_LOGO_PATH = os.path.join(_ASSETS_DIR, "logo.png")


class PillButton(tk.Canvas):
    def __init__(self, master, text, command=None, width=140, height=38,
                 bg=Theme.ACCENT, fg="#FFFFFF", font=Theme.FONT_BOLD, outline=False, **kw):
        try:
            kw.setdefault("bg", master.cget("bg"))
        except tk.TclError:
            kw.setdefault("bg", Theme.BG)
        super().__init__(master, width=width, height=height, highlightthickness=0, **kw)
        self._pw = width
        self._ph = height
        self._text = text
        self._fill = bg
        self._fg = fg
        self._font = font
        self._outline = outline
        self._command = command
        self._enabled = True
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self._draw())

    def set_text(self, text):
        self._text = text
        self._draw()

    def set_enabled(self, enabled):
        self._enabled = enabled
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self._pw, self._ph
        r = h / 2
        fill = self._fill if self._enabled else Theme.BORDER
        fg = self._fg if self._enabled else Theme.DIM
        stroke = Theme.BORDER if self._outline else ""
        self._round_rect(2, 2, w - 2, h - 2, r, fill=fill, outline=stroke, width=1)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        self.create_polygon(points, smooth=True, **kw)

    def _on_click(self, _event):
        if self._enabled and self._command:
            self._command()


class Card(tk.Frame):
    def __init__(self, master, padding=16, **kw):
        kw.setdefault("bg", Theme.CARD)
        kw.setdefault("highlightbackground", Theme.BORDER)
        kw.setdefault("highlightthickness", 1)
        super().__init__(master, **kw)
        self.body = tk.Frame(self, bg=Theme.CARD)
        self.body.pack(fill="both", expand=True, padx=padding, pady=padding)


class Spinner(tk.Canvas):
    def __init__(self, master, size=48, color=Theme.ACCENT, **kw):
        kw.setdefault("bg", Theme.BG)
        super().__init__(master, width=size, height=size, highlightthickness=0, **kw)
        self._size = size
        self._color = color
        self._angle = 0
        self._spinning = False
        self._after_id = None

    def start(self):
        self._spinning = True
        self._tick()

    def stop(self, done_color=Theme.GREEN):
        self._spinning = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.delete("all")
        s = self._size
        self.create_oval(3, 3, s - 3, s - 3, outline=done_color, width=4)

    def _tick(self):
        if not self._spinning:
            return
        self.delete("all")
        s = self._size
        start = self._angle
        self.create_arc(3, 3, s - 3, s - 3, start=start, extent=100,
                         outline=self._color, width=4, style="arc")
        self._angle = (self._angle - 12) % 360
        self._after_id = self.after(40, self._tick)


class LobsterLogo(tk.Canvas):
    _source_image = None

    def __init__(self, master, size=48, **kw):
        try:
            kw.setdefault("bg", master.cget("bg"))
        except tk.TclError:
            kw.setdefault("bg", Theme.BG)
        super().__init__(master, width=size, height=size, highlightthickness=0, **kw)
        self._size = size
        self._photo = self._load_photo(size)
        self.create_image(size / 2, size / 2, image=self._photo)

    @classmethod
    def _load_photo(cls, size):
        if cls._source_image is None:
            cls._source_image = Image.open(_LOGO_PATH).convert("RGBA")
        src = cls._source_image
        w, h = src.size
        scale = size / max(w, h)
        new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        resized = src.resize(new_size, Image.LANCZOS)
        return ImageTk.PhotoImage(resized)


class StatusDot(tk.Canvas):
    def __init__(self, master, color=Theme.GREEN, size=10, **kw):
        kw.setdefault("bg", Theme.CARD)
        super().__init__(master, width=size, height=size, highlightthickness=0, **kw)
        self._size = size
        self._color = color
        self._phase = 0
        self._after_id = None
        self._pulse()

    def _pulse(self):
        self.delete("all")
        s = self._size
        alpha = 0.55 + 0.45 * abs(math.sin(self._phase))
        pad = (1 - alpha) * 2
        self.create_oval(pad, pad, s - pad, s - pad, fill=self._color, outline="")
        self._phase += 0.15
        self._after_id = self.after(60, self._pulse)

    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        super().destroy()
