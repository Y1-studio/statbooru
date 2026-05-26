"""
Annual Seasonality Calendar & Graph for Danbooru Dataset Finder.

Install:
    Save as:
        extensions/tag_annual_seasonality.py

Features:
    - Autocomplete Search Box: Real-time search and filtering of seasonal tags,
      matching the design and behavior of the main application.
    - Manual Apply Button: Filters only run when you click "Apply Filters" -
      change as many controls as you want, no work happens until you commit.
    - Pending-changes indicator: the Apply button highlights yellow with a dot
      when filter controls have changed but haven't been applied yet.
    - Background filter thread: filtering runs off the UI thread so the window
      stays responsive (fixes the freezes when many tags were loaded).
    - Fad Filter: 'Min Recurrence' and 'Max Peak %' strictly eliminate one-time viral trends.
    - Graph Modes: Annual Overlay (365-day) OR All-Time History (Monthly timeline).
    - Normalize All-Time History: View timeline as a percentage of total global posts.
    - Accurately deduplicates posts using MD5 (fallback to ID) exactly like the main app.
    - Save/Load cache system.
"""

import os
import math
import json
import re
import fnmatch
import webbrowser
from urllib.parse import quote
from collections import Counter, deque, defaultdict
from concurrent.futures import ThreadPoolExecutor

try:
    import pyarrow as pa
    import pyarrow.dataset as ds
except Exception:
    pa = None
    ds = None

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QApplication, QGroupBox, QSplitter,
    QDoubleSpinBox, QGridLayout, QWidget, QRadioButton, QButtonGroup,
    QLineEdit, QListWidget, QListWidgetItem
)

# --- CONSTANTS & HELPERS ---

TAG_COLUMNS = [
    ("tag_string_artist", "artist", "#f38ba8"),
    ("tag_string_copyright", "copyright", "#cba6f7"),
    ("tag_string_character", "character", "#a6e3a1"),
    ("tag_string_general", "general", "#89b4fa"),
    ("tag_string_meta", "meta", "#fab387"),
]

DEFAULT_COLOR = "#cdd6f4"

# Apply-button visual states
APPLY_READY_STYLE = "background-color: #94e2d5; color: #11111b; font-weight: bold; padding: 4px 14px;"
APPLY_DIRTY_STYLE = "background-color: #f9e2af; color: #11111b; font-weight: bold; padding: 4px 14px;"
APPLY_BUSY_STYLE  = "background-color: #6c7086; color: #cdd6f4; font-weight: bold; padding: 4px 14px;"

_MONTH_DAYS = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_MONTH_OFFSETS = [0] * 13
for i in range(1, 13):
    _MONTH_OFFSETS[i] = _MONTH_OFFSETS[i-1] + _MONTH_DAYS[i]

def mmdd_to_doy(mm, dd):
    if mm < 1 or mm > 12 or dd < 1 or dd > _MONTH_DAYS[mm]: return -1
    return _MONTH_OFFSETS[mm-1] + dd - 1

def doy_to_mmdd(doy):
    for mm in range(1, 13):
        if doy < _MONTH_OFFSETS[mm]:
            dd = doy - _MONTH_OFFSETS[mm-1] + 1
            return mm, dd
    return 1, 1

def interpolate_color(val, min_val, max_val, c_empty, c_hot):
    if max_val <= min_val or val <= min_val: return c_empty
    ratio = math.log1p(val - min_val) / math.log1p(max_val - min_val)
    r1, g1, b1, _ = c_empty.getRgb()
    r2, g2, b2, _ = c_hot.getRgb()
    return QColor(int(r1 + (r2 - r1) * ratio), int(g1 + (g2 - g1) * ratio), int(b1 + (b2 - b1) * ratio))

def generate_ym_range(min_ym, max_ym):
    start_y, start_m = int(min_ym[:4]), int(min_ym[5:7])
    end_y, end_m = int(max_ym[:4]), int(max_ym[5:7])
    res = []
    y, m = start_y, start_m
    while (y < end_y) or (y == end_y and m <= end_m):
        res.append(f"{y}-{m:02d}")
        m += 1
        if m > 12: m, y = 1, y + 1
    return res

def format_count(c):
    if c >= 1_000_000: return f"{c/1_000_000:.1f}M"
    if c >= 1_000: return f"{c/1_000:.1f}k"
    return str(c)


# --- AUTOCOMPLETE LINE EDIT ---

class ExtAutocompletePopup(QListWidget):
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

