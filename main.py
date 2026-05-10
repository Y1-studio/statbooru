import sys
import re
import os
import time
import glob
import gc
import importlib.util
import requests
import multiprocessing as mp
import tempfile
import queue as queue_module
import traceback

# RAM saver: Polars uses worker threads; fewer threads usually means lower peak native RAM.
# Raise this if you prefer speed over memory, e.g. "4" or "8".
os.environ.setdefault("POLARS_MAX_THREADS", "8")

import polars as pl
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QTextEdit, QPushButton,
    QComboBox, QCheckBox, QDateEdit, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QGroupBox,
    QListWidget, QListWidgetItem, QRadioButton, QSpinBox,
    QDialog, QHeaderView, QMenu, QTextBrowser
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal, QUrl, QRunnable, QThreadPool, pyqtSlot, QObject
from PyQt6.QtGui import QColor, QDesktopServices, QPixmap


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- SETTINGS ---
DB_PATH = os.path.join(BASE_DIR, "data", "danbooru2026_clean.parquet")
API_DB_PATH = os.path.join(BASE_DIR, "data", "danbooru_api_clean.parquet")
DICT_PATH = os.path.join(BASE_DIR, "data", "tags_dictionary.parquet")
API_DICT_PATH = os.path.join(BASE_DIR, "data", "tags_dictionary_API.parquet")
EXT_DIR = os.path.join(BASE_DIR, "extensions")

os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(EXT_DIR, exist_ok=True)

# ==========================================
# PROCESS MEMORY HELPERS (WINDOWS-SAFE)
# ==========================================
def _bytes_to_mb(value):
    try:
        return float(value) / (1024 * 1024)
    except Exception:
        return 0.0


def get_process_memory_mb():
    """Return process working-set/private/pagefile MB when Windows APIs are available."""
    info = {"rss_mb": None, "private_mb": None, "pagefile_mb": None}
    if os.name != "nt":
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            info["rss_mb"] = rss / 1024
        except Exception:
            pass
        return info

    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if ok:
            info["rss_mb"] = _bytes_to_mb(counters.WorkingSetSize)
            info["private_mb"] = _bytes_to_mb(counters.PrivateUsage)
            info["pagefile_mb"] = _bytes_to_mb(counters.PagefileUsage)
    except Exception:
        pass
    return info


def format_memory_suffix():
    m = get_process_memory_mb()
    parts = []
    if m.get("rss_mb") is not None:
        parts.append(f"RSS {m['rss_mb']:.0f} MB")
    if m.get("private_mb") is not None:
        parts.append(f"Private {m['private_mb']:.0f} MB")
    return " | " + ", ".join(parts) if parts else ""


