import tkinter as tk
import math


def _cruise_avg(heights):
    if not heights:
        return None
    lo, hi = min(heights), max(heights)
    rng = hi - lo
    if rng < 5:
        return sum(heights) / len(heights)
    threshold = lo + rng * 0.60
    above = [i for i, h in enumerate(heights) if h >= threshold]
    if not above:
        return sum(heights) / len(heights)
    cruise = heights[above[0]: above[-1] + 1]
    return sum(cruise) / len(cruise)


class HeightProfileWidget(tk.Frame):
    PAD    = 4
    AXIS_W = 44
    AXIS_H = 16

    def __init__(self, parent, dark=True, **kwargs):
        super().__init__(parent, **kwargs)
        self.dark = dark
        self._bg = "#1e1e1e" if dark else "#f0f0f0"

        self._traj   = []
        self._photo  = []
        self._times  = []   # float seconds from start
        self._heights = []  # float metres
        self._photo_t = {}  # id(pp) -> seconds from start

        self._x_zoom   = 1.0   # >1 = zoomed in
        self._x_origin = 0.0   # left edge in seconds

        self._canvas = tk.Canvas(self, bg=self._bg, highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>",  lambda _e: self._redraw())
        self._canvas.bind("<MouseWheel>", self._on_scroll)   # Windows
        self._canvas.bind("<Button-4>",   self._on_scroll)   # Linux up
        self._canvas.bind("<Button-5>",   self._on_scroll)   # Linux down

    # ── public ──────────────────────────────────────────────────────────────

    def set_data(self, traj_points, photo_points=None):
        self._traj  = traj_points  or []
        self._photo = photo_points or []
        self._precompute()
        self._x_zoom   = 1.0
        self._x_origin = 0.0
        self._redraw()

    def clear(self):
        self._traj = []
        self._photo = []
        self._times = []
        self._heights = []
        self._photo_t = {}
        self._canvas.delete("all")

    # ── internal ─────────────────────────────────────────────────────────────

    def _precompute(self):
        pts = self._traj
        if not pts:
            self._times = []
            self._heights = []
            self._photo_t = {}
            return

        t0 = None
        for p in pts:
            if p.get("time"):
                t0 = p["time"]
                break
        if t0 is None:
            self._times = list(range(len(pts)))
            self._heights = [p.get("height") or 0 for p in pts]
            self._photo_t = {}
            return

        self._times   = [(p["time"] - t0).total_seconds() if p.get("time") else 0
                         for p in pts]
        self._heights = [p.get("height") or 0 for p in pts]

        time_map = {p.get("time"): self._times[i] for i, p in enumerate(pts)}
        self._photo_t = {}
        for pp in self._photo:
            t = pp.get("time")
            if t in time_map:
                self._photo_t[id(pp)] = time_map[t]

    def _on_scroll(self, event):
        if not self._times:
            return
        delta = getattr(event, "delta", 0)
        if delta == 0:
            delta = 120 if event.num == 4 else -120

        c    = self._canvas
        w    = c.winfo_width()
        pad, ax_w, ax_h = self.PAD, self.AXIS_W, self.AXIS_H
        cw   = w - pad - ax_w
        if cw <= 0:
            return

        total_t  = self._times[-1] if self._times else 1
        view_t   = total_t / self._x_zoom

        # cursor position as fraction of chart width
        cx       = event.x - ax_w
        frac     = max(0.0, min(1.0, cx / cw))
        t_cursor = self._x_origin + frac * view_t

        factor = 1.15 if delta > 0 else (1 / 1.15)
        self._x_zoom = max(1.0, min(self._x_zoom * factor, total_t / 10))

        new_view = total_t / self._x_zoom
        self._x_origin = t_cursor - frac * new_view
        self._x_origin = max(0.0, min(self._x_origin, total_t - new_view))
        self._redraw()

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        if not self._times or len(self._times) < 2:
            return
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 20:
            return

        pad, ax_w, ax_h = self.PAD, self.AXIS_W, self.AXIS_H
        cw = w - pad - ax_w
        ch = h - pad - ax_h

        total_t  = self._times[-1] or 1
        view_t   = total_t / self._x_zoom
        t_start  = self._x_origin
        t_end    = t_start + view_t

        heights  = self._heights
        h_min    = min(heights)
        h_max    = max(heights)
        rng      = h_max - h_min or 1

        def px(t):
            return ax_w + (t - t_start) / view_t * cw

        def py(v):
            return pad + (1 - (v - h_min) / rng) * ch

        # ── flight altitude line ─────────────────────────────────────────────
        line = []
        for t, hv in zip(self._times, heights):
            if t_start <= t <= t_end:
                line += [px(t), py(hv)]
        if len(line) >= 4:
            c.create_line(line, fill="#00c8ff", width=2, smooth=True)

        # ── photo markers ────────────────────────────────────────────────────
        for pp in self._photo:
            t  = self._photo_t.get(id(pp))
            hv = pp.get("height")
            if t is None or hv is None or not (t_start <= t <= t_end):
                continue
            x, y = px(t), py(hv)
            c.create_oval(x - 2, y - 2, x + 2, y + 2,
                          fill="#ffaa00", outline="")

        # ── cruise mean height dashed line ───────────────────────────────────
        avg_h = _cruise_avg(heights)
        if avg_h is not None:
            ya = py(avg_h)
            c.create_line(ax_w, ya, ax_w + cw, ya,
                          fill="#888888", width=1, dash=(4, 3))
            c.create_text(ax_w + cw - 2, ya - 3,
                          text=f"ср. {avg_h:.0f} м", anchor=tk.SE,
                          fill="#888888", font=("Segoe UI", 7))

        # ── Y axis ───────────────────────────────────────────────────────────
        fg = "#555555" if self.dark else "#888888"
        n_ticks = max(2, int(ch / 22))
        for i in range(n_ticks + 1):
            v = h_min + i * rng / n_ticks
            y = py(v)
            c.create_line(ax_w - 3, y, ax_w, y, fill=fg)
            c.create_text(ax_w - 5, y, text=f"{v:.0f}",
                          anchor=tk.E, fill=fg, font=("Segoe UI", 7))

        # ── X axis: minutes + hour marks ─────────────────────────────────────
        t_start_min = t_start / 60
        t_end_min   = t_end   / 60
        span_min    = t_end_min - t_start_min

        # choose tick interval in minutes
        for step_min in [1, 2, 5, 10, 15, 30, 60, 120, 180]:
            if span_min / step_min <= 12:
                break

        first_tick = math.ceil(t_start_min / step_min) * step_min
        tick_min = first_tick
        while tick_min <= t_end_min:
            t_sec = tick_min * 60
            x = px(t_sec)
            is_hour = (tick_min % 60 == 0)
            tick_h = 6 if is_hour else 3
            color  = "#aaaaaa" if is_hour else fg
            c.create_line(x, pad + ch, x, pad + ch + tick_h, fill=color)
            if is_hour:
                label = f"{int(tick_min // 60)}ч"
                c.create_text(x, pad + ch + tick_h + 1, text=label,
                              anchor=tk.N, fill="#aaaaaa", font=("Segoe UI", 7, "bold"))
            else:
                label = f"{int(tick_min % 60)}м" if tick_min % 60 != 0 else ""
                if label:
                    c.create_text(x, pad + ch + tick_h + 1, text=label,
                                  anchor=tk.N, fill=fg, font=("Segoe UI", 7))
            tick_min += step_min

        # ── border ───────────────────────────────────────────────────────────
        c.create_line(ax_w, pad, ax_w, pad + ch, fill=fg)
        c.create_line(ax_w, pad + ch, ax_w + cw, pad + ch, fill=fg)

        # ── zoom hint ────────────────────────────────────────────────────────
        if self._x_zoom > 1.01:
            c.create_text(ax_w + cw - 2, pad + 2,
                          text=f"×{self._x_zoom:.1f}", anchor=tk.NE,
                          fill="#555555", font=("Segoe UI", 7))
