import os
import sys
import queue
import threading
import traceback

import matplotlib
matplotlib.use("Agg")

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, scrolledtext

from PIL import Image, ImageTk

from core.pipeline import run_pipeline
from plots.map_widget import MapWidget, BASEMAP_KEYS, DEFAULT_BASEMAP

APP_VERSION = "0.25_14.07.2026"
APP_AUTHOR = "andrewkena"

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
ICON_PATH = os.path.join(ASSETS_DIR, "GNSS_logo.ico")

LIGHT_THEME = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "text_bg": "#ffffff",
    "text_fg": "#000000",
    "select_bg": "#0078d7",
    "select_fg": "#ffffff",
}

DARK_THEME = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "text_bg": "#252526",
    "text_fg": "#d4d4d4",
    "select_bg": "#094771",
    "select_fg": "#ffffff",
}

QUALITY_RU = {
    "EXCELLENT": "ОТЛИЧНО",
    "GOOD": "ХОРОШО",
    "NORMAL": "НОРМАЛЬНО",
    "WARNING": "ВНИМАНИЕ",
    "POOR": "ПЛОХО",
}

QUALITY_COLOR = {
    "EXCELLENT": "#1b8a3a",
    "GOOD": "#558b2f",
    "NORMAL": "#f9a825",
    "WARNING": "#fb8c00",
    "POOR": "#e53935",
}

HELP_TEXT = """\
OMJET GNSS ANALYZER
====================================================================
Версия: {version}        Автор: {author}
====================================================================

НАЗНАЧЕНИЕ ПРОГРАММЫ

Программа анализирует «сырые» бинарные данные ГНСС-приёмника
(файлы .cnb, формат ComNav/SinoGNSS, OEM-совместимый протокол) с
аэрофотосъёмочной миссии беспилотника и оценивает качество съёмки
с точки зрения последующего построения ортофотоплана.

--------------------------------------------------------------------
ЧТО ДЕЛАЕТ ПРОГРАММА

1. Декодирование CNB
   - Извлекает из бинарного потока: измерения GPS (псевдодальности,
     фаза, доплер, C/N0 из лога RANGECMPB), эфемериды GPS (RAWEPHEM,
     полный битовый разбор подкадров по ICD-GPS-200), готовое
     позиционное решение приёмника (BESTPOS) и временные метки
     фотоснимков.
   - Собственный декодер покрывает только GPS (RANGECMPB/RAWEPHEM).
     ГЛОНАСС/Galileo/BeiDou/QZSS читаются из уже сконвертированного
     файла .obs/.nav (внешним инструментом производителя), так как
     эфемериды этих созвездий у ComNav используют недокументированные
     идентификаторы логов.

2. Анализ спутников
   - Среднее/минимальное/максимальное число видимых спутников по
     эпохам, в т.ч. по каждой группировке (GPS/GLONASS/Galileo/
     BeiDou/QZSS/SBAS).
   - Принимаемые частоты (коды сигналов) по каждой группировке —
     из заголовка RINEX OBS.
   - Самая и наименее используемая группировка спутников.
   - PDOP (геометрический фактор ухудшения точности) по эпохам —
     рассчитывается из положений GPS-спутников (по эфемеридам) и
     траектории приёмника.

3. Анализ фотосъёмки
   - Интервалы между снимками, разрывы, номинальная частота съёмки.
   - Сопоставление каждого фото с числом видимых спутников на момент
     съёмки и присвоение оценки качества (GOOD/NORMAL/LOW).

4. Траектория и позиционирование
   - Трек миссии (широта/долгота) с метками фото, окрашенными по
     качеству съёмки (зелёный/жёлтый/красный).
   - Профиль высоты полёта (MSL) по времени.
   - Точность позиционирования: тип решения (SINGLE/RTK/...) и
     среднеквадратичные отклонения широты/долготы/высоты — критично
     для оценки абсолютной точности привязки ортофотоплана.

5. Итоговая оценка миссии
   - Комбинированная оценка (ОТЛИЧНО/ХОРОШО/НОРМАЛЬНО/ПЛОХО) на
     основе качества фотосъёмки, качества GNSS-сигнала и доли
     «хороших» фотографий.

--------------------------------------------------------------------
ВКЛАДКИ ПРИЛОЖЕНИЯ

1. Обзор миссии   — итоговые оценки, время/длительность, точность
                     позиционирования, высота, PDOP.
2. Спутники       — статистика по спутникам, частоты по
                     группировкам, PDOP.
3. Качество фото  — интервалы съёмки, разрывы, итоговое качество.
4. Итоговый отчёт — сводный отчёт по миссии.
5. Графики        — спутники по времени, интервалы фото, гистограмма
                     интервалов, профиль высоты, PDOP по времени.
6. Файлы результата — ссылки на сохранённые CSV/TXT/PDF-отчёты с
                     кнопками «Просмотр» и «Открыть папку с файлами».

Карта траектории миссии всегда видна в нижней части окна независимо
от выбранной вкладки.

--------------------------------------------------------------------
СОХРАНЯЕМЫЕ ФАЙЛЫ

- photo_satellite_report.csv — таблица фото/спутники/качество.
- mission_report.txt / mission_report.pdf — итоговый отчёт с
  графиками.
- satellites.png, photo_intervals.png, photo_histogram.png,
  trajectory.png, altitude_profile.png, pdop.png — графики.

Все файлы сохраняются в подпапки decoded/plots/reports рядом с
исходным .cnb файлом.

--------------------------------------------------------------------
ОГРАНИЧЕНИЯ

- Расчёт PDOP и собственный декодер OBS/NAV используют только GPS.
- Позиционирование (BESTPOS) — решение самого приёмника (обычно
  одноточечное, без RTK/PPK); программа не выполняет собственных
  вычислений координат.
- Просмотр PDF-отчёта открывается во внешней программе по умолчанию.
"""