def trim_process_working_set():
    """Ask Windows to trim the process working set. This can lower Task Manager RSS."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        return bool(ctypes.windll.psapi.EmptyWorkingSet(handle))
    except Exception:
        return False

# Limit thumbnail thread pool to avoid spamming the CDN and getting rate limited
QThreadPool.globalInstance().setMaxThreadCount(8)

# --- DARK THEME STYLESHEET ---
DARK_THEME = """
QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }
QTextEdit, QComboBox, QDateEdit, QSpinBox, QTabWidget::pane { background-color: #313244; border: 1px solid #45475a; border-radius: 6px; padding: 6px; color: #cdd6f4; }
QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus { border: 1px solid #89b4fa; }
QPushButton { background-color: #89b4fa; color: #11111b; border: none; border-radius: 6px; padding: 10px; font-weight: bold; }
QPushButton:hover { background-color: #b4befe; }
QPushButton:disabled { background-color: #45475a; color: #a6adc8; }
QGroupBox { border: 1px solid #45475a; border-radius: 8px; margin-top: 14px; padding-top: 14px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; color: #89b4fa; }
QTableWidget { background-color: #1e1e2e; alternate-background-color: #2a2b3d; gridline-color: #45475a; border: 1px solid #45475a; border-radius: 6px; }
QTableWidget::item:selected { background-color: #45475a; }
QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 6px; border: 1px solid #45475a; font-weight: bold; }
QTabBar::tab { background: #313244; color: #cdd6f4; padding: 8px 16px; border: 1px solid #45475a; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
QTabBar::tab:selected { background: #89b4fa; color: #11111b; font-weight: bold; }
QProgressBar { border: 1px solid #45475a; border-radius: 4px; text-align: center; background-color: #313244; color: #cdd6f4; }
QProgressBar::chunk { background-color: #a6e3a1; border-radius: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #1e1e2e; border-radius: 5px; }
QScrollBar::handle { background: #45475a; border-radius: 5px; }
QScrollBar::handle:hover { background: #585b70; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; border: 1px solid #45475a; background: #313244; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: #89b4fa; border: 1px solid #89b4fa; }
QMenu { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; }
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background-color: #89b4fa; color: #11111b; }
"""

# ==========================================
# PARQUET / CACHE HELPERS
# ==========================================
EXPECTED_COLUMNS = ["id", "rating", "score", "fav_count", "file_url", "tag_string_artist", "tag_string_copyright", "tag_string_character", "tag_string_general", "tag_string_meta", "file_size", "image_width", "image_height", "created_at", "md5", "tag_string"]
EXPECTED_DTYPES = {"id": pl.Int64, "rating": pl.Utf8, "score": pl.Int64, "fav_count": pl.Int64, "file_url": pl.Utf8, "tag_string_artist": pl.Utf8, "tag_string_copyright": pl.Utf8, "tag_string_character": pl.Utf8, "tag_string_general": pl.Utf8, "tag_string_meta": pl.Utf8, "file_size": pl.Int64, "image_width": pl.Int64, "image_height": pl.Int64, "created_at": pl.Utf8, "md5": pl.Utf8, "tag_string": pl.Utf8}

def ensure_expected_schema(df: pl.DataFrame) -> pl.DataFrame:
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=EXPECTED_DTYPES[col]).alias(col))
    for col in EXPECTED_COLUMNS:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(EXPECTED_DTYPES[col], strict=False))
    return df.select(EXPECTED_COLUMNS)

def load_combined_lazyframe():
    paths = []
    if os.path.exists(DB_PATH): paths.append(DB_PATH)
    if os.path.exists(API_DB_PATH): paths.append(API_DB_PATH)

    if not paths:
        raise FileNotFoundError("No parquet database files were found.")

    lazy_frames = []
    for path in paths:
        lf = pl.scan_parquet(path)
        existing_cols = lf.collect_schema().names()
        exprs = []
        for c in EXPECTED_COLUMNS:
            if c in existing_cols:
                exprs.append(pl.col(c).cast(EXPECTED_DTYPES[c], strict=False).alias(c))
            else:
                exprs.append(pl.lit(None, dtype=EXPECTED_DTYPES[c]).alias(c))
        lazy_frames.append(lf.select(exprs))

    return pl.concat(lazy_frames, how="vertical")

def get_latest_stored_date():
    latest_dates = []
    for path in [DB_PATH, API_DB_PATH]:
        if os.path.exists(path):
            try:
                value = pl.scan_parquet(path).select(pl.max("created_at")).collect().item()
                if value:
                    latest_dates.append(str(value)[:10])
            except Exception:
                pass
    return max(latest_dates) if latest_dates else "2000-01-01"


# ==========================================
# EXTENSIONS API: QUERY PARSER & FILTERS
# ==========================================
def wildcard_to_regex(pattern: str) -> str:
    escaped_pattern = re.escape(pattern).replace(r'\*', r'.*')
    return escaped_pattern


class QueryParser:
    """Parses Danbooru Syntax strings into Polars expressions for the local database."""
    @staticmethod
    def parse_token(tok: str) -> pl.Expr:
        is_neg = tok.startswith('-')
        if is_neg:
            tok = tok[1:]

        # Handle Metadata modifiers
        if ":" in tok:
            prefix, val = tok.split(":", 1)
            col_map = {
                "score": "score", "favcount": "fav_count",
                "width": "image_width", "height": "image_height", "id": "id"
            }
            if prefix in col_map:
                col = col_map[prefix]
                if val.startswith(">="): e = pl.col(col) >= int(val[2:])
                elif val.startswith("<="): e = pl.col(col) <= int(val[2:])
                elif val.startswith(">"): e = pl.col(col) > int(val[1:])
                elif val.startswith("<"): e = pl.col(col) < int(val[1:])
                elif ".." in val:
                    parts = val.split("..")
                    e = pl.lit(True)
                    if parts[0]: e &= pl.col(col) >= int(parts[0])
                    if len(parts) > 1 and parts[1]: e &= pl.col(col) <= int(parts[1])
                else:
                    e = pl.col(col) == int(val)
                return ~e if is_neg else e

            if prefix == "rating":
                r_map = {"explicit": "e", "e": "e", "questionable": "q", "q": "q", "sensitive": "s", "s": "s", "general": "g", "g": "g"}
                vals = [r_map.get(v, v) for v in val.split(",")]
                e = pl.col("rating").is_in(vals)
                return ~e if is_neg else e

            # --- SOURCE metatag ---
            if prefix == "source":
                if val == "none":
                    e = pl.col("file_url").is_null()
                elif val == "http":
                    e = pl.col("file_url").str.starts_with("http")
                elif (val.startswith('"') and val.endswith('"')) or "*" in val:
                    if val.startswith('"') and val.endswith('"'):
                        val = val[1:-1]
                    regex_pattern = wildcard_to_regex(val)
                    e = pl.col("file_url").str.contains(regex_pattern)
                else:
                    e = pl.col("file_url").str.starts_with(val)

                return ~e.fill_null(True) if is_neg else e.fill_null(False)

            # --- PIXIV metatag ---
            if prefix == "pixiv":
                if val == "any":
                    e = pl.col("file_url").str.contains(r"pixiv\.net\/artworks\/\d+")
                else:
                    pixiv_id_col = pl.col("file_url").str.extract(r"pixiv\.net\/artworks\/(\d+)", 1).cast(pl.Int64, strict=False)

                    if val.isdigit():
                        e = pixiv_id_col == int(val)
                    elif ".." in val:
                        parts = val.split("..")
                        e = pl.lit(True)
                        if parts[0]: e &= pixiv_id_col >= int(parts[0])
                        if len(parts) > 1 and parts[1]: e &= pixiv_id_col <= int(parts[1])
                    else:
                        e = pl.col("file_url").str.contains(f"pixiv.net/artworks/{val}")

                return ~e.fill_null(True) if is_neg else e.fill_null(False)

        # Handle Tags and Wildcards
        padded = pl.concat_str([pl.lit(" "), pl.col("tag_string").fill_null(""), pl.lit(" ")])
        if "*" in tok:
            regex_pattern = r"(^|\s)" + re.escape(tok).replace("\\*", r"\S*") + r"($|\s)"
            e = padded.str.contains(regex_pattern)
        else:
            e = padded.str.contains(f" {tok} ", literal=True)

        return ~e if is_neg else e

    @staticmethod
    def build_polars_expr(query_str: str) -> list[pl.Expr]:
        tokens = query_str.replace("\n", " ").split()
        exprs = []
        i = 0
        while i < len(tokens):
            if i + 2 < len(tokens) and tokens[i+1].lower() == "or":
                exprs.append(QueryParser.parse_token(tokens[i]) | QueryParser.parse_token(tokens[i+2]))
                i += 3
                continue
            if tokens[i].lower() == "or":
                i += 1
                continue
            exprs.append(QueryParser.parse_token(tokens[i]))
            i += 1
        return exprs

def apply_basic_filters(df_or_lf, filters: dict):
    """Apply non-sorting filters to either a Polars DataFrame or LazyFrame.

    Keeping these filters lazy before collect prevents the app from loading
    the whole parquet result into RAM before date/rating/orientation/score
    filters are applied.
    """
    if df_or_lf is None:
        return df_or_lf

    if filters["ratings"]:
        df_or_lf = df_or_lf.filter(pl.col("rating").is_in(filters["ratings"]))

    df_or_lf = df_or_lf.filter((pl.col("created_at") >= filters["date_from"]) & (pl.col("created_at") <= filters["date_to"]))

    ori = filters["orientation"]
    if ori == "Landscape":
        df_or_lf = df_or_lf.filter(pl.col("image_width") > pl.col("image_height"))
    elif ori == "Portrait":
        df_or_lf = df_or_lf.filter(pl.col("image_width") < pl.col("image_height"))
    elif ori == "Square":
        df_or_lf = df_or_lf.filter(pl.col("image_width") == pl.col("image_height"))

    if filters["min_score"] is not None:
        df_or_lf = df_or_lf.filter(pl.col("score") >= filters["min_score"])
    if filters["min_favs"] is not None:
        df_or_lf = df_or_lf.filter(pl.col("fav_count") >= filters["min_favs"])

    return df_or_lf


def apply_all_filters_and_sort(df: pl.DataFrame, filters: dict) -> pl.DataFrame:
    if df is None or len(df) == 0:
        return df

    if filters['ratings']:
        df = df.filter(pl.col("rating").is_in(filters['ratings']))

    df = df.filter((pl.col("created_at") >= filters['date_from']) & (pl.col("created_at") <= filters['date_to']))

    ori = filters['orientation']
    if ori == "Landscape":
        df = df.filter(pl.col("image_width") > pl.col("image_height"))
    elif ori == "Portrait":
        df = df.filter(pl.col("image_width") < pl.col("image_height"))
    elif ori == "Square":
        df = df.filter(pl.col("image_width") == pl.col("image_height"))

    if filters['min_score'] is not None:
        df = df.filter(pl.col("score") >= filters['min_score'])
    if filters['min_favs'] is not None:
        df = df.filter(pl.col("fav_count") >= filters['min_favs'])

    if filters['dedup']:
        dedup_col = "md5" if "md5" in df.columns else "id"
        df = df.unique(subset=[dedup_col])

    if filters['sort_col'] == "random":
        df = df.sample(fraction=1.0, shuffle=True, seed=int(time.time()))
    else:
        df = df.sort(filters['sort_col'], descending=filters['sort_desc'])

    return df

# ==========================================
# UI CLASSES & EXTENSIONS LOADER
# ==========================================

class ExtensionManager:
    @staticmethod
    def load_extensions(app):
        """Load every Python extension from EXT_DIR.

        Supported extension entrypoints:
          - setup(app)      # original API
          - register(app)   # compatibility alias used by some plugins

        Failures are stored on app.extension_errors so one bad extension does not
        prevent the rest of the app or other extensions from loading.
        """
        if not hasattr(app, "loaded_extensions"):
            app.loaded_extensions = []
        if not hasattr(app, "extension_errors"):
            app.extension_errors = []

        for file in glob.glob(os.path.join(EXT_DIR, "*.py")):
            if os.path.basename(file) == "__init__.py":
                continue
            name = os.path.basename(file)[:-3]
            try:
                spec = importlib.util.spec_from_file_location(name, file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                if hasattr(mod, "setup"):
                    mod.setup(app)
                elif hasattr(mod, "register"):
                    mod.register(app)
                else:
                    print(f"Skipped extension {name}: no setup(app) or register(app) entrypoint")
                    continue

                app.loaded_extensions.append((name, mod))
                print(f"Loaded extension: {name}")
            except Exception as e:
                app.extension_errors.append((name, str(e)))
                print(f"Failed to load extension {name}: {e}")

class ImageDownloadWorker(QThread):
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            resp = requests.get(self.url, headers={"User-Agent": "DanbooruDatasetFinder/2.0"}, timeout=15)
            resp.raise_for_status()
            self.finished.emit(resp.content)
        except Exception as e:
            self.error.emit(str(e))

class ThumbWorkerSignals(QObject):
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)

class ThumbWorker(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = ThumbWorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            resp = requests.get(self.url, headers={"User-Agent": "DanbooruDatasetFinder/2.0"}, timeout=10)
            if resp.status_code == 200:
                self.signals.finished.emit(resp.content)
            else:
                self.signals.error.emit(str(resp.status_code))
        except Exception as e:
            self.signals.error.emit(str(e))

class ThumbnailWidget(QLabel):
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setFixedSize(110, 110)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("⌛")
        self.setStyleSheet("background-color: transparent;")
        # Pass clicks through to the table underneath!
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        worker = ThumbWorker(url)
        worker.signals.finished.connect(self.on_loaded)
        worker.signals.error.connect(self.on_error)
        QThreadPool.globalInstance().start(worker)

    def on_loaded(self, data):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if not pixmap.isNull():
            scaled = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(scaled)
        else:
            self.setText("❌")

    def on_error(self, err):
        self.setText("❌")

class ImageViewerDialog(QDialog):
    def __init__(self, df: pl.DataFrame, start_index: int, parent=None):
        super().__init__(parent)
        self.df = df
        self.current_index = start_index

        self.active_workers = []
        self.current_worker = None

        self.setWindowTitle("Image Viewer")
        self.resize(850, 850)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Top Controls
        ctrl_widget = QWidget()
        ctrl_widget.setStyleSheet("background-color: #313244; border-bottom: 1px solid #45475a;")
        ctrl_layout = QHBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(10, 8, 10, 8)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["720p Sample (Fast)", "180p Thumbnail (Fastest)", "Original (Slowest)"])
        self.quality_combo.setStyleSheet("background-color: #1e1e2e; padding: 4px; border: 1px solid #45475a; border-radius: 4px;")
        self.quality_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.quality_combo.currentIndexChanged.connect(self.reload_current)

        lbl = QLabel("Image Quality:")
        lbl.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(lbl)
        ctrl_layout.addWidget(self.quality_combo)

        self.lbl_counter = QLabel()
        self.lbl_counter.setStyleSheet("color: #a6adc8;")
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.lbl_counter)

        self.layout.addWidget(ctrl_widget)

        # Image Area
        self.image_label = QLabel("Downloading image...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.image_label, stretch=1)

        self.load_image(self.current_index)

    def reload_current(self):
        self.load_image(self.current_index)

    def load_image(self, index, fallback_to_original=False):
        row_data = self.df.row(index, named=True)
        raw_url = row_data.get("file_url")
        md5 = row_data.get("md5")

        self.setWindowTitle(f"Image Viewer - {index + 1} of {len(self.df)}")
        self.lbl_counter.setText(f"{index + 1} / {len(self.df)}")

        if not raw_url:
            self.image_label.setText("No Image URL available.")
            self.original_pixmap = None
            return

        url = "https:" + raw_url if raw_url.startswith("//") else raw_url

        if not md5:
            match = re.search(r'/([a-f0-9]{32})\.', raw_url)
            if match: md5 = match.group(1)

        quality = self.quality_combo.currentText()
        if not fallback_to_original and md5:
            sub1, sub2 = md5[0:2], md5[2:4]
            if "180p" in quality:
                url = f"https://cdn.donmai.us/180x180/{sub1}/{sub2}/{md5}.jpg"
            elif "720p" in quality:
                url = f"https://cdn.donmai.us/720x720/{sub1}/{sub2}/{md5}.webp"

        status_text = "Downloading Original..." if fallback_to_original else f"Downloading {quality.split(' ')[0]}..."
        self.image_label.setText(status_text)
        self.original_pixmap = None

        worker = ImageDownloadWorker(url)
        self.active_workers.append(worker)
        self.current_worker = worker

        worker.finished.connect(lambda data, w=worker, i=index, f=fallback_to_original: self._handle_finished(data, w, i, f))
        worker.error.connect(lambda err, w=worker, i=index, f=fallback_to_original: self._handle_error(err, w, i, f))
        worker.start()

    def _handle_finished(self, data, worker, index, fallback):
        if worker in self.active_workers: self.active_workers.remove(worker)
        if worker == self.current_worker:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if pixmap.isNull():
                if not fallback:
                    self.image_label.setText("Format not supported locally, falling back to Original...")
                    self.load_image(index, fallback_to_original=True)
                else:
                    self.image_label.setText("Failed to parse image data.")
            else:
                self.original_pixmap = pixmap
                self.update_image()

    def _handle_error(self, err, worker, index, fallback):
        if worker in self.active_workers: self.active_workers.remove(worker)
        if worker == self.current_worker:
            if not fallback and ("404" in err or "403" in err):
                self.image_label.setText("Sample not found, falling back to Original...")
                self.load_image(index, fallback_to_original=True)
            else:
                self.image_label.setText(f"Error loading image:\n{err}")

    def update_image(self):
        if hasattr(self, 'original_pixmap') and self.original_pixmap and not self.original_pixmap.isNull():
            scaled = self.original_pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_D):
            if self.current_index < len(self.df) - 1:
                self.current_index += 1
                self.load_image(self.current_index)
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_A):
            if self.current_index > 0:
                self.current_index -= 1
                self.load_image(self.current_index)
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()

    def closeEvent(self, event):
        self.original_pixmap = None
        self.image_label.clear()
        self.current_worker = None
        self.active_workers.clear()
        gc.collect()
        super().closeEvent(event)


def format_count(c):
    if c >= 1_000_000:
        return f"{c/1_000_000:.1f}M"
    if c >= 1_000:
        return f"{c/1_000:.1f}k"
    return str(c)

class AutocompletePopup(QListWidget):
    def __init__(self, parent):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("""
            QListWidget { border: 2px solid #89b4fa; background: #313244; border-radius: 6px; }
            QListWidget::item { padding: 2px; border-radius: 4px; }
            QListWidget::item:selected { background-color: #45475a; }
        """)

class TagAutocompleteTextEdit(QTextEdit):
    def __init__(self, tag_data):
        super().__init__()
        self.tag_data = tag_data
        self.popup = AutocompletePopup(self)
        self.popup.itemClicked.connect(self.insert_completion)
        self.textChanged.connect(self.on_text_changed)

    def keyPressEvent(self, event):
        if self.popup.isVisible():
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                current_row = self.popup.currentRow()
                if event.key() == Qt.Key.Key_Down:
                    next_row = min(current_row + 1, self.popup.count() - 1)
                else:
                    next_row = max(current_row - 1, 0)
                self.popup.setCurrentRow(next_row)
                return
            elif event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                if item := self.popup.currentItem():
                    self.insert_completion(item)
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.popup.hide()
                return
        super().keyPressEvent(event)

    def on_text_changed(self):
        cursor = self.textCursor()
        pos = cursor.position()
        text_before = self.toPlainText()[:pos]

        parts = re.split(r'\s+', text_before)
        current_word = parts[-1]

        prefix = ""
        if current_word.startswith("-") or current_word.startswith("~"):
            prefix = current_word[0]
            current_word = current_word[1:]

        if len(current_word) < 2:
            self.popup.hide()
            return

        current_word = current_word.lower()
        word_boundary_match = "_" + current_word

        matches = []
        for search_key, display_text, actual_tag, color, count in self.tag_data:
            if search_key.startswith(current_word) or word_boundary_match in search_key:
                matches.append((search_key, display_text, actual_tag, color, count))

        if not matches:
            self.popup.hide()
            return

        matches.sort(key=lambda x: -x[4])
        matches = matches[:20]

        self.popup.clear()
        for search_key, display_text, actual_tag, color, count in matches:
            item = QListWidgetItem()
            widget = QWidget()
            widget.setMinimumHeight(24)

            layout = QHBoxLayout(widget)
            layout.setContentsMargins(4, 0, 4, 0)

            highlight_color = "#89b4fa"
            formatted_tag_html = f'<span style="color: {color}; font-weight: bold; font-size: 13px;">'

            idx = display_text.find(current_word)
            if idx == -1:
                idx = display_text.find(word_boundary_match)
                if idx != -1: idx += 1

            if idx != -1:
                formatted_tag_html += display_text[:idx]
                formatted_tag_html += f'<span style="color: {highlight_color};">{display_text[idx : idx + len(current_word)]}</span>'
                formatted_tag_html += display_text[idx + len(current_word):]
            else:
                formatted_tag_html += display_text

            formatted_tag_html += '</span>'

            lbl_tag = QLabel()
            lbl_tag.setText(formatted_tag_html)

            lbl_count = QLabel(format_count(count))
            lbl_count.setStyleSheet("color: #a6adc8; font-size: 12px;")

            layout.addWidget(lbl_tag)
            layout.addStretch()
            layout.addWidget(lbl_count)

            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, prefix + actual_tag)

            self.popup.addItem(item)
            self.popup.setItemWidget(item, widget)

        self.popup.setCurrentRow(0)
        rect = self.cursorRect()

        p = self.viewport().mapToGlobal(rect.bottomLeft())
        self.popup.setGeometry(p.x(), p.y() + 8, 350, 250)
        self.popup.show()

    def insert_completion(self, item):
        if not item:
            return

        selected_tag = item.data(Qt.ItemDataRole.UserRole)
        cursor = self.textCursor()
        pos = cursor.position()
        full_text = self.toPlainText()

        text_before = full_text[:pos]
        text_after = full_text[pos:]

        parts = re.split(r'(\s+)', text_before)
        parts[-1] = selected_tag + " "
        new_text_before = "".join(parts)

        self.blockSignals(True)
        self.setPlainText(new_text_before + text_after)

        new_cursor = self.textCursor()
        new_cursor.setPosition(len(new_text_before))
        self.setTextCursor(new_cursor)

        self.blockSignals(False)
        self.popup.hide()

class TagBrowser(QTextBrowser):
    tag_single_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setStyleSheet("background-color: transparent; border: none; padding: 2px;")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tag = self.anchorAt(event.pos())
            if tag:
                self.tag_single_clicked.emit(tag)
                return
        super().mousePressEvent(event)


# ==========================================
# PROCESS-ISOLATED SEARCH HELPERS
# ==========================================
def _child_emit(q, kind, payload):
    """Small queue messages only. Never send a Polars DataFrame through this."""
    try:
        q.put((kind, payload))
    except Exception:
        pass


def _build_filtered_lazy_pipeline(filters, progress_queue=None):
    """Build the filtered/sorted local parquet LazyFrame without collecting it."""
    lf = load_combined_lazyframe()

    if progress_queue is not None:
        _child_emit(progress_queue, "progress", "Child: applying tag query lazily" + format_memory_suffix())
    for expr in QueryParser.build_polars_expr(filters['clean_query']):
        lf = lf.filter(expr)

    if progress_queue is not None:
        _child_emit(progress_queue, "progress", "Child: applying UI filters lazily" + format_memory_suffix())
    lf = apply_basic_filters(lf, filters)

    if filters["dedup"]:
        try:
            lazy_cols = lf.collect_schema().names()
        except Exception:
            lazy_cols = []
        dedup_col = "md5" if "md5" in lazy_cols else "id"
        if progress_queue is not None:
            _child_emit(progress_queue, "progress", f"Child: dedup by {dedup_col} lazily" + format_memory_suffix())
        lf = lf.unique(subset=[dedup_col], keep="first", maintain_order=False)

    if filters["sort_col"] != "random":
        if progress_queue is not None:
            _child_emit(progress_queue, "progress", f"Child: sorting by {filters['sort_col']} lazily" + format_memory_suffix())
        lf = lf.sort(filters["sort_col"], descending=filters["sort_desc"])

    return lf


def _search_to_parquet_child(filters, output_path, progress_queue):
    """
    Run the heavy Polars query in a short-lived child process.

    This fixes the Windows/Rust/Arrow allocator problem: any giant temporary
    MEM_PRIVATE heap regions created during collect/sort/dedup die with this
    child process instead of staying in the PyQt GUI process.
    """
    try:
        _child_emit(progress_queue, "progress", "Child process started for isolated search" + format_memory_suffix())
        lf = _build_filtered_lazy_pipeline(filters, progress_queue)

        _child_emit(progress_queue, "progress", "Child: collecting final filtered result" + format_memory_suffix())
        local_df = lf.collect(streaming=True)
        lf = None
        gc.collect()

        if filters["sort_col"] == "random":
            _child_emit(progress_queue, "progress", "Child: applying random order" + format_memory_suffix())
            local_df = local_df.sample(fraction=1.0, shuffle=True, seed=int(time.time()))

        _child_emit(progress_queue, "progress", f"Child: writing final result parquet ({len(local_df):,} rows)" + format_memory_suffix())
        ensure_expected_schema(local_df).write_parquet(output_path)
        rows = len(local_df)
        est = int(local_df.estimated_size()) if hasattr(local_df, "estimated_size") else 0

        local_df = None
        gc.collect()
        trim_process_working_set()
        _child_emit(progress_queue, "done", {"rows": rows, "estimated_size": est, "path": output_path})
    except Exception:
        _child_emit(progress_queue, "error", traceback.format_exc())

# ==========================================
# BACKGROUND WORKERS
# ==========================================
class TagCountUpdater(QThread):
    finished = pyqtSignal(object)

    def __init__(self, df: pl.DataFrame):
        super().__init__()
        self.df = df

    def run(self):
        try:
            counts_df = self.df.select("tag_string").drop_nulls().select(
                pl.col("tag_string").str.split(" ").explode()
            ).group_by("tag_string").count()
            self.finished.emit(counts_df)
        except Exception as e:
            print(f"Background Tag Updater Failed: {e}")


class FastSearchWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, lazy_df, filters):
        super().__init__()
        self.lazy_df = lazy_df
        self.filters = filters

    def run(self):
        local_df = None
        try:
            self.progress.emit("Fast mode: applying query/filter lazily" + format_memory_suffix())
            for expr in QueryParser.build_polars_expr(self.filters['clean_query']):
                self.lazy_df = self.lazy_df.filter(expr)
            self.lazy_df = apply_basic_filters(self.lazy_df, self.filters)
            if self.filters['dedup']:
                try:
                    lazy_cols = self.lazy_df.collect_schema().names()
                except Exception:
                    lazy_cols = []
                dedup_col = "md5" if "md5" in lazy_cols else "id"
                self.progress.emit(f"Fast mode: lazy dedup by {dedup_col}" + format_memory_suffix())
                self.lazy_df = self.lazy_df.unique(subset=[dedup_col], keep="first", maintain_order=False)
            if self.filters['sort_col'] != "random":
                self.progress.emit("Fast mode: lazy sort" + format_memory_suffix())
                self.lazy_df = self.lazy_df.sort(self.filters['sort_col'], descending=self.filters['sort_desc'])
            self.progress.emit("Fast mode: collecting final result" + format_memory_suffix())
            local_df = self.lazy_df.collect(streaming=True)
            self.lazy_df = None
            gc.collect()
            trim_process_working_set()
            self.progress.emit(f"Fast mode: collected {len(local_df):,} rows" + format_memory_suffix())
            if self.filters['sort_col'] == "random":
                self.progress.emit("Fast mode: random shuffle" + format_memory_suffix())
                local_df = local_df.sample(fraction=1.0, shuffle=True, seed=int(time.time()))

            gc.collect()
            trim_process_working_set()
            self.progress.emit("Fast mode: finished; final result kept for extensions" + format_memory_suffix())
            self.finished.emit(local_df)
            local_df = None
            gc.collect()
            trim_process_working_set()
        except Exception as e:
            import traceback as _traceback
            _traceback.print_exc()
            self.error.emit(str(e))
        finally:
            self.lazy_df = None
            self.filters = None
            gc.collect()
            trim_process_working_set()

class SearchWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, lazy_df, filters):
        super().__init__()
        self.lazy_df = lazy_df
        self.filters = filters

    def run(self):
        temp_path = None
        proc = None
        q = None
        try:
            self.progress.emit("Starting process-isolated search" + format_memory_suffix())

            fd, temp_path = tempfile.mkstemp(prefix="danbooru_search_result_", suffix=".parquet")
            os.close(fd)
            try:
                os.remove(temp_path)
            except Exception:
                pass

            ctx = mp.get_context("spawn" if os.name == "nt" else "fork")
            q = ctx.Queue()
            proc = ctx.Process(target=_search_to_parquet_child, args=(self.filters, temp_path, q), daemon=False)
            proc.start()

            done_payload = None
            while True:
                try:
                    kind, payload = q.get(timeout=0.15)
                    if kind == "progress":
                        self.progress.emit(str(payload))
                    elif kind == "done":
                        done_payload = payload
                        break
                    elif kind == "error":
                        raise RuntimeError(str(payload))
                except queue_module.Empty:
                    if proc is not None and not proc.is_alive():
                        exit_code = proc.exitcode
                        if exit_code not in (0, None):
                            raise RuntimeError(f"Search child process exited with code {exit_code}")
                        # The child may have exited just before the done message was received.
                        continue

            if proc is not None:
                proc.join(timeout=10)

            self.progress.emit("Main app: reading final result only" + format_memory_suffix())
            result_df = pl.read_parquet(temp_path)
            self.progress.emit(f"Main app: loaded final result ({len(result_df):,} rows)" + format_memory_suffix())

            try:
                os.remove(temp_path)
                temp_path = None
            except Exception:
                pass

            gc.collect()
            trim_process_working_set()
            self.finished.emit(result_df)

            # Break local references as soon as Qt has queued the signal delivery.
            result_df = None
            done_payload = None
            gc.collect()
            trim_process_working_set()
        except Exception as e:
            if proc is not None and proc.is_alive():
                try:
                    proc.terminate()
                    proc.join(timeout=5)
                except Exception:
                    pass
            import traceback as _traceback
            _traceback.print_exc()
            self.error.emit(str(e))
        finally:
            if q is not None:
                try:
                    q.close()
                    q.join_thread()
                except Exception:
                    pass
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            gc.collect()
            trim_process_working_set()


# ==========================================
# MAIN APPLICATION
# ==========================================

class DanbooruApp(QMainWindow):
    data_updated = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Danbooru Dataset Finder")
        self.resize(1350, 930)
        self.setStyleSheet(DARK_THEME)

        self.tag_data = self.load_dictionary()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- UNIFIED SEARCH BOX ---
        search_group = QGroupBox("Search Query")
        search_layout = QVBoxLayout()
        search_layout.setContentsMargins(4, 15, 4, 4)

        self.search_input = TagAutocompleteTextEdit(self.tag_data)
        self.search_input.setMinimumHeight(60)
        self.search_input.setPlaceholderText("Supports Danbooru syntax:\ntag1 OR tag2\n-tag\n*miku*\nsource:https://...\norder:score\n\nEmpty Search = Auto-update Tag counts!")

        search_layout.addWidget(self.search_input)
        search_group.setLayout(search_layout)
        left_panel.addWidget(search_group)

        # --- THRESHOLDS ---
        thresh_group = QGroupBox("Thresholds")
        thresh_layout = QVBoxLayout()

        hbox1 = QHBoxLayout()
        self.radio_score = QRadioButton("Min Score:")
        self.spin_score = QSpinBox()
        self.spin_score.setRange(-100, 1000000)
        self.spin_score.setValue(10)
        self.spin_score.setEnabled(False)
        hbox1.addWidget(self.radio_score)
        hbox1.addWidget(self.spin_score)

        hbox2 = QHBoxLayout()
        self.radio_fav = QRadioButton("Min Favorites:")
        self.spin_fav = QSpinBox()
        self.spin_fav.setRange(0, 1000000)
        self.spin_fav.setValue(10)
        self.spin_fav.setEnabled(False)
        hbox2.addWidget(self.radio_fav)
        hbox2.addWidget(self.spin_fav)

        self.radio_none = QRadioButton("No Threshold")
        self.radio_none.setChecked(True)

        self.radio_none.toggled.connect(lambda: self.spin_score.setEnabled(False))
        self.radio_none.toggled.connect(lambda: self.spin_fav.setEnabled(False))
        self.radio_score.toggled.connect(self.spin_score.setEnabled)
        self.radio_fav.toggled.connect(self.spin_fav.setEnabled)

        thresh_layout.addWidget(self.radio_none)
        thresh_layout.addLayout(hbox1)
        thresh_layout.addLayout(hbox2)
        thresh_group.setLayout(thresh_layout)
        left_panel.addWidget(thresh_group)

        # --- SORTING ---
        sort_group = QGroupBox("Sort By")
        sort_layout = QVBoxLayout()

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Score", "Favorites", "Date"])

        self.sort_order = QComboBox()
        self.sort_order.addItems(["Descending", "Ascending"])

        sort_layout.addWidget(self.sort_combo)
        sort_layout.addWidget(self.sort_order)
        sort_group.setLayout(sort_layout)
        left_panel.addWidget(sort_group)

        # --- RATINGS ---
        rating_group = QGroupBox("Rating")
        rating_layout = QHBoxLayout()

        self.cb_g = QCheckBox("General")
        self.cb_g.setChecked(True)
        self.cb_s = QCheckBox("Sensitive")
        self.cb_s.setChecked(True)
        self.cb_q = QCheckBox("Questionable")
        self.cb_e = QCheckBox("Explicit")

        rating_layout.addWidget(self.cb_g)
        rating_layout.addWidget(self.cb_s)
        rating_layout.addWidget(self.cb_q)
        rating_layout.addWidget(self.cb_e)

        rating_group.setLayout(rating_layout)
        left_panel.addWidget(rating_group)

        # --- IMAGE PROPERTIES ---
        props_group = QGroupBox("Image Properties")
        props_layout = QVBoxLayout()

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["Any Orientation", "Landscape", "Portrait", "Square"])
        props_layout.addWidget(self.orientation_combo)

        self.cb_dedup = QCheckBox("Remove duplicates (by MD5)")
        self.cb_dedup.setChecked(True)
        props_layout.addWidget(self.cb_dedup)

        self.cb_thumbs = QCheckBox("Load Thumbnails in Results (Requires Network)")
        self.cb_thumbs.setChecked(False)
        self.cb_thumbs.toggled.connect(self.update_ui) # Refresh if toggled
        props_layout.addWidget(self.cb_thumbs)

        props_group.setLayout(props_layout)
        left_panel.addWidget(props_group)

        # --- DATE RANGE ---
        date_group = QGroupBox("Upload Date")
        date_layout = QHBoxLayout()

        self.date_from = QDateEdit(QDate(2005, 5, 23))
        self.date_from.setCalendarPopup(True)

        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)

        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.date_from)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.date_to)

        date_group.setLayout(date_layout)
        left_panel.addWidget(date_group)

        # --- ADVANCED CONFIG ---
        adv_group = QGroupBox("Advanced")
        adv_layout = QVBoxLayout()

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Search mode:"))
        self.search_mode_combo = QComboBox()
        self.search_mode_combo.addItems(["Fast in-process", "Memory-safe isolated (slower)"])
        self.search_mode_combo.setCurrentIndex(0)
        self.search_mode_combo.setToolTip("Fast mode is quicker. Isolated mode is slower but releases Polars temporary native memory after huge searches.")
        mode_layout.addWidget(self.search_mode_combo)

        adv_layout.addLayout(mode_layout)
        adv_group.setLayout(adv_layout)
        left_panel.addWidget(adv_group)

        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.process_data)
        left_panel.addWidget(self.btn_search)

        # --- RIGHT PANEL ---
        right_panel = QVBoxLayout()
        stats_layout = QHBoxLayout()

        self.lbl_stats = QLabel("Found posts: 0")
        self.lbl_stats.setStyleSheet("font-size: 15px; font-weight: bold; color: #a6e3a1;")

        stats_layout.addWidget(self.lbl_stats)
        stats_layout.addStretch()
        right_panel.addLayout(stats_layout)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Thumb", "ID", "Rating", "Score", "Favs", "Tags (Preview)"])
        self.table.setColumnWidth(0, 115) # Thumb
        self.table.setColumnWidth(1, 80)  # ID
        self.table.setColumnWidth(2, 60)  # Rating
        self.table.setColumnWidth(3, 60)  # Score
        self.table.setColumnWidth(4, 60)  # Favs
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemDoubleClicked.connect(self.on_table_double_clicked)
        right_panel.addWidget(self.table)

        self.ext_button_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export Image URLs to TXT")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_links)
        self.ext_button_layout.addWidget(self.btn_export)
        right_panel.addLayout(self.ext_button_layout)

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 8)
        self.current_df = None
        self.unlimited_lazy_df = None
        self.last_filters = None
        self.last_query = ""
        self.extension_errors = []
        self.loaded_extensions = []

        ExtensionManager.load_extensions(self)

    def add_extension_button(self, button: QPushButton):
        self.ext_button_layout.addWidget(button)

    def get_current_df(self):
        """Return the full filtered result currently held in RAM.

        This is intentionally NOT just the visible table preview. Extensions can
        use this directly when they need a Polars DataFrame without forcing a
        second parquet/API query.
        """
        return self.current_df

    def get_results_df(self):
        """Compatibility alias for extensions that call get_results_df()."""
        return self.get_current_df()

    def get_current_lazy_df(self):
        """Return the full in-RAM result as a LazyFrame for extension code."""
        if self.current_df is not None:
            return self.current_df.lazy()
        return None

    def get_unlimited_lazy_df(self):
        """Compatibility hook used by analytics/extensions.

        Older extension builds expected this method so they could bypass the UI
        Max Results / 500-row preview path. In this build, current_df already
        contains the full filtered result in RAM, so this returns a LazyFrame
        view of that same data instead of recalculating the search.
        """
        # Return a LazyFrame view on demand instead of storing one persistently.
        # This keeps extension compatibility without adding another app-owned
        # long-lived reference to the current/old DataFrame.
        return self.get_current_lazy_df()

    def get_full_lazy_df(self):
        """Compatibility alias for get_unlimited_lazy_df()."""
        return self.get_unlimited_lazy_df()

    def get_current_query(self):
        return self.search_input.toPlainText().strip()

    def get_search_query(self):
        """Compatibility alias for extensions that inspect the search text."""
        return self.get_current_query()

    def set_search_query(self, text: str):
        self.search_input.setPlainText(str(text or ""))

    def get_last_filters(self):
        """Return a copy of the last search filter dictionary, if available."""
        return dict(self.last_filters or {})

    def get_base_dir(self):
        return BASE_DIR

    def get_data_dir(self):
        return os.path.join(BASE_DIR, "data")

    def get_extensions_dir(self):
        return EXT_DIR

    def set_status(self, msg: str):
        self.lbl_stats.setText(str(msg))

    def refresh_results_ui(self):
        self.update_ui()

    def add_extension_widget(self, widget):
        """Allow extensions to add any QWidget, not only QPushButton."""
        self.ext_button_layout.addWidget(widget)

    def add_extension_control(self, widget):
        """Compatibility alias for add_extension_widget()."""
        self.add_extension_widget(widget)

    def register_extension_button(self, button: QPushButton):
        """Compatibility alias for add_extension_button()."""
        self.add_extension_button(button)

    def append_tag_to_search(self, tag):
        text = self.search_input.toPlainText().strip()
        if not text:
            self.search_input.setPlainText(tag + " ")
            return
        if not text.endswith(" "):
            text += " "
        self.search_input.setPlainText(text + tag + " ")

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        if self.current_df is None or row >= len(self.current_df):
            return

        row_data = self.current_df.row(row, named=True)
        post_id = row_data.get("id")

        menu = QMenu(self)
        action_view = menu.addAction("🖼️ Show Image")
        action_open = menu.addAction("🌐 Open Post in Browser")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == action_view:
            self.show_image_viewer(row)
        elif action == action_open and post_id:
            QDesktopServices.openUrl(QUrl(f"https://danbooru.donmai.us/posts/{post_id}"))

    def on_table_double_clicked(self, item):
        row = item.row()
        if self.current_df is None or row >= len(self.current_df):
            return
        self.show_image_viewer(row)

    def show_image_viewer(self, start_index):
        if self.current_df is not None:
            dialog = ImageViewerDialog(self.current_df.head(100), start_index, self)
            dialog.exec()

    def load_dictionary(self):
        target_path = API_DICT_PATH if os.path.exists(API_DICT_PATH) else DICT_PATH

        if not os.path.exists(target_path):
            return []

        df = pl.read_parquet(target_path)

        if "count" not in df.columns:
            df = df.with_columns(pl.lit(0).alias("count"))

        tag_props = {t: (c, cnt) for t, c, cnt in zip(df["tag"], df["color"], df["count"])}

        tag_data = []
        for t, c, cnt in zip(df["tag"], df["color"], df["count"]):
            tag_data.append((t, t, t, c, cnt))

        alias_path = os.path.join(BASE_DIR, "data", "aliases.parquet")
        if os.path.exists(alias_path):
            adf = pl.read_parquet(alias_path)
            for a, t in zip(adf["alias"], adf["tag"]):
                if t in tag_props:
                    c, cnt = tag_props[t]
                    display_text = f"{a} → {t}"
                    tag_data.append((a, display_text, t, c, cnt))

        return tag_data

    def update_progress(self, msg):
        self.lbl_stats.setText(msg)

    def clear_results_ui(self):
        """Clear table items/widgets so repeated searches do not keep Qt objects alive."""
        self.table.setUpdatesEnabled(False)
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                widget = self.table.cellWidget(row, col)
                if widget is not None:
                    self.table.removeCellWidget(row, col)
                    widget.deleteLater()
        self.table.clearContents()
        self.table.setRowCount(0)
        self.table.setUpdatesEnabled(True)
        gc.collect()

    def cleanup_worker(self, *args):
        """Release the finished SearchWorker object after each search."""
        worker = self.sender()
        if worker is not None:
            worker.deleteLater()
        if getattr(self, "worker", None) is worker:
            self.worker = None
        gc.collect()

    def release_old_results(self):
        """Drop app-owned references to previous result data before a new search.

        This cannot clear references held by third-party extensions, but it
        prevents the main app from keeping old Polars DataFrames/LazyFrames.
        """
        self.current_df = None
        self.unlimited_lazy_df = None
        self.clear_results_ui()
        gc.collect()
        trim_process_working_set()

    def process_data(self):
        if not os.path.exists(DB_PATH) and not os.path.exists(API_DB_PATH):
            self.lbl_stats.setText("Error: No database parquet files found!")
            return

        self.release_old_results()

        self.btn_search.setEnabled(False)
        self.btn_search.setText("Processing...")

        try:
            df = load_combined_lazyframe()

            ratings = []
            if self.cb_g.isChecked(): ratings.append("g")
            if self.cb_s.isChecked(): ratings.append("s")
            if self.cb_q.isChecked(): ratings.append("q")
            if self.cb_e.isChecked(): ratings.append("e")

            raw_query = self.search_input.toPlainText().strip()
            tokens = raw_query.split()

            sort_map_ui = {"Score": "score", "Favorites": "fav_count", "Date": "created_at"}
            sort_col = sort_map_ui[self.sort_combo.currentText()]
            sort_desc = self.sort_order.currentText() == "Descending"

            cleaned_tokens = []
            has_explicit_order = False

            for tok in tokens:
                tok_lower = tok.lower()
                if tok_lower.startswith("order:") or tok_lower.startswith("-order:"):
                    has_explicit_order = True
                    if tok_lower.startswith("-"):
                        tok_lower = tok_lower[1:]

                    order_val = tok_lower.split(":", 1)[1]
                    if order_val in ("id", "id_asc"): sort_col, sort_desc = "id", False
                    elif order_val == "id_desc": sort_col, sort_desc = "id", True
                    elif order_val in ("score", "score_desc"): sort_col, sort_desc = "score", True
                    elif order_val == "score_asc": sort_col, sort_desc = "score", False
                    elif order_val in ("favcount", "favcount_desc"): sort_col, sort_desc = "fav_count", True
                    elif order_val == "favcount_asc": sort_col, sort_desc = "fav_count", False
                    elif order_val in ("created_at", "created_at_desc", "date", "date_desc"): sort_col, sort_desc = "created_at", True
                    elif order_val in ("created_at_asc", "date_asc"): sort_col, sort_desc = "created_at", False
                    elif order_val == "random": sort_col, sort_desc = "random", False
                else:
                    cleaned_tokens.append(tok)

            clean_query = " ".join(cleaned_tokens)

            filters = {
                'raw_query': raw_query,
                'clean_query': clean_query,
                'has_explicit_order': has_explicit_order,
                'sort_col': sort_col,
                'sort_desc': sort_desc,
                'ratings': ratings,
                'date_from': self.date_from.date().toString("yyyy-MM-dd"),
                'date_to': self.date_to.date().toString("yyyy-MM-dd"),
                'orientation': self.orientation_combo.currentText(),
                'min_score': self.spin_score.value() if self.radio_score.isChecked() else None,
                'min_favs': self.spin_fav.value() if self.radio_fav.isChecked() else None,
                'dedup': self.cb_dedup.isChecked(),
                'search_mode': self.search_mode_combo.currentText() if hasattr(self, 'search_mode_combo') else 'Fast in-process',
            }

            self.last_filters = dict(filters)
            self.last_query = raw_query

            use_isolated = hasattr(self, 'search_mode_combo') and self.search_mode_combo.currentIndex() == 1
            worker_cls = SearchWorker if use_isolated else FastSearchWorker
            self.worker = worker_cls(df, filters)
            if use_isolated:
                self.lbl_stats.setText("Memory-safe isolated search selected. Slower but releases temp RAM.")
            else:
                self.lbl_stats.setText("Fast in-process search selected.")
            self.worker.progress.connect(self.update_progress)
            self.worker.finished.connect(self.on_process_success)
            self.worker.error.connect(self.on_process_error)
            self.worker.finished.connect(self.cleanup_worker)
            self.worker.error.connect(self.cleanup_worker)
            self.worker.start()

        except Exception as e:
            self.on_process_error(str(e))

    def on_process_success(self, result_df):
        # Store the complete filtered result in RAM once. The visible table only
        # previews rows from this DataFrame; extensions should reuse this object
        # via get_current_df() or get_unlimited_lazy_df().
        self.current_df = result_df
        # Do not store result_df.lazy() persistently. Creating it on demand avoids
        # an extra long-lived wrapper that can keep old native buffers alive.
        self.unlimited_lazy_df = None
        trim_process_working_set()
        self.update_ui()
        self.btn_search.setEnabled(True)
        self.btn_search.setText("Search")
        gc.collect()

        # Tag dictionary API syncing was moved into the Dataset Updater extension.
        # Use Dataset Updater > Tag Dictionary API to rebuild tags_dictionary_API.parquet.

    def on_process_error(self, error_msg):
        self.lbl_stats.setText(f"Error: {error_msg}")
        self.btn_search.setEnabled(True)
        self.btn_search.setText("Search")

    def on_tag_counts_updated(self, counts_df):
        try:
            dict_df = pl.read_parquet(DICT_PATH)

            if "count" in dict_df.columns:
                dict_df = dict_df.drop("count")

            dict_df = dict_df.join(counts_df, left_on="tag", right_on="tag_string", how="left")
            dict_df = dict_df.with_columns(pl.col("count").fill_null(0))

            dict_df.write_parquet(API_DICT_PATH)

            self.tag_data = self.load_dictionary()
            self.search_input.tag_data = self.tag_data
            self.lbl_stats.setText(self.lbl_stats.text() + " | ✅ Tag counts locally synced to API file!")

        except Exception as e:
            print("Failed to save tag counts:", e)

    def update_ui(self):
        if self.current_df is None:
            return

        self.lbl_stats.setText(f"Found: {len(self.current_df):,}")

        preview_df = self.current_df.head(100)

        self.clear_results_ui()
        self.table.setRowCount(len(preview_df))

        show_thumbs = self.cb_thumbs.isChecked()
        self.table.setColumnHidden(0, not show_thumbs)

        for i, row in enumerate(preview_df.iter_rows(named=True)):

            # 1. Fetch & Show Thumbnail (If Enabled)
            if show_thumbs:
                self.table.setItem(i, 0, QTableWidgetItem(""))

                raw_url = row.get("file_url")
                md5 = row.get("md5")
                thumb_url = ""

                if not md5 and raw_url:
                    match = re.search(r'/([a-f0-9]{32})\.', raw_url)
                    if match: md5 = match.group(1)

                if md5:
                    sub1, sub2 = md5[0:2], md5[2:4]
                    thumb_url = f"https://cdn.donmai.us/180x180/{sub1}/{sub2}/{md5}.jpg"

                if thumb_url:
                    thumb_widget = ThumbnailWidget(thumb_url)
                    self.table.setCellWidget(i, 0, thumb_widget)

            # 2. Text Data
            self.table.setItem(i, 1, QTableWidgetItem(str(row.get("id", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(row.get("rating", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(row.get("score", "0"))))
            self.table.setItem(i, 4, QTableWidgetItem(str(row.get("fav_count", "0"))))

            # 3. Colored Tags
            html = " ".join(filter(None, [
                self.wrap_tag(row.get("tag_string_artist"), "#f38ba8"),
                self.wrap_tag(row.get("tag_string_copyright"), "#cba6f7"),
                self.wrap_tag(row.get("tag_string_character"), "#a6e3a1"),
                self.wrap_tag(row.get("tag_string_general"), "#89b4fa"),
                self.wrap_tag(row.get("tag_string_meta"), "#fab387")
            ]))

            tb = TagBrowser()
            tb.setHtml(html)
            tb.tag_single_clicked.connect(self.append_tag_to_search)
            self.table.setCellWidget(i, 5, tb)

            # Dynamic Row Heights based on thumbnail setting
            self.table.setRowHeight(i, 115 if show_thumbs else 60)

        self.btn_export.setEnabled(len(self.current_df) > 0)
        # Emit the full in-RAM result so extensions receive all matches, not only the preview rows.
        self.data_updated.emit(self.current_df)

    def wrap_tag(self, tags_str, color):
        if not tags_str:
            return ""
        return " ".join([f'<a href="{t}" style="color:{color}; text-decoration:none;">{t}</a>' for t in str(tags_str).split()])

    def export_links(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.current_df["file_url"].drop_nulls().to_list()))
            self.lbl_stats.setText(self.lbl_stats.text() + " (Saved!)")

if __name__ == "__main__":
    mp.freeze_support()
    app = QApplication(sys.argv)
    window = DanbooruApp()
    window.show()
    sys.exit(app.exec())