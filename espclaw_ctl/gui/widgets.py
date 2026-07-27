import math
import tkinter as tk

from espclaw_ctl.gui.theme import Theme


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
    def __init__(self, master, size=48, color=Theme.LOBSTER, dark=Theme.LOBSTER_DARK, **kw):
        try:
            kw.setdefault("bg", master.cget("bg"))
        except tk.TclError:
            kw.setdefault("bg", Theme.BG)
        super().__init__(master, width=size, height=size, highlightthickness=0, **kw)
        self._size = size
        self._color = color
        self._dark = dark
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self._size / 64.0
        c, d = self._color, self._dark

        def pt(*coords):
            out = []
            for i, v in enumerate(coords):
                out.append(v * s)
            return out

        # arms connecting claws to the body (drawn under the claw mitts and head)
        self.create_line(*pt(24, 30, 9, 10), fill=c, width=max(1, 5 * s), capstyle="round")
        self.create_line(*pt(24, 34, 9, 54), fill=c, width=max(1, 5 * s), capstyle="round")

        # upper claw (mitt + split line)
        self.create_oval(*pt(0, 2, 20, 18), fill=c, outline="")
        self.create_line(*pt(11, 4, 11, 16), fill=d, width=max(1, 1.2 * s))

        # lower claw (mitt + split line)
        self.create_oval(*pt(0, 46, 20, 62), fill=c, outline="")
        self.create_line(*pt(11, 48, 11, 60), fill=d, width=max(1, 1.2 * s))

        # tail fan (drawn first so body overlaps it)
        self.create_polygon(*pt(52, 24, 62, 14, 58, 32, 62, 50, 52, 40), fill=c, outline="")
        for x in (52, 56, 60):
            self.create_line(*pt(x, 22, x - 3, 42), fill=d, width=max(1, 1.3 * s))

        # ribbed tail segments
        for cx in (44, 50):
            self.create_oval(*pt(cx - 7, 21, cx + 7, 43), fill=c, outline="")
        self.create_line(*pt(41, 22, 41, 42), fill=d, width=max(1, 1.3 * s))
        self.create_line(*pt(47, 21, 47, 43), fill=d, width=max(1, 1.3 * s))

        # body
        self.create_oval(*pt(24, 19, 46, 45), fill=c, outline="")

        # head
        self.create_oval(*pt(14, 22, 32, 42), fill=c, outline="")

        # eyes
        self.create_oval(*pt(15, 20, 23, 28), fill="#FFFFFF", outline="")
        self.create_oval(*pt(17.5, 22.5, 21, 26), fill="#1B1B22", outline="")
        self.create_oval(*pt(23, 20, 31, 28), fill="#FFFFFF", outline="")
        self.create_oval(*pt(25.5, 22.5, 29, 26), fill="#1B1B22", outline="")

        # antennae (drawn last so they stay visible above everything)
        self.create_line(*pt(20, 21, 12, 10, 16, 0), smooth=True, fill=c, width=max(1, 2 * s))
        self.create_line(*pt(26, 21, 28, 8, 24, 0), smooth=True, fill=c, width=max(1, 2 * s))


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