CRITERIA_TOOLTIPS = {
    "final_score": (
        "Итоговая оценка миссии — сумма баллов:\n"
        "• Качество фото и Качество GNSS дают от 1 до 4 баллов\n"
        "  (ПЛОХО=1, НОРМАЛЬНО=2, ХОРОШО=3, ОТЛИЧНО=4)\n"
        "• Доля хороших фото: +2 балла если ≥95%, +1 если ≥90%,\n"
        "  -1 балл если <80%\n\n"
        "Итог: ОТЛИЧНО ≥8, ХОРОШО ≥6, НОРМАЛЬНО ≥4, иначе ПЛОХО."
    ),
    "photo_quality": (
        "Оценка качества фотосъёмки — по числу разрывов между\n"
        "снимками (интервал более чем в 2 раза превышает\n"
        "номинальный):\n\n"
        "ОТЛИЧНО — разрывов нет\n"
        "ХОРОШО — менее 5 разрывов\n"
        "ВНИМАНИЕ — от 5 до 19 разрывов\n"
        "ПЛОХО — 20 и более разрывов"
    ),
    "gnss_quality": (
        "Оценка качества GNSS — по среднему числу видимых\n"
        "спутников за всю миссию:\n\n"
        "ОТЛИЧНО — 20 и более спутников\n"
        "ХОРОШО — от 15 до 19\n"
        "НОРМАЛЬНО — от 10 до 14\n"
        "ПЛОХО — менее 10"
    ),
}