class ExtTagAutocompleteLineEdit(QLineEdit):
    def __init__(self, tag_data):
        super().__init__()
        self.tag_data = tag_data
        self.popup = ExtAutocompletePopup(self)
        self.popup.itemClicked.connect(self.insert_completion)
        self.textChanged.connect(self.on_text_changed)
        self.setStyleSheet("background-color: #313244; border: 1px solid #45475a; border-radius: 6px; padding: 6px; color: #cdd6f4;")

    def keyPressEvent(self, event):
        if self.popup.isVisible():
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                current_row = self.popup.currentRow()
                next_row = min(current_row + 1, self.popup.count() - 1) if event.key() == Qt.Key.Key_Down else max(current_row - 1, 0)
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
        text = self.text()
        cursor_pos = self.cursorPosition()
        text_before = text[:cursor_pos]
        parts = re.split(r'\s+', text_before)
        current_word = parts[-1]

        prefix = ""
        if current_word.startswith("-") or current_word.startswith("~"):
            prefix = current_word[0]
            current_word = current_word[1:]

        if len(current_word) < 2 or not self.tag_data:
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
        p = self.mapToGlobal(rect.bottomLeft())
        self.popup.setGeometry(p.x(), p.y() + 4, 350, 200)
        self.popup.show()

    def insert_completion(self, item):
        if not item: return
        selected_tag = item.data(Qt.ItemDataRole.UserRole)
        text = self.text()
        cursor_pos = self.cursorPosition()

        text_before = text[:cursor_pos]
        text_after = text[cursor_pos:]

        parts = re.split(r'(\s+)', text_before)
        parts[-1] = selected_tag + " "
        new_text_before = "".join(parts)

        self.blockSignals(True)
        self.setText(new_text_before + text_after)
        self.setCursorPosition(len(new_text_before))
        self.blockSignals(False)
        self.popup.hide()


# --- DB-SCAN WORKER THREAD ---

def _pass1_batch(pyd, cols, valid_indices):
    c = Counter()
    col_arrays = [pyd.get(col) for col in cols]
    n = 0
    for arr in col_arrays:
        if arr: n = len(arr); break
    indices = valid_indices if valid_indices is not None else range(n)
    for i in indices:
        for arr in col_arrays:
            if arr and (val := (arr[i] if i < len(arr) else None)):
                for t in str(val).split(): c[t] += 1
    return c

def _pass2_batch(pyd, sel_cols_info, valid_tags, valid_indices):
    partial_doy = defaultdict(lambda: defaultdict(int))
    partial_ym = defaultdict(lambda: defaultdict(int))
    partial_global_ym = defaultdict(int)
    cat_vote = {}

    ca_col = pyd.get("created_at")
    n = len(ca_col) if ca_col else 0
    indices = valid_indices if valid_indices is not None else range(n)
    col_arrays = [(pyd.get(col), cat, color) for col, cat, color in sel_cols_info]

    for i in indices:
        ca = ca_col[i] if i < len(ca_col) else None
        if not ca: continue
        s = str(ca)
        if len(s) < 10: continue
        try: yyyy, mm, dd = int(s[0:4]), int(s[5:7]), int(s[8:10])
        except ValueError: continue

        doy = mmdd_to_doy(mm, dd)
        if doy < 0: continue

        ym_str = f"{yyyy}-{mm:02d}"
        partial_global_ym[ym_str] += 1

        row_tags = []
        for arr, cat, color in col_arrays:
            if arr and (val := (arr[i] if i < len(arr) else None)):
                for t in str(val).split():
                    if t in valid_tags: row_tags.append((t, cat, color))

        if not row_tags: continue

        for t, cat, color in row_tags:
            partial_doy[t][doy] += 1
            partial_ym[t][ym_str] += 1
            if t not in cat_vote: cat_vote[t] = (cat, color)

    return partial_doy, partial_ym, partial_global_ym, cat_vote


