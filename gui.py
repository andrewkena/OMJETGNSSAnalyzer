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
from plots.height_profile_widget import HeightProfileWidget

APP_VERSION = "0.26_15.07.2026"
APP_AUTHOR = "andrewkena"

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
ICON_PATH = os.path.join(ASSETS_DIR, "GNSS_logo.ico")
DONE_WAV  = os.path.join(ASSETS_DIR, "done.wav")


def _play_done():
    try:
        import winsound
        if os.path.isfile(DONE_WAV):
            winsound.PlaySound(DONE_WAV, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass

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
3. Качество геометок  — интервалы съёмки, разрывы, итоговое качество.
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
        "• Качество геометок и Качество GNSS дают от 1 до 4 баллов\n"
        "  (ПЛОХО=1, НОРМАЛЬНО=2, ХОРОШО=3, ОТЛИЧНО=4)\n"
        "• Доля хороших геометок: +2 балла если ≥95%, +1 если ≥90%,\n"
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


def _themed_messagebox(parent, title, message, dialog_type="info",
                       dark=True, apply_tb=None):
    """Themed replacement for tkinter.messagebox dialogs."""
    theme = DARK_THEME if dark else LIGHT_THEME
    result = [None]

    win = tk.Toplevel(parent)
    win.title(title)
    win.resizable(False, False)
    win.configure(bg=theme["bg"])
    win.grab_set()

    if os.path.exists(ICON_PATH):
        try:
            win.iconbitmap(ICON_PATH)
        except Exception:
            pass

    prefix = {"info": "ℹ  ", "warning": "⚠  ", "error": "✖  ", "yesno": "❓  "}.get(dialog_type, "")
    tk.Label(
        win, text=prefix + message,
        bg=theme["bg"], fg=theme["fg"],
        font=("Segoe UI", 10), justify=tk.LEFT,
        wraplength=440, padx=24, pady=18
    ).pack()

    btn_frame = tk.Frame(win, bg=theme["bg"])
    btn_frame.pack(pady=(0, 14))

    if dialog_type == "yesno":
        ttk.Button(btn_frame, text="Да",
                   command=lambda: (result.__setitem__(0, True), win.destroy())
                   ).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="Нет",
                   command=lambda: (result.__setitem__(0, False), win.destroy())
                   ).pack(side=tk.LEFT, padx=8)
    else:
        ttk.Button(btn_frame, text="OK", command=win.destroy).pack()

    win.update_idletasks()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    ww = win.winfo_reqwidth()
    wh = win.winfo_reqheight()
    win.geometry(f"+{px + (pw - ww) // 2}+{py + (ph - wh) // 2}")

    if apply_tb:
        win.after(80, lambda: apply_tb(win))

    win.focus_set()
    win.wait_window()
    return result[0]


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
        self._height_profile = None
        self._geomarks_tree = None
        self._geomarks_count_label = None
        self._height_filter_var = None
        self._height_pct_var = None
        self._filter_duplicates_var = None
        self._filter_h_range_var = None
        self._filter_h_min_var = None
        self._filter_h_max_var = None
        self._excluded_ids = set()
        self._filtered_ids_cache = set()
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
        self.root.after(400,  self._check_whats_new)
        self.root.after(2000, self._check_for_updates)

    # ── what's new ───────────────────────────────────────────────────────────

    _WHATS_NEW = """\
Версия 0.26  (15.07.2026)
══════════════════════════════════════════════════════

  ✦ Контур площади съёмки
      В окне Мультитрек вокруг каждого трека рисуется
      контур-полоса, повторяющий форму маршрута. Площадь
      считается по этим полосам с учётом перекрытий.
      Чекбокс «Площадь» скрывает/показывает контур,
      рядом — подсказка о методе расчёта.

  ✦ Средняя высота по горизонтальному полёту
      Средняя высота в разделе «Высота полёта» теперь
      считается только по крейсерскому участку, без
      набора высоты и снижения.

  ✦ Звук завершения в Мультитреке
      После загрузки и обработки всех треков звук
      воспроизводится один раз.


Версия 0.25  (14.07.2026)
══════════════════════════════════════════════════════

  ✦ Мультитрек
      Новая кнопка на панели инструментов открывает окно
      для сравнения нескольких CNB-файлов на одной карте.
      Каждый трек своим цветом, режим «В одном цвете»,
      маркеры начала/конца, легенда на карте.

  ✦ Экспорт KML
      Из окна Мультитрек треки можно сохранить в KML
      (Google Earth, Яндекс Карты, QGIS и др.).

  ✦ Статистика треков
      В правом нижнем углу карты Мультитрека показывается
      суммарная протяжённость маршрутов и площадь зоны
      съёмки (га / м²) по выпуклой оболочке точек.

  ✦ Поддержка .obs.gz
      Файл наблюдений RINEX теперь принимается как в виде
      обычного .cnb.obs, так и сжатого .cnb.obs.gz.

  ✦ Двустороннее подсвечивание (карта ↔ таблица)
      При наведении мыши на строку в таблице геометок
      соответствующая точка подсвечивается на карте,
      и наоборот.

  ✦ Организация результатов по файлам
      Все отчёты, графики и CSV теперь сохраняются
      в отдельную папку с именем анализируемого файла.

  ✦ Проверка обновлений
      При каждом запуске программа проверяет наличие
      новой версии на GitHub и предлагает скачать её.

  ✦ Установщик на русском языке
      Добавлен Setup-установщик с деинсталлятором
      и ярлыком на рабочем столе.
"""

    @staticmethod
    def _version_file_path():
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(appdata, "OMJET_GNSS_Analyzer", "last_version.txt")

    def _check_whats_new(self):
        try:
            vf = self._version_file_path()
            os.makedirs(os.path.dirname(vf), exist_ok=True)
            last = None
            if os.path.exists(vf):
                with open(vf, "r", encoding="utf-8") as f:
                    last = f.read().strip()
            if last != APP_VERSION:
                with open(vf, "w", encoding="utf-8") as f:
                    f.write(APP_VERSION)
                self._show_whats_new()
        except Exception:
            pass

    def _show_whats_new(self):
        import tkinter.scrolledtext as scrolledtext
        win = tk.Toplevel(self.root)
        win.title(f"Что нового в версии {APP_VERSION}")
        win.geometry("620x500")
        win.resizable(False, False)
        if os.path.exists(ICON_PATH):
            try:
                win.iconbitmap(ICON_PATH)
            except Exception:
                pass

        theme = DARK_THEME if self.dark_mode.get() else LIGHT_THEME
        win.configure(bg=theme["bg"])

        txt = scrolledtext.ScrolledText(
            win, wrap=tk.WORD, font=("Consolas", 10),
            background=theme["text_bg"], foreground=theme["text_fg"],
            relief=tk.FLAT, padx=16, pady=12, state=tk.NORMAL
        )
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        txt.insert(tk.END, self._WHATS_NEW)
        txt.configure(state=tk.DISABLED)

        ttk.Button(win, text="Понятно", command=win.destroy).pack(pady=10)

        win.after(100, lambda: self._apply_titlebar_theme_to(win))
        win.grab_set()
        win.focus_set()

    def _msginfo(self, title, message, parent=None):
        _themed_messagebox(parent or self.root, title, message, "info",
                           self.dark_mode.get(), self._apply_titlebar_theme_to)

    def _msgwarn(self, title, message, parent=None):
        _themed_messagebox(parent or self.root, title, message, "warning",
                           self.dark_mode.get(), self._apply_titlebar_theme_to)

    def _msgerror(self, title, message, parent=None):
        _themed_messagebox(parent or self.root, title, message, "error",
                           self.dark_mode.get(), self._apply_titlebar_theme_to)

    def _msgyesno(self, title, message, parent=None):
        return _themed_messagebox(parent or self.root, title, message, "yesno",
                                  self.dark_mode.get(), self._apply_titlebar_theme_to)

    def _apply_titlebar_theme_to(self, window):
        try:
            import ctypes
            from ctypes import c_int, sizeof
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            if not hwnd:
                hwnd = window.winfo_id()
            dark = c_int(1 if self.dark_mode.get() else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), sizeof(dark))
        except Exception:
            pass

    def _open_multitrack(self):
        MultitrackWindow(self.root, self)

    def _check_for_updates(self):
        threading.Thread(target=self._fetch_latest_version, daemon=True).start()

    def _fetch_latest_version(self):
        import webbrowser
        import json
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.github.com/repos/andrewkena/OMJETGNSSAnalyzer/releases/latest",
                headers={"User-Agent": "OMJET-GNSS-Analyzer"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            html_url = data.get("html_url", "")
            if not tag or tag == APP_VERSION:
                return
            current = self._parse_version_date(APP_VERSION)
            latest = self._parse_version_date(tag)
            if latest and current and latest > current:
                self.root.after(0, lambda: self._show_update_dialog(tag, html_url))
        except Exception:
            pass

    @staticmethod
    def _parse_version_date(version):
        from datetime import datetime
        try:
            return datetime.strptime(version.split("_", 1)[1], "%d.%m.%Y").date()
        except Exception:
            return None

    def _show_update_dialog(self, latest_tag, url):
        import webbrowser
        answer = self._msgyesno(
            "Доступна новая версия",
            f"Доступна новая версия программы:\n\n"
            f"  Новая:    {latest_tag}\n"
            f"  Текущая:  {APP_VERSION}\n\n"
            f"Открыть страницу загрузки на GitHub?"
        )
        if answer:
            webbrowser.open(url)

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

        ttk.Button(
            bar,
            text="Мультитрек",
            command=self._open_multitrack
        ).pack(side=tk.LEFT, padx=(6, 0))

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
        self.tab_photo = self._make_text_tab("Качество геометок")
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

        vpaned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        vpaned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))

        map_frame = ttk.Frame(vpaned)
        vpaned.add(map_frame, weight=1)

        self._map_widget = MapWidget(map_frame, basemap=self._basemap_var.get())
        self._map_widget.pack(fill=tk.BOTH, expand=True)

        dark = _windows_dark_mode()
        self._height_profile = HeightProfileWidget(vpaned, dark=dark,
                                                   bg="#1e1e1e" if dark else "#f0f0f0")
        vpaned.add(self._height_profile, weight=0)

        def _fix_sash():
            total = vpaned.winfo_height()
            if total > 200:
                vpaned.sashpos(0, total - 60)
            else:
                frame.after(100, _fix_sash)

        frame.after(150, _fix_sash)

        return frame, self._map_widget

    def _build_geomarks_panel(self, parent_pane):
        frame = ttk.Frame(parent_pane, padding=(4, 4, 0, 0))
        parent_pane.add(frame, weight=1)

        # header row: title + counts
        header = ttk.Frame(frame)
        header.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))

        ttk.Label(
            header,
            text="Геометки",
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        self._geomarks_count_label = ttk.Label(header, text="", font=("Segoe UI", 9))
        self._geomarks_count_label.pack(side=tk.LEFT, padx=(6, 0))

        # ── filter row 1: from average height ────────────────────────────────
        self._height_filter_var = tk.BooleanVar(value=False)
        self._height_pct_var = tk.StringVar(value="10")

        f1 = ttk.Frame(frame)
        f1.pack(side=tk.TOP, fill=tk.X, pady=(0, 1))
        ttk.Checkbutton(
            f1, text="Фильтровать от средней высоты",
            variable=self._height_filter_var,
            command=self._on_height_filter_changed,
        ).pack(side=tk.LEFT)
        ttk.Entry(f1, textvariable=self._height_pct_var, width=4).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(f1, text="% от ср. высоты").pack(side=tk.LEFT)

        self._height_pct_var.trace_add("write", lambda *_: self._on_height_filter_changed())

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X, pady=3)

        # ── filter row 2: duplicates ──────────────────────────────────────────
        self._filter_duplicates_var = tk.BooleanVar(value=False)

        f2 = ttk.Frame(frame)
        f2.pack(side=tk.TOP, fill=tk.X, pady=(0, 1))
        ttk.Checkbutton(
            f2, text="Фильтровать дубли",
            variable=self._filter_duplicates_var,
            command=self._on_height_filter_changed,
        ).pack(side=tk.LEFT)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X, pady=3)

        # ── filter row 3: height range ────────────────────────────────────────
        self._filter_h_range_var = tk.BooleanVar(value=False)
        self._filter_h_min_var = tk.StringVar(value="")
        self._filter_h_max_var = tk.StringVar(value="")

        f3 = ttk.Frame(frame)
        f3.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))
        ttk.Checkbutton(
            f3, text="Фильтровать по высоте",
            variable=self._filter_h_range_var,
            command=self._on_height_filter_changed,
        ).pack(side=tk.LEFT)
        ttk.Label(f3, text="от").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Entry(f3, textvariable=self._filter_h_min_var, width=6).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(f3, text="до").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Entry(f3, textvariable=self._filter_h_max_var, width=6).pack(side=tk.LEFT)
        ttk.Label(f3, text="м").pack(side=tk.LEFT, padx=(2, 0))

        self._filter_h_min_var.trace_add("write", lambda *_: self._on_height_filter_changed())
        self._filter_h_max_var.trace_add("write", lambda *_: self._on_height_filter_changed())

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X, pady=3)

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
        tree.tag_configure("DUPLICATE", background="#3a2500", foreground="#ffaa33")
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
        self._msginfo(
            "Подготовка к анализу",
            "Для анализа необходимы два файла в одной папке:\n\n"
            "  • Файл данных приёмника:  имя_файла.cnb\n"
            "  • Файл наблюдений RINEX:  имя_файла.cnb.obs\n"
            "                        или  имя_файла.cnb.obs.gz\n\n"
            "Файл .obs создаётся утилитой конвертации производителя\n"
            "(CnbConverter / NovAtel Convert) и должен лежать\n"
            "рядом с .cnb файлом.\n\n"
            "Обработка большого файла может занять несколько минут."
        )
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
            self._msgwarn(
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
        self._msgerror("Ошибка анализа", f"{exc}\n\n{error_text}")

    def _on_analysis_done(self, result):
        self.result = result
        self.status_var.set("Анализ завершён")
        _play_done()

        self._fill_geomarks(result)
        self._fill_overview(result)
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

        sep_right = self._fit_separator(self.tab_overview_right, "-")

        left_lines = [
            ("quality", "Итоговая оценка    : ", mission["final_score"], "final_score"),
            ("quality", "Качество геометок  :", mission["photo_quality"], "photo_quality"),
            ("quality", "Качество GNSS      : ", mission["gnss_quality"], "gnss_quality"),
            f"Доля хор. геометок : {mission['good_percent']:.1f}%",
            "",
            f"Время начала (UTC) : {start}",
            f"Время окончания    : {end}",
            f"Длительность полёта: {mission['flight_duration_min']:.1f} мин",
            f"Интервал записи    : {time_result['median_interval']:.3f} сек ({time_result['nominal_rate_hz']:.1f} Гц)",
            f"Количество геометок: {mission['photo_count']}  (отфильтровано: {len(self._filtered_ids_cache)})",
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
                excluded_ids=self._excluded_ids,
            )
            if self._height_profile:
                self._height_profile.set_data(traj["points"], photo_points)

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
            self._map_widget.update_filter(excluded_ids=self._excluded_ids)

    def _on_height_filter_changed(self):
        if self.result:
            self._fill_geomarks(self.result)
            self._rewrite_csv(self.result)

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

        if heights and self._height_filter_var and self._height_filter_var.get():
            avg_h = sum(heights) / len(heights)
            threshold = avg_h * pct
        else:
            avg_h = None
            threshold = None

        from collections import Counter
        coord_counts = Counter(
            (r.get("lat"), r.get("lon")) for r in report
            if r.get("lat") is not None and r.get("lon") is not None
        )
        duplicate_coords = {c for c, n in coord_counts.items() if n > 1}

        filter_dups = bool(self._filter_duplicates_var and self._filter_duplicates_var.get())
        seen_coords = set()

        filter_range = bool(self._filter_h_range_var and self._filter_h_range_var.get())
        try:
            h_min = float(self._filter_h_min_var.get()) if self._filter_h_min_var and self._filter_h_min_var.get().strip() else None
        except ValueError:
            h_min = None
        try:
            h_max = float(self._filter_h_max_var.get()) if self._filter_h_max_var and self._filter_h_max_var.get().strip() else None
        except ValueError:
            h_max = None

        total = len(report)
        filtered_count = 0
        excluded_count = 0
        duplicate_count = 0
        range_filtered_count = 0
        filtered_ids = set()

        for r in report:
            lat = f"{r['lat']:.7f}" if r.get("lat") is not None else "—"
            lon = f"{r['lon']:.7f}" if r.get("lon") is not None else "—"
            height = f"{r['height']:.1f}" if r.get("height") is not None else "—"
            time_str = r["time"].strftime("%H:%M:%S.%f")[:-3] if hasattr(r["time"], "strftime") else str(r["time"])
            quality = r["quality"]
            photo_id = r["photo_id"]

            manually_excluded = photo_id in self._excluded_ids
            height_filtered = (
                avg_h is not None
                and r.get("height") is not None
                and abs(r["height"] - avg_h) > threshold
            )
            coord = (r.get("lat"), r.get("lon"))
            is_duplicate = coord in duplicate_coords
            dup_filtered = filter_dups and is_duplicate and coord in seen_coords
            if is_duplicate:
                seen_coords.add(coord)

            h_val = r.get("height")
            range_filtered = (
                filter_range and h_val is not None
                and ((h_min is not None and h_val < h_min) or (h_max is not None and h_val > h_max))
            )

            if manually_excluded:
                excluded_count += 1
                indicator = "⬛"
                tags = ("EXCLUDED",)
            elif height_filtered:
                filtered_count += 1
                filtered_ids.add(photo_id)
                indicator = "🔴"
                tags = ("FILTERED",)
            elif dup_filtered:
                duplicate_count += 1
                filtered_ids.add(photo_id)
                indicator = "🟠"
                tags = ("FILTERED",)
            elif range_filtered:
                range_filtered_count += 1
                filtered_ids.add(photo_id)
                indicator = "🔵"
                tags = ("FILTERED",)
            elif is_duplicate and not filter_dups:
                indicator = "🟠"
                tags = ("DUPLICATE",)
            else:
                indicator = ""
                tags = (quality,)

            iid = tree.insert("", tk.END, values=(
                indicator, photo_id, time_str, lat, lon, height, r["satellites"], quality
            ), tags=tags)
            self._geomarks_iid_map[photo_id] = iid

        if self._geomarks_count_label:
            total_filtered = filtered_count + duplicate_count + range_filtered_count + excluded_count
            kept = total - total_filtered
            parts = [f"всего: {total}", f"ок: {kept}"]
            if duplicate_count:
                parts.append(f"дубли: {duplicate_count}")
            if filtered_count:
                parts.append(f"ср.высота: {filtered_count}")
            if range_filtered_count:
                parts.append(f"диапазон: {range_filtered_count}")
            if excluded_count:
                parts.append(f"исключено: {excluded_count}")
            self._geomarks_count_label.configure(text="(" + ",  ".join(parts) + ")")

        self._filtered_ids_cache = filtered_ids

        if self._map_widget:
            self._map_widget.update_filter(
                excluded_ids=self._excluded_ids,
                filtered_ids=filtered_ids,
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
        # small delay: if mouse went to map, _on_map_hover will cancel the clear
        self._tree_leave_job = self.root.after(80, self._do_tree_leave)

    def _do_tree_leave(self):
        self._set_tree_hover(None)
        if self._map_widget:
            self._map_widget.highlight_point(None)

    def _on_map_hover(self, photo_id):
        # cancel pending tree-leave clear
        job = getattr(self, "_tree_leave_job", None)
        if job:
            self.root.after_cancel(job)
            self._tree_leave_job = None
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

        lines = [
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
            ("quality", "Качество геометок  :", mission["photo_quality"], "photo_quality"),
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

        self._filter_height_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            filter_frame,
            text="Применить фильтрацию геометок",
            variable=self._filter_height_var,
            command=lambda: self._rewrite_csv(result),
        ).pack(side=tk.LEFT)

        tooltip_text = (
            "При включении в CSV-файл попадают только те геометки,\n"
            "которые прошли все активные фильтры в таблице:\n"
            "  • Фильтр от средней высоты\n"
            "  • Фильтр дублей\n"
            "  • Фильтр по диапазону высот\n\n"
            "Исключённые вручную метки убираются всегда."
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

    def _rewrite_csv(self, result):
        import csv as _csv
        report = result["photo_report"]
        csv_path = result["files"]["csv"]

        apply_filters = bool(self._filter_height_var and self._filter_height_var.get())

        rows = []
        for r in report:
            pid = r["photo_id"]
            if pid in self._excluded_ids:
                continue
            if apply_filters and pid in self._filtered_ids_cache:
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
            self._msgerror("Ошибка", f"Папка не найдена:\n{path}")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            self._msgerror("Ошибка", f"Не удалось открыть папку:\n{exc}")

    def _view_file(self, path):
        if not os.path.exists(path):
            self._msgerror("Ошибка", f"Файл не найден:\n{path}")
            return

        if path.lower().endswith(".pdf"):
            try:
                os.startfile(path)
            except OSError as exc:
                self._msgerror("Ошибка", f"Не удалось открыть PDF:\n{exc}")
            return

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as exc:
            self._msgerror("Ошибка", f"Не удалось прочитать файл:\n{exc}")
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


class MultitrackWindow:

    COLORS = [
        "#00c8ff", "#ff6b35", "#7fff00", "#ff44cc",
        "#ffee00", "#ff9900", "#00ff9f", "#ff4466",
        "#aa88ff", "#44ffdd",
    ]
    SINGLE_COLOR = "#00c8ff"

    def __init__(self, parent, app):
        self.app = app
        self._tracks_data = []   # [{label, color, points}]
        self.win = tk.Toplevel(parent)
        self.win.title("Мультитрек")
        self.win.geometry("1400x900")
        self._track_count = 0
        self._pending_loads = 0
        self._last_dir = None
        self._single_color_var = tk.BooleanVar(value=False)
        self._hide_stats_var = tk.BooleanVar(value=False)
        self._hull_visible_var = tk.BooleanVar(value=True)
        self._build()
        self._apply_theme()
        self.win.after(100, self._apply_titlebar_theme)

    def _build(self):
        # ── top bar ──────────────────────────────────────────────────────
        top = ttk.Frame(self.win, padding=(8, 6))
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(top, text="Добавить файлы", command=self._add_files).pack(side=tk.LEFT)
        ttk.Button(top, text="Очистить", command=self._clear).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(top, text="  Подложка:").pack(side=tk.LEFT)
        self._basemap_var = tk.StringVar(value=DEFAULT_BASEMAP)
        cb = ttk.Combobox(
            top, textvariable=self._basemap_var,
            values=BASEMAP_KEYS, state="readonly", width=22
        )
        cb.pack(side=tk.LEFT, padx=(4, 0))
        cb.bind("<<ComboboxSelected>>", lambda _e: self._map.set_basemap(self._basemap_var.get()))

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(16, 0), pady=2)

        ttk.Checkbutton(
            top, text="В одном цвете",
            variable=self._single_color_var,
            command=self._on_color_mode_changed
        ).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=2)

        ttk.Checkbutton(
            top, text="Скрыть статистику",
            variable=self._hide_stats_var,
            command=self._on_stats_toggle
        ).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=2)

        ttk.Checkbutton(
            top, text="Площадь",
            variable=self._hull_visible_var,
            command=self._on_hull_toggle
        ).pack(side=tk.LEFT, padx=(10, 0))

        area_help = (
            "Площадь съёмки\n"
            "\n"
            "Вокруг линии каждого трека строится буфер (полоса)\n"
            "фиксированной ширины, повторяющий форму маршрута.\n"
            "Соседние проходы сетки сливаются в единый контур.\n"
            "Площадь — суммарная площадь этих полос по всем трекам\n"
            "(перекрытия учитываются один раз).\n"
            "\n"
            "Ширина полосы подбирается автоматически от размера\n"
            "трека (2% диагонали, в пределах 30–150 м)."
        )
        self.app._make_help_icon(top, area_help).pack(side=tk.LEFT, padx=(4, 0))

        # ── map ───────────────────────────────────────────────────────────
        self._map = MapWidget(self.win, basemap=self._basemap_var.get())
        self._map.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 0))

        # ── bottom bar ────────────────────────────────────────────────────
        bottom = ttk.Frame(self.win, padding=(8, 4))
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(bottom, text="Экспортировать KML",
                   command=self._export_kml).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Экспортировать изображение",
                   command=self._export_image).pack(side=tk.LEFT, padx=(8, 0))

        self._status_var = tk.StringVar(value="Добавьте CNB файлы")
        ttk.Label(self.win, textvariable=self._status_var,
                  relief=tk.SUNKEN, anchor=tk.W, padding=4).pack(side=tk.BOTTOM, fill=tk.X)

    def _apply_theme(self):
        theme = DARK_THEME if self.app.dark_mode.get() else LIGHT_THEME
        self.win.configure(bg=theme["bg"])

    def _apply_titlebar_theme(self):
        self.app._apply_titlebar_theme_to(self.win)
        if os.path.exists(ICON_PATH):
            try:
                self.win.iconbitmap(ICON_PATH)
            except Exception:
                pass

    def _on_color_mode_changed(self):
        if self._single_color_var.get():
            self._map.set_single_color(self.SINGLE_COLOR)
            self._map.set_legend_visible(False)
        else:
            self._map.set_single_color(None)
            self._map.set_legend_visible(True)

    def _on_stats_toggle(self):
        self._map.set_stats_visible(not self._hide_stats_var.get())

    def _on_hull_toggle(self):
        self._map.set_hull_visible(self._hull_visible_var.get())

    def _export_image(self):
        from PIL import ImageGrab
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Сохранить изображение",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")],
        )
        if not path:
            return
        self.win.update_idletasks()
        x = self._map.winfo_rootx()
        y = self._map.winfo_rooty()
        w = self._map.winfo_width()
        h = self._map.winfo_height()
        try:
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img.save(path)
            self._status_var.set(f"Изображение сохранено: {os.path.basename(path)}")
        except Exception as e:
            self.app._msgerror("Ошибка экспорта", str(e), parent=self.win)

    def _add_files(self):
        self.app._msginfo(
            "Загрузка файлов",
            "При загрузке больших CNB-файлов обработка может занять некоторое время.\n\n"
            "Программа не зависнет — дождитесь появления треков на карте.",
            parent=self.win
        )
        paths = filedialog.askopenfilenames(
            parent=self.win,
            title="Выберите CNB файлы",
            initialdir=self._last_dir,
            filetypes=[("CNB файлы", "*.cnb"), ("Все файлы", "*.*")]
        )
        if not paths:
            return
        self._last_dir = os.path.dirname(paths[0])
        for path in paths:
            self._load_file(path)

    def _load_file(self, path):
        color = self.COLORS[self._track_count % len(self.COLORS)]
        self._track_count += 1
        self._pending_loads += 1
        label = os.path.splitext(os.path.basename(path))[0]
        self._status_var.set(f"Загрузка {label}…")
        threading.Thread(
            target=self._extract_and_draw,
            args=(path, color, label),
            daemon=True
        ).start()

    def _extract_and_draw(self, path, color, label):
        from core.novatel.reader import iter_messages
        from core.novatel.bestpos import decode_bestposb
        from core.novatel.gps_ephemeris import gps_time_to_datetime
        MSG_ID_BESTPOS = 42
        points = []
        try:
            for msg in iter_messages(path):
                if msg.msg_id != MSG_ID_BESTPOS:
                    continue
                fix = decode_bestposb(msg.body)
                if fix is not None:
                    fix["time"] = gps_time_to_datetime(msg.week, msg.tow_sec)
                    points.append(fix)
        except Exception as e:
            self.win.after(0, lambda: self._on_track_failed(label, e))
            return
        if points:
            self.win.after(0, lambda: self._on_track_loaded(points, color, label))
        else:
            self.win.after(0, lambda: self._on_track_failed(label, "нет данных"))

    def _on_track_failed(self, label, err):
        self._status_var.set(f"Ошибка {label}: {err}")
        self._pending_loads -= 1
        if self._pending_loads == 0:
            _play_done()

    def _on_track_loaded(self, points, color, label):
        self._tracks_data.append({"label": label, "color": color, "points": points})
        self._map.add_track(points, color, label)
        self._status_var.set(f"Загружено: {label}  ({len(points)} точек)")
        self._pending_loads -= 1
        if self._pending_loads == 0:
            _play_done()

    @staticmethod
    def _hex_to_kml_color(hex_color):
        h = hex_color.lstrip("#")
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"ff{b}{g}{r}"

    def _export_kml(self):
        if not self._tracks_data:
            self.app._msginfo("Экспорт KML", "Нет загруженных треков.", parent=self.win)
            return
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Сохранить KML",
            defaultextension=".kml",
            filetypes=[("KML файлы", "*.kml"), ("Все файлы", "*.*")],
            initialfile="multitrack.kml",
            initialdir=self._last_dir,
        )
        if not path:
            return

        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<kml xmlns="http://www.opengis.net/kml/2.2">',
                 '  <Document>',
                 '    <name>Мультитрек</name>']

        for i, track in enumerate(self._tracks_data):
            kml_color = self._hex_to_kml_color(track["color"])
            lines.append(f'    <Style id="s{i}"><LineStyle>'
                         f'<color>{kml_color}</color><width>3</width>'
                         f'</LineStyle></Style>')

        for i, track in enumerate(self._tracks_data):
            coords = " ".join(
                f"{p['lon']},{p['lat']},{p.get('height', 0):.1f}"
                for p in track["points"]
            )
            lines += [
                f'    <Placemark>',
                f'      <name>{track["label"]}</name>',
                f'      <styleUrl>#s{i}</styleUrl>',
                f'      <LineString><tessellate>1</tessellate>',
                f'        <coordinates>{coords}</coordinates>',
                f'      </LineString>',
                f'    </Placemark>',
            ]

        lines += ['  </Document>', '</kml>']

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._status_var.set(f"KML сохранён: {os.path.basename(path)}")

    def _clear(self):
        self._map.clear_tracks()
        self._track_count = 0
        self._tracks_data = []
        self._status_var.set("Добавьте CNB файлы")


def main():
    root = tk.Tk()
    GnssAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