class Tooltip:

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self.tip is not None or not self.text:
            return

        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + 18

        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            foreground="#000000",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=6,
            pady=4
        )
        label.pack()

    def _hide(self, event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def _windows_dark_mode():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0  # 0 = тёмная, 1 = светлая
    except Exception:
        return False


class GnssAnalyzerApp:

    def __init__(self, root):
        self.root = root
        self.root.title(f"OMJET GNSS Analyzer v{APP_VERSION}")
        self.root.geometry("1900x1000")

        self.cnb_file = None
        self.result = None
        self.plot_images = []
        self.overview_photo = None
        self._map_widget = None
        self._geomarks_tree = None
        self._geomarks_count_label = None
        self._height_filter_var = None
        self._height_pct_var = None
        self._excluded_ids = set()
        self._geomarks_iid_map = {}
        self._tree_hovered_item = None
        self.dark_mode = tk.BooleanVar(value=_windows_dark_mode())
        self._basemap_var = tk.StringVar(value=DEFAULT_BASEMAP)
        self._text_widgets = []
        self._canvases = []
        self._queue = queue.Queue()

        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self._set_window_icon()
        self.root.after(100, self._apply_titlebar_theme)
        self._build_top_bar()
        self._build_progress_bar()
        self._build_status_bar()
        self._build_main_area()

        self._apply_theme()

    def _make_help_icon(self, parent, tooltip_text, size=16, command=None):
        canvas = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bd=0)
        canvas.create_oval(1, 1, size - 1, size - 1, outline="#777777", fill="#dddddd")
        canvas.create_text(
            size // 2, size // 2,
            text="?",
            font=("Segoe UI", max(8, size // 2), "bold"),
            fill="#333333"
        )

        if command is not None:
            canvas.bind("<Button-1>", lambda e: command())
            canvas.configure(cursor="hand2")

        if tooltip_text:
            Tooltip(canvas, tooltip_text)

        return canvas

    def _show_help(self):
        theme = DARK_THEME if self.dark_mode.get() else LIGHT_THEME

        window = tk.Toplevel(self.root)
        window.title("Справка о программе")
        window.geometry("700x800")
        window.configure(bg=theme["bg"])

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))
        text.configure(background=theme["text_bg"], foreground=theme["text_fg"])
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, HELP_TEXT.format(version=APP_VERSION, author=APP_AUTHOR))
        text.configure(state=tk.DISABLED)

    def _set_window_icon(self):
        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except tk.TclError:
                pass

    def _apply_titlebar_theme(self, window=None):
        """Apply dark/light title bar via Windows DWM API."""
        if window is None:
            window = self.root
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            dark = 1 if self.dark_mode.get() else 0
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11), 19 (Windows 10)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr,
                    ctypes.byref(ctypes.c_int(dark)),
                    ctypes.sizeof(ctypes.c_int)
                )
        except Exception:
            pass

    def _build_logo_bar(self):
        frame = ttk.Frame(self.root, padding=(8, 8, 8, 0))
        frame.pack(side=tk.TOP, fill=tk.X)

        top_row = ttk.Frame(frame)
        top_row.pack(side=tk.TOP, fill=tk.X)

        help_icon = self._make_help_icon(
            top_row, "Справка о программе", size=24, command=self._show_help
        )
        help_icon.pack(side=tk.RIGHT)

        if os.path.exists(LOGO_PATH):
            image = Image.open(LOGO_PATH)
            image.thumbnail((220, 70))
            self.logo_photo = ImageTk.PhotoImage(image)
            ttk.Label(frame, image=self.logo_photo).pack(side=tk.TOP, anchor=tk.CENTER)

    def _build_top_bar(self):
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(
            bar,
            text="Выбрать файл...",
            command=self.choose_file
        ).pack(side=tk.LEFT)

        self.file_label = ttk.Label(bar, text="Файл не выбран")
        self.file_label.pack(side=tk.LEFT, padx=10)

        ttk.Checkbutton(
            bar,
            text="Тёмная тема",
            variable=self.dark_mode,
            command=self._apply_theme
        ).pack(side=tk.RIGHT, padx=10)

        self._last_dir = None

    def _build_progress_bar(self):
        frame = ttk.Frame(self.root, padding=(8, 0))
        frame.pack(side=tk.TOP, fill=tk.X)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            frame,
            orient=tk.HORIZONTAL,
            mode="determinate",
            maximum=100,
            variable=self.progress_var
        )
        self.progress_bar.pack(side=tk.TOP, fill=tk.X)

    def _build_status_bar(self):
        self.status_var = tk.StringVar(value="Готово")
        status = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=4
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _apply_theme(self):
        self._apply_titlebar_theme()
        theme = DARK_THEME if self.dark_mode.get() else LIGHT_THEME

        self.root.configure(bg=theme["bg"])

        self.style.configure(".", background=theme["bg"], foreground=theme["fg"])
        self.style.configure("TFrame", background=theme["bg"])
        self.style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
        self.style.configure("TButton", background=theme["bg"], foreground=theme["fg"])
        self.style.configure("TCheckbutton", background=theme["bg"], foreground=theme["fg"])
        self.style.configure(
            "TNotebook", background=theme["bg"], borderwidth=0
        )
        self.style.configure(
            "TNotebook.Tab", background=theme["bg"], foreground=theme["fg"]
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", theme["select_bg"])],
            foreground=[("selected", theme["select_fg"])]
        )
        self.style.configure(
            "TProgressbar", background=theme["select_bg"], troughcolor=theme["bg"]
        )

        for widget in self._text_widgets:
            widget.configure(
                background=theme["text_bg"],
                foreground=theme["text_fg"],
                insertbackground=theme["text_fg"]
            )

        for canvas in self._canvases:
            canvas.configure(background=theme["bg"], highlightbackground=theme["bg"])

    def _build_main_area(self):
        # Outer horizontal split: left (tabs+map) | right (geomarks table)
        outer_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        outer_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left side: vertical split tabs on top, map below
        left_frame = ttk.Frame(outer_pane)
        outer_pane.add(left_frame, weight=3)

        self.main_paned = ttk.PanedWindow(left_frame, orient=tk.VERTICAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(self.main_paned)
        self.main_paned.add(self.notebook, weight=2)

        self.trajectory_panel, self.overview_image_label = self._build_map_panel()
        self.main_paned.add(self.trajectory_panel, weight=3)

        # Right side: geomarks table full height
        self._build_geomarks_panel(outer_pane)

        self.tab_overview_left, self.tab_overview_right = self._make_overview_tab("Обзор миссии")
        self.tab_satellites = self._make_text_tab("Спутники")
        self.tab_photo = self._make_text_tab("Качество фото")
        self.tab_report = self._make_text_tab("Итоговый отчёт")
        self.tab_plots = self._make_plots_tab("Графики")
        self.tab_files = self._make_files_tab("Файлы результата")

        self.notebook.bind(
            "<<NotebookTabChanged>>",
            lambda e: self.root.after(20, self._adjust_sash)
        )

    def _adjust_sash(self):
        current = self.notebook.select()
        if not current:
            return

        tab_frame = self.notebook.nametowidget(current)
        tab_frame.update_idletasks()
        content_height = tab_frame.winfo_reqheight()

        self.main_paned.update_idletasks()
        paned_height = self.main_paned.winfo_height()
        if paned_height <= 1:
            return

        tab_strip_height = 30
        min_trajectory_height = 220

        target = content_height + tab_strip_height
        target = max(120, min(target, paned_height - min_trajectory_height))

        try:
            self.main_paned.sashpos(0, int(target))
        except tk.TclError:
            pass

    def _build_map_panel(self):
        frame = ttk.Frame(self.main_paned, padding=(0, 4, 0, 0))

        header = ttk.Frame(frame)
        header.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(
            header,
            text="Траектория миссии",
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        ttk.Label(header, text="  Подложка:").pack(side=tk.LEFT)
        basemap_cb = ttk.Combobox(
            header,
            textvariable=self._basemap_var,
            values=BASEMAP_KEYS,
            state="readonly",
            width=22,
        )
        basemap_cb.pack(side=tk.LEFT, padx=(4, 0))
        basemap_cb.bind("<<ComboboxSelected>>", self._on_basemap_changed)

        self._map_widget = MapWidget(frame, basemap=self._basemap_var.get())
        self._map_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))

        return frame, self._map_widget

    def _build_geomarks_panel(self, parent_pane):
        frame = ttk.Frame(parent_pane, padding=(4, 4, 0, 0))
        parent_pane.add(frame, weight=1)

        # header row: title + counts + filter controls
        header = ttk.Frame(frame)
        header.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))

        ttk.Label(
            header,
            text="Геометки",
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        self._geomarks_count_label = ttk.Label(header, text="", font=("Segoe UI", 9))
        self._geomarks_count_label.pack(side=tk.LEFT, padx=(6, 0))

        # right side controls
        self._height_filter_var = tk.BooleanVar(value=True)
        self._height_pct_var = tk.StringVar(value="10")

        ttk.Combobox(
            header,
            textvariable=self._height_pct_var,
            values=["5", "10", "15", "20", "25", "30"],
            state="readonly",
            width=4,
        ).pack(side=tk.RIGHT, padx=(0, 2))
        ttk.Label(header, text="% от ср. высоты").pack(side=tk.RIGHT)
        ttk.Checkbutton(
            header,
            text="Фильтр по высоте",
            variable=self._height_filter_var,
            command=self._on_height_filter_changed,
        ).pack(side=tk.RIGHT, padx=(0, 8))

        self._height_pct_var.trace_add("write", lambda *_: self._on_height_filter_changed())

        cols = ("!", "№", "Время", "Широта", "Долгота", "Высота, м", "Спутники", "Качество")
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        col_widths = (28, 40, 130, 105, 105, 85, 75, 75)
        for col, w in zip(cols, col_widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor=tk.CENTER, stretch=(col != "!"))
        tree.column("!", stretch=False)

        tree.tag_configure("GOOD",      background="#1a3a1a", foreground="#88ff88")
        tree.tag_configure("NORMAL",    background="#3a3a1a", foreground="#ffee88")
        tree.tag_configure("LOW",       background="#3a1a1a", foreground="#ff8888")
        tree.tag_configure("FILTERED",  background="#3a0000", foreground="#ff4444")
        tree.tag_configure("EXCLUDED",  background="#2a2a2a", foreground="#666666")
        tree.tag_configure("HOVERED",   background="#1a3a5a", foreground="#ffffff")

        # context menu
        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(label="Исключить из вывода", command=lambda: self._exclude_selected())
        menu.add_command(label="Восстановить",        command=lambda: self._restore_selected())

        def _show_menu(event):
            item = tree.identify_row(event.y)
            if item and item not in tree.selection():
                tree.selection_set(item)
            if tree.selection():
                menu.tk_popup(event.x_root, event.y_root)

        tree.bind("<Button-3>", _show_menu)
        tree.bind("<Motion>",  self._on_tree_hover)
        tree.bind("<Leave>",   lambda _e: self._on_tree_leave())

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._geomarks_tree = tree
        self._excluded_ids = set()  # photo_id excluded manually

        if self._map_widget:
            self._map_widget.set_hover_callback(self._on_map_hover)

    def _make_overview_tab(self, title):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)

        frame.columnconfigure(0, weight=1, uniform="overview_cols")
        frame.columnconfigure(1, weight=1, uniform="overview_cols")
        frame.rowconfigure(0, weight=0)

        left = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
        left.grid(row=0, column=0, sticky="new")
        left.configure(state=tk.DISABLED)
        self._text_widgets.append(left)

        right = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=("Consolas", 10))
        right.grid(row=0, column=1, sticky="new", padx=(8, 0))
        right.configure(state=tk.DISABLED)
        self._text_widgets.append(right)

        return left, right

    def _make_text_tab(self, title):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)

        text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.configure(state=tk.DISABLED)
        self._text_widgets.append(text)
        return text

    def _make_plots_tab(self, title):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)

        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)

        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda e: self._on_plots_canvas_resize(e, window_id))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvases.append(canvas)
        self.plots_canvas = canvas
        self._plot_entries = []

        return inner

    def _on_plots_canvas_resize(self, event, window_id):
        self.plots_canvas.itemconfig(window_id, width=event.width)
        self._render_plot_images(event.width)

    def _render_plot_images(self, width=None):
        if not self._plot_entries:
            return

        if width is None:
            width = self.plots_canvas.winfo_width()

        width = max(width - 20, 1)

        for entry in self._plot_entries:
            source = entry["image"]
            ratio = source.height / source.width
            height = max(int(width * ratio), 1)

            resized = source.resize((width, height), Image.LANCZOS)
            entry["photo"] = ImageTk.PhotoImage(resized)
            entry["label"].configure(image=entry["photo"])

    def _make_files_tab(self, title):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=title)
        return frame

    def _set_text(self, widget, content):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.configure(state=tk.DISABLED)

    def _render_lines(self, widget, lines):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)

        for line in lines:
            if isinstance(line, tuple) and line[0] == "quality":
                _, label, value, kind = line
                translated = QUALITY_RU.get(value, value)
                color = QUALITY_COLOR.get(value, "#000000")
                tag = f"quality_{value}"

                if tag not in widget.tag_names():
                    widget.tag_configure(tag, font=("Consolas", 10, "bold"), foreground=color)

                widget.insert(tk.END, label)
                widget.insert(tk.END, f"{translated} ●  ", tag)

                icon = self._make_help_icon(widget, CRITERIA_TOOLTIPS.get(kind, ""))
                widget.window_create(tk.END, window=icon)
                widget.insert(tk.END, "\n")
            else:
                widget.insert(tk.END, line + "\n")

        widget.configure(state=tk.DISABLED)

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Выберите CNB файл",
            initialdir=self._last_dir,
            filetypes=[("CNB файлы", "*.cnb"), ("Все файлы", "*.*")]
        )
        if not path:
            return

        self._last_dir = os.path.dirname(path)

        obs_path = path + ".obs"
        obs_path_gz = path + ".obs.gz"
        if not os.path.isfile(obs_path) and not os.path.isfile(obs_path_gz):
            self.status_var.set(
                f"⚠ Не найден {os.path.basename(obs_path)} — конвертируйте .cnb в RINEX OBS"
            )
            messagebox.showwarning(
                "Отсутствует файл OBS",
                f"Файл наблюдений RINEX OBS не найден:\n\n"
                f"{obs_path}\n\n"
                f"Сконвертируйте .cnb с помощью утилиты производителя "
                f"(CnbConverter / NovAtel Convert). Файл должен называться\n"
                f"«{os.path.basename(obs_path)}» или «{os.path.basename(obs_path_gz)}» "
                f"и лежать в той же папке.\n\n"
                f"После появления файла выберите .cnb снова."
            )
            return

        self.cnb_file = path
        self.file_label.configure(text=os.path.basename(path))
        self.status_var.set(f"Выбран файл: {path}")
        self.run_analysis()

    def run_analysis(self):
        if not self.cnb_file:
            return

        self.progress_var.set(0)
        self.status_var.set("Анализ выполняется...")

        thread = threading.Thread(target=self._run_analysis_worker, daemon=True)
        thread.start()

        self.root.after(100, self._poll_queue)

    def _on_progress(self, percent, message):
        # Called from the worker thread -- never touch Tk widgets here,
        # just hand the update off through the thread-safe queue.
        self._queue.put(("progress", percent, message))

    def _poll_queue(self):
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]

                if kind == "progress":
                    _, percent, message = item
                    self.progress_var.set(percent)
                    self.status_var.set(f"{message} ({percent}%)")

                elif kind == "done":
                    _, result = item
                    self._on_analysis_done(result)
                    return

                elif kind == "error":
                    _, exc, error_text = item
                    self._on_analysis_error(exc, error_text)
                    return

        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)

    def _on_basemap_changed(self, _event=None):
        if self._map_widget:
            self._map_widget.set_basemap(self._basemap_var.get())

    def _run_analysis_worker(self):
        try:
            result = run_pipeline(
                self.cnb_file,
                progress_callback=self._on_progress,
                basemap=self._basemap_var.get(),
            )
        except Exception as exc:
            error_text = traceback.format_exc()
            self._queue.put(("error", exc, error_text))
            return

        self._queue.put(("done", result))

    def _on_analysis_error(self, exc, error_text):
        self.status_var.set("Ошибка анализа")
        messagebox.showerror("Ошибка анализа", f"{exc}\n\n{error_text}")

    def _on_analysis_done(self, result):
        self.result = result
        self.status_var.set("Анализ завершён")

        self._fill_overview(result)
        self._fill_geomarks(result)
        self._fill_satellites(result)
        self._fill_photo_quality(result)
        self._fill_report(result)
        self._fill_plots(result)
        self._fill_files(result)

        self.notebook.select(0)
        self.root.after(50, self._adjust_sash)

    def _fit_separator(self, widget, char="="):
        widget.update_idletasks()
        width_px = max(widget.winfo_width() - 12, 10)
        font = tkfont.Font(font=widget.cget("font"))
        char_width = max(font.measure(char), 1)
        count = max(10, width_px // char_width)
        return char * count

    def _fill_overview(self, result):
        mission = result["mission_data"]
        trajectory = result["trajectory"]
        time_result = result["time_result"]

        start = str(time_result["start"]).replace("T", " ")
        end = str(time_result["end"]).replace("T", " ")

        sep_left = self._fit_separator(self.tab_overview_left, "=")
        sep_right = self._fit_separator(self.tab_overview_right, "-")

        left_lines = [
            "ОБЗОР МИССИИ",
            sep_left,
            "",
            ("quality", "Итоговая оценка    : ", mission["final_score"], "final_score"),
            ("quality", "Качество фото      : ", mission["photo_quality"], "photo_quality"),
            ("quality", "Качество GNSS      : ", mission["gnss_quality"], "gnss_quality"),
            f"Доля хороших фото  : {mission['good_percent']:.1f}%",
            "",
            f"Время начала (UTC) : {start}",
            f"Время окончания    : {end}",
            f"Длительность полёта: {mission['flight_duration_min']:.1f} мин",
            f"Интервал записи    : {time_result['median_interval']:.3f} сек ({time_result['nominal_rate_hz']:.1f} Гц)",
            f"Количество фото    : {mission['photo_count']}{self._filtered_photo_label(result)}",
            f"Уникальных спутников: {mission['unique_satellites']}",
        ]

        if trajectory["points"]:
            left_lines.append("")
            left_lines.append(f"Точек траектории   : {len(trajectory['points'])}")
            left_lines.append(f"Длина траектории   : {trajectory['distance_m']:.1f} м")

        right_lines = []

        accuracy = trajectory.get("position_accuracy")
        if accuracy:
            right_lines += [
                "ТОЧНОСТЬ ПОЗИЦИОНИРОВАНИЯ",
                sep_right,
                f"Тип решения        : {accuracy['dominant_type']}",
                f"σ широты (среднее) : {accuracy['avg_lat_sigma']:.2f} м",
                f"σ долготы (среднее): {accuracy['avg_lon_sigma']:.2f} м",
                f"σ высоты (среднее) : {accuracy['avg_height_sigma']:.2f} м",
            ]
            if accuracy["dominant_type"] == "SINGLE":
                right_lines.append(
                    "Внимание: автономное решение (без RTK/PPK) — точность "
                    "метровая, недостаточная для точной привязки ортофотоплана."
                )
            right_lines.append("")

        altitude = trajectory.get("altitude")
        if altitude:
            right_lines += [
                "ВЫСОТА ПОЛЁТА",
                sep_right,
                f"Средняя высота     : {altitude['avg_height']:.1f} м",
                f"Мин / Макс         : {altitude['min_height']:.1f} / {altitude['max_height']:.1f} м",
                f"Разброс высоты     : {altitude['height_range']:.1f} м",
                "",
            ]

        pdop = result.get("pdop")
        if pdop:
            right_lines += [
                "ГЕОМЕТРИЯ СПУТНИКОВ (PDOP, GPS)",
                sep_right,
                f"Средний PDOP       : {pdop['avg_pdop']:.2f}",
                f"Максимальный PDOP  : {pdop['max_pdop']:.2f}",
                f"Эпох с PDOP > 6    : {pdop['poor_count']} из {pdop['samples']}",
            ]

        self.tab_overview_left.configure(height=len(left_lines))
        self.tab_overview_right.configure(height=len(right_lines))

        self._render_lines(self.tab_overview_left, left_lines)
        self._render_lines(self.tab_overview_right, right_lines)

        if self._map_widget:
            traj = result["trajectory"]
            photo_report = result["photo_report"]
            matched_fixes = result.get("matched_fixes", [])
            photo_points = [
                {**fix,
                 "quality": photo_report[i]["quality"],
                 "height": photo_report[i].get("height"),
                 "photo_id": photo_report[i]["photo_id"]}
                for i, fix in enumerate(matched_fixes)
            ]
            self._map_widget.set_data(
                traj["points"], photo_points,
                height_filter=bool(self._height_filter_var and self._height_filter_var.get()),
                height_pct=self._get_height_threshold_pct(),
                excluded_ids=self._excluded_ids,
            )

    def _get_height_threshold_pct(self):
        try:
            return float(self._height_pct_var.get()) / 100.0 if self._height_pct_var else 0.10
        except (ValueError, AttributeError):
            return 0.10

    def _exclude_selected(self):
        if not self._geomarks_tree:
            return
        for item in self._geomarks_tree.selection():
            vals = self._geomarks_tree.item(item, "values")
            try:
                self._excluded_ids.add(int(vals[1]))
            except (IndexError, ValueError):
                pass
        self._refresh_after_exclusion()

    def _restore_selected(self):
        if not self._geomarks_tree:
            return
        for item in self._geomarks_tree.selection():
            vals = self._geomarks_tree.item(item, "values")
            try:
                self._excluded_ids.discard(int(vals[1]))
            except (IndexError, ValueError):
                pass
        self._refresh_after_exclusion()

    def _refresh_after_exclusion(self):
        if not self.result:
            return
        self._fill_geomarks(self.result)
        self._rewrite_csv(self.result)
        if self._map_widget:
            self._map_widget.update_filter(
                height_filter=bool(self._height_filter_var and self._height_filter_var.get()),
                height_pct=self._get_height_threshold_pct(),
                excluded_ids=self._excluded_ids,
            )

    def _on_height_filter_changed(self):
        if self.result:
            self._fill_geomarks(self.result)
            self._rewrite_csv(self.result)
            if self._map_widget:
                self._map_widget.update_filter(
                    height_filter=bool(self._height_filter_var and self._height_filter_var.get()),
                    height_pct=self._get_height_threshold_pct(),
                    excluded_ids=self._excluded_ids,
                )

    def _fill_geomarks(self, result):
        if self._geomarks_tree is None:
            return
        tree = self._geomarks_tree
        tree.delete(*tree.get_children())
        self._geomarks_iid_map = {}
        self._tree_hovered_item = None

        report = result["photo_report"]
        heights = [r["height"] for r in report if r.get("height") is not None]
        pct = self._get_height_threshold_pct()

        if heights:
            avg_h = sum(heights) / len(heights)
            threshold = avg_h * pct
        else:
            avg_h = None
            threshold = None

        total = len(report)
        filtered_count = 0
        excluded_count = 0

        for r in report:
            lat = f"{r['lat']:.7f}" if r.get("lat") is not None else "—"
            lon = f"{r['lon']:.7f}" if r.get("lon") is not None else "—"
            height = f"{r['height']:.1f}" if r.get("height") is not None else "—"
            time_str = r["time"].strftime("%H:%M:%S.%f")[:-3] if hasattr(r["time"], "strftime") else str(r["time"])
            quality = r["quality"]
            photo_id = r["photo_id"]

            manually_excluded = photo_id in self._excluded_ids
            height_filtered = (
                self._height_filter_var and self._height_filter_var.get()
                and avg_h is not None
                and r.get("height") is not None
                and abs(r["height"] - avg_h) > threshold
            )

            if manually_excluded:
                excluded_count += 1
                indicator = "⬛"
                tags = ("EXCLUDED",)
            elif height_filtered:
                filtered_count += 1
                indicator = "🔴"
                tags = ("FILTERED",)
            else:
                indicator = ""
                tags = (quality,)

            iid = tree.insert("", tk.END, values=(
                indicator, photo_id, time_str, lat, lon, height, r["satellites"], quality
            ), tags=tags)
            self._geomarks_iid_map[photo_id] = iid

        if self._geomarks_count_label:
            kept = total - filtered_count - excluded_count
            self._geomarks_count_label.configure(
                text=f"(всего: {total},  в диапазоне: {kept},  отфильтровано: {filtered_count},  исключено: {excluded_count})"
            )

    # ── hover highlight: table ↔ map ─────────────────────────────────────────

    def _on_tree_hover(self, event):
        if not self._geomarks_tree:
            return
        item = self._geomarks_tree.identify_row(event.y)
        if item:
            vals = self._geomarks_tree.item(item, "values")
            if vals:
                try:
                    photo_id = int(vals[1])
                except (ValueError, IndexError):
                    photo_id = None
                if photo_id is not None and self._map_widget:
                    self._map_widget.highlight_point(photo_id)
            self._set_tree_hover(item)
        else:
            if self._map_widget:
                self._map_widget.highlight_point(None)
            self._set_tree_hover(None)

    def _on_tree_leave(self):
        self._set_tree_hover(None)
        if self._map_widget:
            self._map_widget.highlight_point(None)

    def _on_map_hover(self, photo_id):
        if not self._geomarks_tree:
            return
        item = self._geomarks_iid_map.get(photo_id) if photo_id is not None else None
        self._set_tree_hover(item)
        if item:
            self._geomarks_tree.see(item)

    def _set_tree_hover(self, new_item):
        old_item = self._tree_hovered_item
        if old_item and old_item != new_item:
            tags = list(self._geomarks_tree.item(old_item, "tags"))
            if "HOVERED" in tags:
                tags.remove("HOVERED")
            self._geomarks_tree.item(old_item, tags=tags)
        if new_item and new_item != old_item:
            tags = list(self._geomarks_tree.item(new_item, "tags"))
            if "HOVERED" not in tags:
                tags.append("HOVERED")
            self._geomarks_tree.item(new_item, tags=tags)
        self._tree_hovered_item = new_item

    def _fill_satellites(self, result):
        sat = result["sat_result"]

        lines = [
            "АНАЛИЗ СПУТНИКОВ",
            "=" * 50,
            "",
            f"Среднее число спутников : {sat['avg_satellites']:.1f}",
            f"Минимум                 : {sat['min_satellites']}",
            f"Максимум                : {sat['max_satellites']}",
            "",
            f"GPS (среднее)     : {sat['gps_avg']:.1f}",
            f"GLONASS (среднее) : {sat['glo_avg']:.1f}",
            f"Galileo (среднее) : {sat['gal_avg']:.1f}",
            f"BeiDou (среднее)  : {sat['bds_avg']:.1f}",
            "",
            f"Уникальных спутников : {sat['unique_satellites']}",
        ]

        signal_summary = result.get("signal_summary")
        if signal_summary:
            lines.append("")
            lines.append("ПРИНИМАЕМЫЕ ЧАСТОТЫ ПО ГРУППИРОВКАМ")
            lines.append("-" * 50)
            for group in signal_summary["groups"]:
                avg = group["avg_satellites"]
                avg_text = f", в среднем {avg:.1f} спутн." if avg is not None else ""
                lines.append(f"{group['system']:10}: {', '.join(group['codes'])}{avg_text}")

            lines.append("")
            if signal_summary["most_used"]:
                lines.append(f"Самая используемая группировка   : {signal_summary['most_used']}")
            if signal_summary["least_used"]:
                lines.append(f"Наименее используемая группировка: {signal_summary['least_used']}")

        pdop = result.get("pdop")
        if pdop:
            lines.append("")
            lines.append("PDOP (геометрия GPS-спутников)")
            lines.append("-" * 50)
            lines.append(f"Средний PDOP    : {pdop['avg_pdop']:.2f}")
            lines.append(f"Максимальный    : {pdop['max_pdop']:.2f}")
            lines.append(f"Плохих эпох (>6): {pdop['poor_count']} из {pdop['samples']}")

        self._set_text(self.tab_satellites, "\n".join(lines))

    def _fill_photo_quality(self, result):
        quality = result["photo_quality"]

        excluded = quality.get("excluded_count", 0)
        cluster_size = quality.get("cluster_size", 0)
        lines = [
            "КАЧЕСТВО ФОТОСЪЁМКИ",
            "=" * 50,
            "",
            f"Фото в основном массиве : {cluster_size}",
            f"Точек на удалении       : {excluded}" if excluded else "",
            f"Номинальный интервал    : {quality['median_interval']:.3f} сек",
            f"Стд. отклонение         : {quality['std_dev']:.3f} сек",
            f"95-й перцентиль         : {quality['p95']:.3f} сек",
            f"Самый большой разрыв    : {quality['longest_gap']:.3f} сек",
            f"Количество разрывов     : {quality['gap_count']}",
            ("quality", "Качество (без удалённых): ", quality["quality"], "photo_quality"),
        ]
        self._render_lines(self.tab_photo, lines)

    def _fill_report(self, result):
        mission = result["mission_data"]

        lines = [
            "ИТОГОВЫЙ ОТЧЁТ ПО МИССИИ",
            "=" * 50,
            "",
            ("quality", "Качество фото      : ", mission["photo_quality"], "photo_quality"),
            ("quality", "Качество GNSS      : ", mission["gnss_quality"], "gnss_quality"),
            f"Хороших фото       : {mission['good_percent']:.1f}%",
            "",
            f"ХОРОШО (GOOD)      : {mission['good_count']}",
            f"НОРМАЛЬНО (NORMAL) : {mission['normal_count']}",
            f"ПЛОХО (LOW)        : {mission['low_count']}",
            "",
            f"Среднее число спутников : {mission['avg_satellites']:.1f}",
            f"Минимум спутников       : {mission['min_satellites']}",
            f"Максимум спутников      : {mission['max_satellites']}",
            "",
            ("quality", "ИТОГОВАЯ ОЦЕНКА    : ", mission["final_score"], "final_score"),
        ]

        self._render_lines(self.tab_report, lines)

    def _fill_plots(self, result):
        for child in self.tab_plots.winfo_children():
            child.destroy()
        self.plot_images = []
        self._plot_entries = []

        titles = {
            "satellites": "Спутники по времени",
            "photo_intervals": "Интервалы между фото",
            "photo_histogram": "Гистограмма интервалов",
            "altitude_profile": "Профиль высоты полёта",
            "pdop": "PDOP по времени (GPS)",
        }

        for key, path in result["plots"].items():
            if key == "trajectory":
                continue
            if not path or not os.path.exists(path):
                continue

            ttk.Label(
                self.tab_plots,
                text=titles.get(key, key),
                font=("Segoe UI", 11, "bold")
            ).pack(anchor=tk.W, fill=tk.X, pady=(10, 2))

            label = ttk.Label(self.tab_plots)
            label.pack(anchor=tk.W, fill=tk.X)

            self._plot_entries.append({
                "image": Image.open(path),
                "label": label,
                "photo": None,
            })

        self.plots_canvas.update_idletasks()
        self._render_plot_images(self.plots_canvas.winfo_width())

    def _fill_files(self, result):
        for child in self.tab_files.winfo_children():
            child.destroy()

        reports_dir = result["runner"].reports_dir

        top = ttk.Frame(self.tab_files, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(
            top,
            text="Открыть папку с файлами",
            command=lambda: self._open_folder(reports_dir)
        ).pack(side=tk.LEFT)

        # --- фильтр по высоте ---
        filter_frame = ttk.Frame(self.tab_files, padding=(8, 6, 8, 0))
        filter_frame.pack(side=tk.TOP, fill=tk.X)

        self._filter_height_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            filter_frame,
            text="Отфильтровать метки по высоте",
            variable=self._filter_height_var,
            command=lambda: self._rewrite_csv(result),
        ).pack(side=tk.LEFT)

        tooltip_text = (
            "При включении из CSV-отчёта исключаются геометки,\n"
            "высота которых отличается от средней высоты полёта\n"
            "более чем на 10%.\n\n"
            "Это позволяет убрать снимки, сделанные на взлёте\n"
            "или посадке, которые не входят в рабочий маршрут."
        )
        icon = self._make_help_icon(filter_frame, tooltip_text)
        filter_frame.after(10, lambda: icon.pack(side=tk.LEFT, padx=(4, 0)))

        # применяем фильтр сразу при открытии вкладки
        self._rewrite_csv(result)

        ttk.Label(
            self.tab_files,
            text="СОХРАНЁННЫЕ ФАЙЛЫ",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor=tk.W, padx=8, pady=(10, 4))

        file_labels = {
            "csv": "CSV-отчёт (фото/спутники)",
            "txt": "Текстовый отчёт",
            "pdf": "PDF-отчёт",
        }

        for key, path in result["files"].items():
            row = ttk.Frame(self.tab_files, padding=(8, 3))
            row.pack(side=tk.TOP, fill=tk.X)

            ttk.Label(
                row, text=file_labels.get(key, key), width=26, anchor=tk.W
            ).pack(side=tk.LEFT)

            ttk.Label(row, text=path, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

            ttk.Button(
                row, text="Просмотр",
                command=lambda p=path: self._view_file(p)
            ).pack(side=tk.RIGHT, padx=4)

    def _filtered_photo_label(self, result):
        report = result["photo_report"]
        heights = [r["height"] for r in report if r.get("height") is not None]
        if not heights:
            return ""
        avg_h = sum(heights) / len(heights)
        threshold = avg_h * self._get_height_threshold_pct()
        count = sum(1 for r in report
                    if r.get("height") is not None and abs(r["height"] - avg_h) <= threshold)
        return f"  (отфильтровано: {count})"

    def _rewrite_csv(self, result):
        import csv as _csv
        report = result["photo_report"]
        csv_path = result["files"]["csv"]

        heights = [r.get("height") for r in report if r.get("height") is not None]
        use_height_filter = self._height_filter_var and self._height_filter_var.get()
        if use_height_filter and heights:
            avg_h = sum(heights) / len(heights)
            threshold = avg_h * self._get_height_threshold_pct()
        else:
            avg_h = None
            threshold = None

        rows = []
        for r in report:
            if r["photo_id"] in self._excluded_ids:
                continue
            if avg_h is not None and r.get("height") is not None:
                if abs(r["height"] - avg_h) > threshold:
                    continue
            rows.append(r)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = _csv.writer(f)
            writer.writerow(["PhotoID", "Time", "Latitude", "Longitude", "Height_m",
                             "Satellites", "Quality"])
            for r in rows:
                writer.writerow([
                    r["photo_id"], r["time"],
                    f"{r['lat']:.8f}" if r.get("lat") is not None else "",
                    f"{r['lon']:.8f}" if r.get("lon") is not None else "",
                    f"{r['height']:.3f}" if r.get("height") is not None else "",
                    r["satellites"], r["quality"],
                ])

    def _open_folder(self, path):
        if not os.path.isdir(path):
            messagebox.showerror("Ошибка", f"Папка не найдена:\n{path}")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{exc}")

    def _view_file(self, path):
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", f"Файл не найден:\n{path}")
            return

        if path.lower().endswith(".pdf"):
            try:
                os.startfile(path)
            except OSError as exc:
                messagebox.showerror("Ошибка", f"Не удалось открыть PDF:\n{exc}")
            return

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as exc:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{exc}")
            return

        theme = DARK_THEME if self.dark_mode.get() else LIGHT_THEME

        window = tk.Toplevel(self.root)
        window.title(os.path.basename(path))
        window.geometry("700x500")
        window.configure(bg=theme["bg"])

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))
        text.configure(background=theme["text_bg"], foreground=theme["text_fg"])
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, content)
        text.configure(state=tk.DISABLED)


def main():
    root = tk.Tk()
    GnssAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