class AnnualSeasonalityWorker(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(dict, dict, dict, dict)
    failed = pyqtSignal(str)

    def __init__(self, base_dir, settings):
        super().__init__()
        self.base_dir = base_dir
        self.settings = settings

    def _db_paths(self):
        return [p for name in ("danbooru2026_clean.parquet", "danbooru_api_clean.parquet")
                if os.path.exists(p := os.path.join(self.base_dir, "data", name))]

    def _get_valid_indices(self, pyd, seen_keys):
        md5_arr = pyd.get("md5"); id_arr = pyd.get("id")
        n = len(md5_arr) if md5_arr else (len(id_arr) if id_arr else 0)
        if n == 0: return None

        valid = []
        for i in range(n):
            key = None
            if md5_arr and i < len(md5_arr) and md5_arr[i]: key = md5_arr[i]
            elif id_arr and i < len(id_arr) and id_arr[i]: key = str(id_arr[i])
            if key:
                if key not in seen_keys: seen_keys.add(key); valid.append(i)
            else: valid.append(i)
        return valid

    def run(self):
        try: self._run()
        except Exception as e:
            import traceback; traceback.print_exc()
            self.failed.emit(str(e))

    def _run(self):
        if pa is None or ds is None: return self.failed.emit("Missing pyarrow")
        paths = self._db_paths()
        if not paths: return self.failed.emit("No databases found in data/ folder.")

        dataset = ds.dataset(paths, format="parquet")
        schema_names = dataset.schema.names

        dedup_cols = []
        if "id" in schema_names: dedup_cols.append("id")
        if "md5" in schema_names: dedup_cols.append("md5")

        sel_types = self.settings["selected_types"]
        cols_to_scan = [c for c, cat, _ in TAG_COLUMNS if cat in sel_types and c in schema_names]
        sel_cols_info = [(c, cat, color) for c, cat, color in TAG_COLUMNS if cat in sel_types and c in schema_names]

        workers, batch_size, min_posts = self.settings["num_workers"], self.settings["batch_size"], self.settings["min_posts"]
        seen_keys = set()

        self.progress.emit(f"Pass 1: Identifying tags with ≥{min_posts:,} posts...")
        scanner1 = dataset.scanner(columns=dedup_cols + cols_to_scan, batch_size=batch_size, use_threads=True)
        global_counts = Counter()
        scanned1 = last_emit1 = 0

        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = deque()
            for batch in scanner1.to_batches():
                pyd = batch.to_pydict()
                valid_indices = self._get_valid_indices(pyd, seen_keys)
                pending.append(pool.submit(_pass1_batch, pyd, cols_to_scan, valid_indices))
                scanned1 += batch.num_rows
                if scanned1 - last_emit1 >= 500_000: self.progress.emit(f"Pass 1: Scanned {scanned1:,} rows..."); last_emit1 = scanned1
                while len(pending) > workers + 2: global_counts.update(pending.popleft().result())
            while pending: global_counts.update(pending.popleft().result())

        valid_tags = {t for t, c in global_counts.items() if c >= min_posts}
        if not valid_tags: return self.failed.emit(f"No tags met the {min_posts} threshold.")

        self.progress.emit(f"Pass 2: Extracting dates for {len(valid_tags):,} candidate tags...")
        seen_keys.clear()

        scanner2 = dataset.scanner(columns=dedup_cols + ["created_at"] + cols_to_scan, batch_size=batch_size, use_threads=True)
        tag_doy_counts = {t: [0]*366 for t in valid_tags}
        tag_ym_counts = {t: Counter() for t in valid_tags}
        global_ym_counts = Counter()
        cat_vote = {}
        scanned2 = last_emit2 = 0

        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = deque()
            for batch in scanner2.to_batches():
                pyd = batch.to_pydict()
                valid_indices = self._get_valid_indices(pyd, seen_keys)
                pending.append(pool.submit(_pass2_batch, pyd, sel_cols_info, valid_tags, valid_indices))
                scanned2 += batch.num_rows
                if scanned2 - last_emit2 >= 500_000: self.progress.emit(f"Pass 2: Extracted dates for {scanned2:,} rows..."); last_emit2 = scanned2
                while len(pending) > workers + 2:
                    pdoy, pym, pglobal_ym, pcat = pending.popleft().result()
                    for t, d_dict in pdoy.items():
                        for d, c in d_dict.items(): tag_doy_counts[t][d] += c
                    for t, ym_dict in pym.items(): tag_ym_counts[t].update(ym_dict)
                    global_ym_counts.update(pglobal_ym); cat_vote.update(pcat)
            while pending:
                pdoy, pym, pglobal_ym, pcat = pending.popleft().result()
                for t, d_dict in pdoy.items():
                    for d, c in d_dict.items(): tag_doy_counts[t][d] += c
                for t, ym_dict in pym.items(): tag_ym_counts[t].update(ym_dict)
                global_ym_counts.update(pglobal_ym); cat_vote.update(pcat)

        self.progress.emit(f"Extraction complete! Building visuals...")
        self.finished_ok.emit(tag_doy_counts, dict(tag_ym_counts), dict(global_ym_counts), cat_vote)


# --- FILTER WORKER ---

class FilterWorker(QThread):
    done = pyqtSignal(list, list)

    def __init__(self, tag_doy_counts, tag_ym_counts, cat_vote, params):
        super().__init__()
        self.tag_doy_counts = tag_doy_counts
        self.tag_ym_counts = tag_ym_counts
        self.cat_vote = cat_vote
        self.p = params

    def run(self):
        w               = self.p["w"]
        min_score       = self.p["min_score"]
        max_peak_share  = self.p["max_peak_share"]
        min_recurrence  = self.p["min_recurrence"]
        sel_types       = self.p["sel_types"]
        search_query    = self.p["search_query"]

        results = []
        global_heat = [0.0] * 366
        search_tokens = search_query.split() if search_query else []

        for t, doy_arr in self.tag_doy_counts.items():
            cat, color = self.cat_vote.get(t, ("unknown", DEFAULT_COLOR))

            # Query filtering
            if search_tokens:
                matched_all = True
                for tok in search_tokens:
                    is_neg = tok.startswith('-')
                    clean_tok = tok[1:] if is_neg else tok
                    match = fnmatch.fnmatchcase(t, clean_tok)
                    if (is_neg and match) or (not is_neg and not match):
                        matched_all = False
                        break
                if not matched_all:
                    continue

            if cat not in sel_types:
                continue

            total = sum(doy_arr)
            if total == 0:
                continue

            doubled = doy_arr + doy_arr
            w_sum = max_sum = sum(doubled[0:w])
            best_doy = 0
            for i in range(1, 366):
                w_sum += doubled[i + w - 1] - doubled[i - 1]
                if w_sum > max_sum:
                    max_sum, best_doy = w_sum, i

            peak_avg = max_sum / w
            bg_avg = (total - max_sum) / (366 - w) if (366 - w) > 0 else 0
            score = (peak_avg + 1e-5) / (bg_avg + 1e-5)

            if score < min_score:
                continue

            start_mm, _ = doy_to_mmdd(best_doy)
            end_mm,   _ = doy_to_mmdd((best_doy + w - 1) % 366)
            months_to_check = {start_mm, end_mm}

            ym_counts = self.tag_ym_counts.get(t, {})
            peak_months_per_year = Counter()
            for ym, count in ym_counts.items():
                y_str, m_str = ym.split("-")
                if int(m_str) in months_to_check:
                    peak_months_per_year[int(y_str)] += count

            total_peak_months = sum(peak_months_per_year.values())
            if total_peak_months == 0:
                continue

            max_year_peak = max(peak_months_per_year.values())
            my_share = max_year_peak / total_peak_months

            if my_share > max_peak_share:
                continue

            threshold = max_year_peak * 0.10
            years_spiked = sum(1 for v in peak_months_per_year.values() if v >= threshold)

            if years_spiked < min_recurrence:
                continue

            mm, dd = doy_to_mmdd(best_doy + w // 2)
            for offset in range(w):
                global_heat[(best_doy + offset) % 366] += 1

            results.append({
                "tag": t, "category": cat, "color": color,
                "peak_date": f"{mm:02d}-{dd:02d}", "best_doy": best_doy,
                "w": w, "score": score, "peak_posts": max_sum,
                "bg_avg": bg_avg, "max_peak_share": my_share * 100.0,
                "years_spiked": years_spiked,
                "total_posts": total,
            })

        self.done.emit(results, global_heat)


# --- CUSTOM UI WIDGETS ---

class NumericTableItem(QTableWidgetItem):
    def __init__(self, display_text, sort_value):
        super().__init__(display_text)
        self.sort_value = sort_value
    def __lt__(self, other):
        if isinstance(other, NumericTableItem): return self.sort_value < other.sort_value
        return super().__lt__(other)

class CalendarGrid(QTableWidget):
    dateClicked = pyqtSignal(int, int)
    def __init__(self):
        super().__init__(31, 12)
        self.setHorizontalHeaderLabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        self.setVerticalHeaderLabels([str(i) for i in range(1, 32)])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setStyleSheet("QTableWidget { gridline-color: #313244; border-radius: 6px; }")
        for row in range(31):
            for col in range(12): self.setItem(row, col, QTableWidgetItem())
        self.cellClicked.connect(lambda r, c: self.dateClicked.emit(c+1, r+1) if mmdd_to_doy(c+1, r+1) >= 0 else None)

    def set_heat(self, heat_array_366, base_color="#313244", hot_color="#f38ba8"):
        max_val = max(heat_array_366) if heat_array_366 else 0
        c_empty, c_hot = QColor(base_color), QColor(hot_color)
        for col in range(12):
            for row in range(31):
                doy = mmdd_to_doy(col+1, row+1)
                item = self.item(row, col)
                if doy < 0:
                    item.setBackground(QColor("#181825")); item.setFlags(Qt.ItemFlag.NoItemFlags); item.setToolTip("")
                else:
                    val = heat_array_366[doy]
                    item.setBackground(interpolate_color(val, 0, max_val, c_empty, c_hot))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setToolTip(f"{col+1:02d}-{row+1:02d}  (Intensity: {val:g})")


# --- MAIN DIALOG ---

class AnnualSeasonalityDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.worker = None
        self.filter_worker = None
        self.filters_dirty = False
        self.cache_file = os.path.join(self._base_dir(), "data", "seasonality_cache.json")

        self.tag_doy_counts = {}
        self.tag_ym_counts = {}
        self.global_ym_counts = {}
        self.cat_vote = {}

        self.active_results = []
        self.active_global_heat = []

        self.setWindowTitle("Annual Seasonality Calendar & Graph")
        self.resize(1480, 950)
        self._build_ui()

        if os.path.exists(self.cache_file):
            self.lbl_status.setText("Cache file found. You can 'Load Cache' to view previous results instantly.")

    def _build_ui(self):
        layout = QVBoxLayout(self)

        cfg = QGroupBox("Analysis Settings")
        cfg_layout = QGridLayout(cfg)

        # Row 0: DB Scan Parameters
        scan_layout = QHBoxLayout()
        scan_layout.addWidget(QLabel("<b>[Requires Rescan]</b> Min Total Posts:"))
        self.spin_min_posts = QSpinBox(); self.spin_min_posts.setRange(100, 1_000_000); self.spin_min_posts.setSingleStep(500); self.spin_min_posts.setValue(1000)
        scan_layout.addWidget(self.spin_min_posts)

        scan_layout.addSpacing(20)
        scan_layout.addWidget(QLabel("Workers:")); self.spin_workers = QSpinBox(); self.spin_workers.setRange(1, max(8, os.cpu_count() or 1)); self.spin_workers.setValue(max(2, (os.cpu_count() or 4) // 2)); scan_layout.addWidget(self.spin_workers)
        scan_layout.addWidget(QLabel("Batch Size:")); self.spin_batch = QSpinBox(); self.spin_batch.setRange(10_000, 200_000); self.spin_batch.setSingleStep(10_000); self.spin_batch.setValue(50_000); scan_layout.addWidget(self.spin_batch)

        scan_layout.addStretch()
        self.btn_load = QPushButton("📂 Load Cache"); self.btn_load.clicked.connect(self.load_cache); self.btn_load.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold;")
        self.btn_save = QPushButton("💾 Save Cache"); self.btn_save.clicked.connect(self.save_cache); self.btn_save.setStyleSheet("background-color: #cba6f7; color: #11111b; font-weight: bold;")
        self.btn_analyze = QPushButton("🚀 Run Database Scan"); self.btn_analyze.clicked.connect(self.start); self.btn_analyze.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        scan_layout.addWidget(self.btn_load); scan_layout.addWidget(self.btn_save); scan_layout.addWidget(self.btn_analyze)
        cfg_layout.addLayout(scan_layout, 0, 0, 1, 6)

        # Row 1: Filter controls + Apply button
        live_layout = QHBoxLayout()
        live_layout.addWidget(QLabel("<b>[Filters]</b> Tag Types:"))

        self.chks = {}
        for k, lbl, c in [("artist","Artist","#f38ba8"), ("copyright","Copyright","#cba6f7"), ("character","Character","#a6e3a1"), ("general","General","#89b4fa"), ("meta","Meta","#fab387")]:
            chk = QCheckBox(lbl); chk.setChecked(k != "meta"); chk.setStyleSheet(f"color: {c};")
            chk.toggled.connect(self.mark_dirty)
            self.chks[k] = chk; live_layout.addWidget(chk)

        live_layout.addSpacing(20)
        live_layout.addWidget(QLabel("Peak Window:"))
        self.spin_window = QSpinBox(); self.spin_window.setRange(1, 90); self.spin_window.setValue(7)
        self.spin_window.valueChanged.connect(self.mark_dirty)
        live_layout.addWidget(self.spin_window)

        live_layout.addWidget(QLabel("Min Score:"))
        self.spin_score = QDoubleSpinBox(); self.spin_score.setRange(1.0, 500.0); self.spin_score.setSingleStep(0.2); self.spin_score.setValue(1.8)
        self.spin_score.valueChanged.connect(self.mark_dirty)
        live_layout.addWidget(self.spin_score)

        live_layout.addWidget(QLabel("Max Peak Year %:"))
        self.spin_max_year = QSpinBox(); self.spin_max_year.setRange(10, 100); self.spin_max_year.setValue(50); self.spin_max_year.setSuffix(" %")
        self.spin_max_year.valueChanged.connect(self.mark_dirty)
        live_layout.addWidget(self.spin_max_year)

        live_layout.addWidget(QLabel("Min Recurrence:"))
        self.spin_recurrence = QSpinBox(); self.spin_recurrence.setRange(1, 15); self.spin_recurrence.setValue(3)
        self.spin_recurrence.valueChanged.connect(self.mark_dirty)
        live_layout.addWidget(self.spin_recurrence)

        live_layout.addSpacing(20)
        self.btn_apply = QPushButton("✓ Apply Filters")
        self.btn_apply.clicked.connect(self.apply_filters)
        self.btn_apply.setStyleSheet(APPLY_READY_STYLE)
        live_layout.addWidget(self.btn_apply)

        live_layout.addStretch()
        cfg_layout.addLayout(live_layout, 1, 0, 1, 6)

        # Row 2: Tag Filter Box with Autocomplete (using standard QLineEdit, no resize handle)
        search_filter_layout = QHBoxLayout()
        search_filter_layout.addWidget(QLabel("<b>Tag Search Filter:</b>"))
        self.txt_tag_search = ExtTagAutocompleteLineEdit(getattr(self.app, "tag_data", []))
        self.txt_tag_search.setPlaceholderText("Filter seasonal results by tag name (supports *wildcards* and -negations)...")
        self.txt_tag_search.textChanged.connect(self.mark_dirty)
        search_filter_layout.addWidget(self.txt_tag_search)
        cfg_layout.addLayout(search_filter_layout, 2, 0, 1, 6)

        layout.addWidget(cfg)

        self.lbl_status = QLabel("Ready. Select tag types and configure thresholds, then run analysis.")
        self.lbl_status.setStyleSheet("color: #f9e2af; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # Calendar Area
        cal_widget = QWidget(); cal_layout = QVBoxLayout(cal_widget); cal_layout.setContentsMargins(0,0,0,0)
        cal_ctrl = QHBoxLayout()
        self.lbl_cal_view = QLabel("<b>View:</b> Global Seasonality Heatmap")
        cal_ctrl.addWidget(self.lbl_cal_view); cal_ctrl.addStretch()
        self.btn_reset_view = QPushButton("🌍 Reset to Global Heat"); self.btn_reset_view.clicked.connect(self.reset_view)
        cal_ctrl.addWidget(self.btn_reset_view)
        cal_layout.addLayout(cal_ctrl)
        self.calendar = CalendarGrid(); self.calendar.dateClicked.connect(self.on_calendar_clicked)
        cal_layout.addWidget(self.calendar)
        left_splitter.addWidget(cal_widget)

        # Graph Area
        chart_widget = QWidget(); chart_layout = QVBoxLayout(chart_widget); chart_layout.setContentsMargins(0,10,0,0)

        graph_ctrl = QHBoxLayout()
        graph_ctrl.addWidget(QLabel("<b>Graph Mode:</b>"))
        self.radio_annual = QRadioButton("Annual Overlay (365 Days)")
        self.radio_history = QRadioButton("All-Time History (Months)")
        self.radio_annual.setChecked(True)

        self.chk_normalize = QCheckBox("Normalize (%)")
        self.chk_normalize.setStyleSheet("color: #cdd6f4;")
        self.chk_normalize.toggled.connect(self.on_table_selection)

        self.btn_group = QButtonGroup()
        self.btn_group.addButton(self.radio_annual); self.btn_group.addButton(self.radio_history)
        self.radio_annual.toggled.connect(self.on_table_selection)

        graph_ctrl.addWidget(self.radio_annual); graph_ctrl.addWidget(self.radio_history)
        graph_ctrl.addWidget(self.chk_normalize)
        graph_ctrl.addStretch()
        chart_layout.addLayout(graph_ctrl)

        self.fig = Figure(dpi=100, facecolor="#1e1e2e")
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111); self.ax.set_facecolor("#313244"); self.ax.tick_params(colors="#cdd6f4")
        for spine in self.ax.spines.values(): spine.set_color("#6c7086")
        chart_layout.addWidget(self.canvas)
        left_splitter.addWidget(chart_widget)

        main_splitter.addWidget(left_splitter)

        # Table Area
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget); right_layout.setContentsMargins(0,0,0,0)
        self.lbl_table_target = QLabel("<b>Tags peaking on:</b> All Dates")
        right_layout.addWidget(self.lbl_table_target)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Tag", "Category", "Peak Date", "Score", "Window Posts", "Bg Avg / Day", "Max Peak %", "Spiked Years", "Total Posts"])
        for i in range(8): self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_table_selection)
        right_layout.addWidget(self.table)

        btns = QHBoxLayout()
        self.btn_include = QPushButton("Include"); self.btn_include.clicked.connect(self.add_selected_include)
        self.btn_exclude = QPushButton("Exclude"); self.btn_exclude.clicked.connect(self.add_selected_exclude)
        self.btn_search = QPushButton("Main Window Search"); self.btn_search.clicked.connect(self.search_selected_alone)
        self.btn_browser = QPushButton("Danbooru"); self.btn_browser.clicked.connect(self.open_selected_on_danbooru)
        for b in [self.btn_include, self.btn_exclude, self.btn_search, self.btn_browser]: btns.addWidget(b)
        right_layout.addLayout(btns)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([650, 800])
        layout.addWidget(main_splitter)

    def _base_dir(self): return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def save_cache(self):
        if not self.tag_doy_counts: return QMessageBox.warning(self, "No Data", "Run a scan first.")
        try:
            self.lbl_status.setText("Saving cache to disk..."); QApplication.processEvents()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "tag_doy_counts": self.tag_doy_counts, "tag_ym_counts": self.tag_ym_counts,
                    "global_ym_counts": self.global_ym_counts, "cat_vote": self.cat_vote
                }, f)
            self.lbl_status.setText("Cache saved successfully!")
            QMessageBox.information(self, "Saved", "Analysis cache saved successfully!")
        except Exception as e: QMessageBox.critical(self, "Save Error", f"Failed to save cache:\n{str(e)}")

    def load_cache(self):
        if not os.path.exists(self.cache_file): return QMessageBox.warning(self, "No Cache", "No cache file found in the data/ folder.")
        try:
            self.lbl_status.setText("Loading cache from disk..."); QApplication.processEvents()
            with open(self.cache_file, 'r', encoding='utf-8') as f: data = json.load(f)

            self.tag_doy_counts = data["tag_doy_counts"]
            self.tag_ym_counts = data.get("tag_ym_counts", {})
            self.global_ym_counts = data.get("global_ym_counts", {})
            self.cat_vote = data.get("cat_vote", {})

            if not self.tag_ym_counts or not self.global_ym_counts:
                QMessageBox.information(self, "Old Cache", "This cache lacks Timeline/Fad-Filtering data. Rescan to unlock these features.")
                return

            self.lbl_status.setText("Cache loaded. Running first filter pass...")
            self.apply_filters()
        except Exception as e: QMessageBox.critical(self, "Load Error", f"Failed to load cache:\n{str(e)}")

    def start(self):
        if self.worker is not None and self.worker.isRunning(): return

        sel_types = [k for k, cb in self.chks.items()]
        settings = {
            "selected_types": sel_types, "min_posts": self.spin_min_posts.value(),
            "batch_size": self.spin_batch.value(), "num_workers": self.spin_workers.value()
        }
        self.btn_analyze.setEnabled(False); self.btn_analyze.setText("Scanning Database...")
        self.worker = AnnualSeasonalityWorker(self._base_dir(), settings)
        self.worker.progress.connect(self.lbl_status.setText)
        self.worker.finished_ok.connect(self.on_success)
        self.worker.failed.connect(self.on_error)
        self.worker.start()

    def on_success(self, tag_doy_counts, tag_ym_counts, global_ym_counts, cat_vote):
        self.tag_doy_counts = tag_doy_counts
        self.tag_ym_counts = tag_ym_counts
        self.global_ym_counts = global_ym_counts
        self.cat_vote = cat_vote
        self.lbl_status.setText("Database extraction complete. Running first filter pass...")
        self.btn_analyze.setEnabled(True); self.btn_analyze.setText("🚀 Run Database Scan"); self.worker = None
        self.apply_filters()

    def on_error(self, err):
        self.lbl_status.setText(f"Error: {err}"); QMessageBox.critical(self, "Scan Failed", err)
        self.btn_analyze.setEnabled(True); self.btn_analyze.setText("🚀 Run Database Scan"); self.worker = None

    def mark_dirty(self):
        if not self.tag_doy_counts:
            return
        if self.filters_dirty:
            return
        self.filters_dirty = True
        self.btn_apply.setText("✓ Apply Filters  ●")
        self.btn_apply.setStyleSheet(APPLY_DIRTY_STYLE)
        self.lbl_status.setText("Filter changes pending - click '✓ Apply Filters' to refresh.")

    def apply_filters(self):
        if not self.tag_doy_counts:
            QMessageBox.warning(self, "No Data", "Load a cache or run a database scan first.")
            return
        if self.filter_worker is not None and self.filter_worker.isRunning():
            return

        params = {
            "w":              self.spin_window.value(),
            "min_score":      self.spin_score.value(),
            "max_peak_share": self.spin_max_year.value() / 100.0,
            "min_recurrence": self.spin_recurrence.value(),
            "sel_types":      set(k for k, cb in self.chks.items() if cb.isChecked()),
            "search_query":   self.txt_tag_search.text().strip()
        }

        self.btn_apply.setEnabled(False)
        self.btn_apply.setText("⏳ Filtering...")
        self.btn_apply.setStyleSheet(APPLY_BUSY_STYLE)
        self.lbl_status.setText(f"Filtering {len(self.tag_doy_counts):,} tags in the background...")

        self.filter_worker = FilterWorker(self.tag_doy_counts, self.tag_ym_counts, self.cat_vote, params)
        self.filter_worker.done.connect(self._on_filter_done)
        self.filter_worker.start()

    def _on_filter_done(self, results, global_heat):
        self.active_results = results
        self.active_global_heat = global_heat
        self.filters_dirty = False
        self.btn_apply.setEnabled(True)
        self.btn_apply.setText("✓ Apply Filters")
        self.btn_apply.setStyleSheet(APPLY_READY_STYLE)
        self.lbl_status.setText(f"Done. {len(results):,} recurring seasonal tags match the current filters.")
        self.filter_worker = None
        self.reset_view()

    def populate_table(self, results):
        self.table.blockSignals(True); self.table.clearSelection(); self.table.setSortingEnabled(False); self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            color = QColor(r["color"])
            t_item = QTableWidgetItem(r["tag"]); t_item.setForeground(color); t_item.setData(Qt.ItemDataRole.UserRole, r["tag"])
            c_item = QTableWidgetItem(r["category"]); c_item.setForeground(color)
            self.table.setItem(i, 0, t_item); self.table.setItem(i, 1, c_item)
            self.table.setItem(i, 2, QTableWidgetItem(r["peak_date"]))
            self.table.setItem(i, 3, NumericTableItem(f"{r['score']:.2f}x", r["score"]))
            self.table.setItem(i, 4, NumericTableItem(f"{r['peak_posts']:,}", r["peak_posts"]))
            self.table.setItem(i, 5, NumericTableItem(f"{r['bg_avg']:.2f}", r["bg_avg"]))
            self.table.setItem(i, 6, NumericTableItem(f"{r['max_peak_share']:.1f}%", r["max_peak_share"]))
            self.table.setItem(i, 7, NumericTableItem(f"{r['years_spiked']} Yrs", r["years_spiked"]))
            self.table.setItem(i, 8, NumericTableItem(f"{r['total_posts']:,}", r["total_posts"]))
        self.table.setSortingEnabled(True); self.table.sortItems(3, Qt.SortOrder.DescendingOrder); self.table.blockSignals(False)

    def draw_chart(self, title, heat_data, line_color="#f38ba8", is_global=False):
        self.ax.clear()
        if not heat_data:
            self.canvas.draw(); return

        x = list(range(1, 367))
        if is_global:
            self.ax.bar(x, heat_data, color=line_color, alpha=0.8, width=1.0)
            self.ax.set_ylabel("Overlapping Spikes", color="#cdd6f4")
        else:
            w = 7; smoothed = []; doubled = heat_data + heat_data
            for i in range(366): smoothed.append(sum(doubled[i:i+w])/w)

            self.ax.bar(x, heat_data, color="#45475a", alpha=0.6, width=1.0, label="Raw Daily Posts")
            self.ax.plot(x, smoothed, color=line_color, linewidth=2, label="7-Day Avg")
            self.ax.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4")
            self.ax.set_ylabel("Total Posts", color="#cdd6f4")

        self.ax.set_title(title, color="#cdd6f4", pad=12)
        month_starts = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        self.ax.set_xticks(month_starts); self.ax.set_xticklabels(month_names, rotation=45, ha='left')
        self.ax.tick_params(colors="#cdd6f4")
        for spine in self.ax.spines.values(): spine.set_color("#6c7086")
        self.ax.grid(axis="y", linestyle="--", alpha=0.2); self.fig.tight_layout(); self.canvas.draw()

    def draw_timeline(self, title, ym_data, line_color="#f38ba8", normalize=False):
        self.ax.clear()
        if not ym_data:
            self.canvas.draw(); return

        keys = sorted(ym_data.keys())
        all_months = generate_ym_range(keys[0], keys[-1])

        if normalize and self.global_ym_counts:
            y_vals = [(ym_data.get(m, 0) / max(1, self.global_ym_counts.get(m, 1))) * 100.0 for m in all_months]
            self.ax.set_ylabel("Percentage of Total Posts (%)", color="#cdd6f4")
        else:
            y_vals = [ym_data.get(m, 0) for m in all_months]
            self.ax.set_ylabel("Monthly Posts", color="#cdd6f4")

        x_vals = range(len(all_months))

        self.ax.plot(x_vals, y_vals, color=line_color, linewidth=2)
        self.ax.fill_between(x_vals, y_vals, color=line_color, alpha=0.2)

        self.ax.set_title(title, color="#cdd6f4", pad=12)
        tick_spacing = max(1, len(all_months) // 12)
        self.ax.set_xticks(x_vals[::tick_spacing])
        self.ax.set_xticklabels([all_months[i] for i in x_vals[::tick_spacing]], rotation=45, ha='right')

        self.ax.tick_params(colors="#cdd6f4")
        for spine in self.ax.spines.values(): spine.set_color("#6c7086")
        self.ax.grid(axis="y", linestyle="--", alpha=0.2); self.ax.grid(axis="x", linestyle="--", alpha=0.1)
        self.fig.tight_layout(); self.canvas.draw()

    def reset_view(self):
        self.lbl_table_target.setText("<b>Tags peaking on:</b> All Dates"); self.populate_table(self.active_results)
        self.table.clearSelection(); self.radio_annual.setChecked(True)
        if self.active_global_heat:
            self.calendar.set_heat(self.active_global_heat, hot_color="#f9e2af")
            self.lbl_cal_view.setText("<b>View:</b> Global Seasonality (Heatmap of Spikes)")
            self.draw_chart("Global Seasonality: Concurrent Peak Windows", self.active_global_heat, "#f9e2af", is_global=True)

    def on_calendar_clicked(self, mm, dd):
        if not self.active_results: return
        target, click_doy = f"{mm:02d}-{dd:02d}", mmdd_to_doy(mm, dd)
        filtered = []
        for r in self.active_results:
            b_doy, w = r["best_doy"], r["w"]
            if b_doy <= click_doy < b_doy + w: filtered.append(r)
            elif b_doy + w > 366 and (click_doy >= b_doy or click_doy < (b_doy + w) % 366): filtered.append(r)
        self.lbl_table_target.setText(f"<b>Tags peaking during window overlapping:</b> {target}")
        self.populate_table(filtered)

    def on_table_selection(self):
        if not (sel := self.table.selectedItems()): return
        if (item := self.table.item(sel[0].row(), 0)) is None: return

        tag = item.data(Qt.ItemDataRole.UserRole)
        color = item.foreground().color().name()

        if heat := self.tag_doy_counts.get(tag):
            self.calendar.set_heat(heat, hot_color=color)
            self.lbl_cal_view.setText(f"<b>View:</b> Single Tag Heatmap -> {tag}")

        if self.radio_annual.isChecked():
            if heat: self.draw_chart(f"Annual Overlay (365 Days): {tag}", heat, color, is_global=False)
        else:
            if ym_heat := self.tag_ym_counts.get(tag):
                self.draw_timeline(f"All-Time History: {tag}", ym_heat, color, normalize=self.chk_normalize.isChecked())
            else:
                self.ax.clear(); self.ax.set_title(f"No Timeline Data for {tag} (Update Cache)", color="#cdd6f4"); self.canvas.draw()

    def selected_tag(self):
        return item.data(Qt.ItemDataRole.UserRole) if (sel := self.table.selectedItems()) and (item := self.table.item(sel[0].row(), 0)) else None
    def add_selected_include(self):
        if t := self.selected_tag(): getattr(self.app, "add_tag_to_include", lambda x: QApplication.clipboard().setText(x))(t)
    def add_selected_exclude(self):
        if t := self.selected_tag(): getattr(self.app, "add_tag_to_exclude", lambda x: QApplication.clipboard().setText(x))(t)
    def search_selected_alone(self):
        if t := self.selected_tag():
            if hasattr(self.app, "search_input"): self.app.search_input.setPlainText(t)
            if hasattr(self.app, "blacklist_input"): self.app.blacklist_input.clear()
            if callable(getattr(self.app, "process_data", None)): self.app.process_data()
            self.close()
    def open_selected_on_danbooru(self):
        if t := self.selected_tag(): webbrowser.open(f"https://danbooru.donmai.us/posts?tags={quote(t)}", new=2)

class AnnualSeasonalityPlugin:
    def __init__(self, app):
        self.app = app; self.dialog = None
        self.btn = QPushButton("📅 Annual Seasonality Calendar")
        self.btn.clicked.connect(self.show_dialog); app.add_extension_button(self.btn)
    def show_dialog(self):
        if self.dialog is None: self.dialog = AnnualSeasonalityDialog(self.app)
        if hasattr(self.app, "tag_data"):
            self.dialog.txt_tag_search.tag_data = self.app.tag_data
        self.dialog.show(); self.dialog.raise_(); self.dialog.activateWindow()

def setup(app):
    if not hasattr(app, "loaded_plugins"): app.loaded_plugins = []
    app.loaded_plugins.append(AnnualSeasonalityPlugin(app))