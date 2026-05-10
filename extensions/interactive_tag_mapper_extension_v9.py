"""
Interactive Tag Mapper + improved Bubble Visualizer extension for Danbooru Dataset Finder.

v9 — Visual overhaul (Catppuccin Mocha theme, polished controls, category legend,
stats bar, clear-filters, keyboard shortcuts, edge-strength slider, zoom controls,
node search highlight) while keeping the original extension API and behavior.

Install:
    1. Copy this file into the app's ./extensions/ folder.
    2. Restart Nmain.py.
    3. Run a search, then click "Interactive Tag Mapper".

The extension uses the host app's extension API:
    - app.add_extension_button(button)
    - app.get_current_df()
    - app.data_updated signal
"""

from __future__ import annotations

import csv
import gc
import math
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Tuple

import polars as pl
from PyQt6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Theme (Catppuccin Mocha)
# ---------------------------------------------------------------------------

THEME = {
    "base":        "#1e1e2e",
    "mantle":      "#181825",
    "crust":       "#11111b",
    "surface0":    "#313244",
    "surface1":    "#45475a",
    "surface2":    "#585b70",
    "overlay0":    "#6c7086",
    "overlay1":    "#7f849c",
    "overlay2":    "#9399b2",
    "subtext0":    "#a6adc8",
    "subtext1":    "#bac2de",
    "text":        "#cdd6f4",
    "blue":        "#89b4fa",
    "lavender":    "#b4befe",
    "sapphire":    "#74c7ec",
    "sky":         "#89dceb",
    "teal":        "#94e2d5",
    "green":       "#a6e3a1",
    "yellow":      "#f9e2af",
    "peach":       "#fab387",
    "maroon":      "#eba0ac",
    "red":         "#f38ba8",
    "mauve":       "#cba6f7",
    "pink":        "#f5c2e7",
    "flamingo":    "#f2cdcd",
    "rosewater":   "#f5e0dc",
}


def _build_stylesheet() -> str:
    t = THEME
    return f"""
QDialog {{
    background-color: {t['base']};
    color: {t['text']};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}
QWidget {{
    color: {t['text']};
}}
QLabel {{
    color: {t['text']};
    background: transparent;
}}
QLabel#sectionHeader {{
    color: {t['subtext0']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 2px 0;
}}
QLabel#dialogTitle {{
    color: {t['text']};
    font-size: 18px;
    font-weight: 700;
    padding: 2px 0;
}}
QLabel#dialogSubtitle {{
    color: {t['subtext0']};
    font-size: 12px;
}}
QFrame#card {{
    background-color: {t['mantle']};
    border: 1px solid {t['surface0']};
    border-radius: 10px;
}}
QFrame#hLine {{
    background-color: {t['surface0']};
    max-height: 1px;
    border: none;
}}

/* Pill / badge labels */
QLabel#statusPill {{
    background-color: {t['surface0']};
    color: {t['green']};
    border: 1px solid {t['surface1']};
    border-radius: 10px;
    padding: 4px 12px;
    font-weight: 600;
}}
QLabel#statusPill[state="info"] {{ color: {t['blue']}; }}
QLabel#statusPill[state="warn"] {{ color: {t['peach']}; }}
QLabel#statusPill[state="error"] {{ color: {t['red']}; }}
QLabel#statusPill[state="busy"] {{ color: {t['yellow']}; }}
QLabel#statusPill[state="ok"] {{ color: {t['green']}; }}

QLabel#statChip {{
    background-color: {t['surface0']};
    color: {t['subtext1']};
    border-radius: 8px;
    padding: 6px 12px;
}}
QLabel#statChip b {{
    color: {t['text']};
}}

/* Inputs */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {t['surface0']};
    color: {t['text']};
    border: 1px solid {t['surface1']};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {t['blue']};
    selection-color: {t['crust']};
    min-height: 18px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {t['blue']};
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
    border-color: {t['surface2']};
}}
QLineEdit::placeholder {{
    color: {t['overlay1']};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {t['surface1']};
    border: none;
    width: 18px;
    border-radius: 3px;
    margin: 1px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {t['surface2']};
}}
QSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {t['text']};
    width: 0; height: 0;
}}
QSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t['text']};
    width: 0; height: 0;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t['text']};
    width: 0; height: 0;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['mantle']};
    color: {t['text']};
    border: 1px solid {t['surface1']};
    border-radius: 6px;
    selection-background-color: {t['surface1']};
    selection-color: {t['text']};
    outline: 0;
    padding: 4px;
}}

/* Buttons */
QPushButton {{
    background-color: {t['surface0']};
    color: {t['text']};
    border: 1px solid {t['surface1']};
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {t['surface1']};
    border-color: {t['surface2']};
}}
QPushButton:pressed {{
    background-color: {t['surface2']};
}}
QPushButton:disabled {{
    background-color: {t['mantle']};
    color: {t['overlay0']};
    border-color: {t['surface0']};
}}
QPushButton[variant="primary"] {{
    background-color: {t['blue']};
    color: {t['crust']};
    border: 1px solid {t['blue']};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {t['lavender']};
    border-color: {t['lavender']};
}}
QPushButton[variant="primary"]:pressed {{
    background-color: {t['sapphire']};
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {t['surface0']};
    color: {t['overlay0']};
    border-color: {t['surface0']};
}}
QPushButton[variant="success"] {{
    background-color: {t['green']};
    color: {t['crust']};
    border: 1px solid {t['green']};
    font-weight: 600;
}}
QPushButton[variant="success"]:hover {{
    background-color: {t['teal']};
    border-color: {t['teal']};
}}
QPushButton[variant="danger"] {{
    color: {t['red']};
    border-color: {t['surface1']};
}}
QPushButton[variant="danger"]:hover {{
    background-color: {t['surface1']};
    color: {t['maroon']};
}}
QPushButton[variant="ghost"] {{
    background-color: transparent;
    border-color: {t['surface1']};
    color: {t['subtext1']};
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {t['surface0']};
    color: {t['text']};
}}
QToolButton {{
    background-color: {t['surface0']};
    color: {t['text']};
    border: 1px solid {t['surface1']};
    border-radius: 6px;
    padding: 5px 8px;
    min-width: 22px;
}}
QToolButton:hover {{
    background-color: {t['surface1']};
}}
QToolButton:pressed {{
    background-color: {t['surface2']};
}}

/* Table */
QTableWidget {{
    background-color: {t['mantle']};
    alternate-background-color: {t['base']};
    color: {t['text']};
    border: 1px solid {t['surface0']};
    border-radius: 8px;
    gridline-color: {t['surface0']};
    selection-background-color: {t['surface1']};
    selection-color: {t['text']};
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {t['surface1']};
    color: {t['text']};
}}
QTableWidget::item:hover {{
    background-color: {t['surface0']};
}}
QHeaderView {{
    background-color: {t['mantle']};
    border: none;
}}
QHeaderView::section {{
    background-color: {t['mantle']};
    color: {t['subtext0']};
    border: none;
    border-bottom: 1px solid {t['surface1']};
    padding: 8px 10px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{
    background-color: {t['surface0']};
    color: {t['text']};
}}
QTableCornerButton::section {{
    background-color: {t['mantle']};
    border: none;
}}

/* Checkbox */
QCheckBox {{
    color: {t['text']};
    spacing: 8px;
    padding: 2px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {t['surface2']};
    border-radius: 4px;
    background-color: {t['surface0']};
}}
QCheckBox::indicator:hover {{
    border-color: {t['blue']};
}}
QCheckBox::indicator:checked {{
    background-color: {t['blue']};
    border-color: {t['blue']};
    image: none;
}}
QCheckBox::indicator:checked:hover {{
    background-color: {t['lavender']};
    border-color: {t['lavender']};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {t['surface0']};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background-color: {t['blue']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {t['text']};
    border: 2px solid {t['blue']};
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background-color: {t['lavender']};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {t['mantle']};
    width: 12px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['surface1']};
    min-height: 24px;
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['surface2']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    background: {t['mantle']};
    height: 12px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t['surface1']};
    min-width: 24px;
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t['surface2']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* Menus */
QMenu {{
    background-color: {t['mantle']};
    color: {t['text']};
    border: 1px solid {t['surface1']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {t['surface1']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {t['surface0']};
    margin: 4px 6px;
}}

/* Tooltips */
QToolTip {{
    background-color: {t['crust']};
    color: {t['text']};
    border: 1px solid {t['surface1']};
    border-radius: 4px;
    padding: 4px 8px;
}}
"""


# ---------------------------------------------------------------------------
# Domain types and shared data
# ---------------------------------------------------------------------------

TAG_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    ("tag_string_artist", "artist", "#f38ba8"),
    ("tag_string_copyright", "copyright", "#cba6f7"),
    ("tag_string_character", "character", "#a6e3a1"),
    ("tag_string_general", "general", "#89b4fa"),
    ("tag_string_meta", "meta", "#fab387"),
)

CATEGORY_COLOR: Dict[str, str] = {category: color for _, category, color in TAG_COLUMNS}
CATEGORY_COLOR["mixed"] = "#f9e2af"
CATEGORY_COLOR["unknown"] = "#cdd6f4"
CATEGORY_ORDER = ["artist", "copyright", "character", "general", "meta", "mixed", "unknown"]


class NumericItem(QTableWidgetItem):
    """Table item that sorts numbers numerically instead of lexicographically."""

    def __init__(self, value, display: Optional[str] = None):
        super().__init__(str(value if display is None else display))
        self._value = value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self._value < other._value
        return super().__lt__(other)


class TagRow:
    __slots__ = ("tag", "category", "count", "coverage")

    def __init__(self, tag: str, category: str, count: int, coverage: float):
        self.tag = tag
        self.category = category
        self.count = count
        self.coverage = coverage


class BubbleNodeData:
    __slots__ = ("tag", "category", "count", "coverage", "related")

    def __init__(self, tag: str, category: str, count: int, coverage: float, related: int = 0):
        self.tag = tag
        self.category = category
        self.count = count
        self.coverage = coverage
        self.related = related


class BubbleEdgeData:
    __slots__ = ("a", "b", "count", "strength")

    def __init__(self, a: str, b: str, count: int, strength: float):
        self.a = a
        self.b = b
        self.count = count
        self.strength = strength


# ---------------------------------------------------------------------------
# Small reusable UI helpers
# ---------------------------------------------------------------------------

def make_card(parent=None) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName("card")
    return frame


def make_section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionHeader")
    return label


def make_hline() -> QFrame:
    line = QFrame()
    line.setObjectName("hLine")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


def make_status_pill(text: str = "Ready", state: str = "ok") -> QLabel:
    label = QLabel(text)
    label.setObjectName("statusPill")
    label.setProperty("state", state)
    return label


def set_status(pill: QLabel, text: str, state: str = "ok"):
    pill.setText(text)
    pill.setProperty("state", state)
    # Force re-polish so the [state] selector takes effect.
    style = pill.style()
    style.unpolish(pill)
    style.polish(pill)


def make_stat_chip(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("statChip")
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


class CategoryLegend(QWidget):
    """Compact horizontal legend so users always know what category colors mean."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for category in CATEGORY_ORDER:
            color = CATEGORY_COLOR.get(category, "#cdd6f4")
            pill = QLabel(f"●  {category}")
            pill.setStyleSheet(
                f"color: {color}; font-weight: 600; "
                f"background: transparent; padding: 0;"
            )
            layout.addWidget(pill)
        layout.addStretch()


# ---------------------------------------------------------------------------
# Workers (unchanged logic from v8)
# ---------------------------------------------------------------------------

class TagMapWorker(QThread):
    finished = pyqtSignal(object, int)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, df: pl.DataFrame, selected_tag: str = "", top_n: int = 5000):
        super().__init__()
        self.df = df
        self.selected_tag = selected_tag.strip().lower()
        self.top_n = max(1, int(top_n))

    def run(self):
        try:
            total_posts = len(self.df) if self.df is not None else 0
            if self.df is None or total_posts == 0:
                self.finished.emit([], 0)
                return

            work_df = self._filtered_posts_for_related_tag(self.df, self.selected_tag)
            if len(work_df) == 0:
                self.finished.emit([], 0)
                return

            self.progress.emit("Counting tags with Polars...")
            rows = self._count_tags(work_df, total_posts=len(work_df), top_n=self.top_n)

            if self.selected_tag:
                rows = [row for row in rows if row.tag != self.selected_tag]

            self.finished.emit(rows, len(work_df))
            self.df = None
            gc.collect()
        except Exception as exc:  # pragma: no cover
            self.error.emit(str(exc))

    @staticmethod
    def _filtered_posts_for_related_tag(df: pl.DataFrame, tag: str) -> pl.DataFrame:
        if not tag:
            return df

        if "tag_string" in df.columns:
            tag_expr = pl.concat_str([pl.lit(" "), pl.col("tag_string").fill_null(""), pl.lit(" ")])
            return df.filter(tag_expr.str.contains(f" {tag} ", literal=True))

        available = [col for col, _, _ in TAG_COLUMNS if col in df.columns]
        if not available:
            return df.head(0)
        tag_expr = pl.concat_str([pl.lit(" ")] + [pl.col(c).fill_null("") + " " for c in available])
        return df.filter(tag_expr.str.contains(f" {tag} ", literal=True))

    @staticmethod
    def _count_tags(df: pl.DataFrame, total_posts: int, top_n: int) -> List[TagRow]:
        frames: List[pl.DataFrame] = []

        for col, category, _ in TAG_COLUMNS:
            if col not in df.columns:
                continue
            frame = (
                df.select(pl.col(col).fill_null("").str.split(" ").alias("tag"))
                .explode("tag")
                .filter(pl.col("tag") != "")
                .group_by("tag")
                .len()
                .rename({"len": "count"})
                .with_columns(pl.lit(category).alias("category"))
            )
            frames.append(frame)

        if not frames and "tag_string" in df.columns:
            frames.append(
                df.select(pl.col("tag_string").fill_null("").str.split(" ").alias("tag"))
                .explode("tag")
                .filter(pl.col("tag") != "")
                .group_by("tag")
                .len()
                .rename({"len": "count"})
                .with_columns(pl.lit("unknown").alias("category"))
            )

        if not frames:
            return []

        counted = pl.concat(frames, how="diagonal_relaxed")
        result = (
            counted.group_by("tag")
            .agg(
                pl.sum("count").alias("count"),
                pl.col("category").unique().alias("categories"),
            )
            .with_columns(
                pl.when(pl.col("categories").list.len() == 1)
                .then(pl.col("categories").list.first())
                .otherwise(pl.lit("mixed"))
                .alias("category")
            )
            .with_columns(((pl.col("count") / max(1, total_posts)) * 100).alias("coverage"))
            .sort("count", descending=True)
            .head(top_n)
            .select(["tag", "category", "count", "coverage"])
        )

        return [
            TagRow(
                tag=str(row["tag"]),
                category=str(row["category"]),
                count=int(row["count"]),
                coverage=float(row["coverage"]),
            )
            for row in result.iter_rows(named=True)
        ]


class BubbleMapWorker(QThread):
    finished = pyqtSignal(object, object, int, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        df: pl.DataFrame,
        focus_tag: str = "",
        max_nodes: int = 60,
        min_edge_count: int = 2,
        allowed_categories: Optional[set] = None,
    ):
        super().__init__()
        self.df = df
        self.focus_tag = focus_tag.strip().lower()
        self.max_nodes = max(6, int(max_nodes))
        self.min_edge_count = max(1, int(min_edge_count))
        self.allowed_categories = set(allowed_categories or CATEGORY_ORDER)

    def run(self):
        try:
            if self.df is None or len(self.df) == 0:
                self.finished.emit([], [], 0, self.focus_tag)
                return

            total_posts = len(self.df)
            self.progress.emit("Preparing bubble data...")
            all_rows = TagMapWorker._count_tags(self.df, total_posts=total_posts, top_n=max(8000, self.max_nodes * 40))
            all_rows = [r for r in all_rows if r.category in self.allowed_categories]
            if not all_rows:
                self.finished.emit([], [], total_posts, self.focus_tag)
                return

            by_tag = {row.tag: row for row in all_rows}

            work_df = self.df
            related_counts: Dict[str, int] = {}
            if self.focus_tag:
                work_df = TagMapWorker._filtered_posts_for_related_tag(self.df, self.focus_tag)
                if len(work_df) == 0:
                    self.finished.emit([], [], 0, self.focus_tag)
                    return
                self.progress.emit("Counting related tags...")
                related_rows = TagMapWorker._count_tags(work_df, total_posts=len(work_df), top_n=max(5000, self.max_nodes * 20))
                related_rows = [r for r in related_rows if r.category in self.allowed_categories]
                related_counts = {row.tag: row.count for row in related_rows}

                ordered_tags: List[str] = []
                if self.focus_tag in by_tag:
                    ordered_tags.append(self.focus_tag)
                ordered_tags.extend([row.tag for row in related_rows if row.tag != self.focus_tag][: self.max_nodes - len(ordered_tags)])
            else:
                ordered_tags = [row.tag for row in all_rows[: self.max_nodes]]

            ordered_tags = [tag for tag in ordered_tags if tag in by_tag]
            if not ordered_tags:
                self.finished.emit([], [], len(work_df), self.focus_tag)
                return

            node_set = set(ordered_tags)
            edge_source_df = work_df.select([c for c in ["tag_string"] + [col for col, _, _ in TAG_COLUMNS] if c in work_df.columns])
            self.progress.emit("Computing tag relationships...")
            edge_counts = self._count_edges(edge_source_df, node_set)

            nodes: List[BubbleNodeData] = []
            for tag in ordered_tags:
                row = by_tag[tag]
                nodes.append(
                    BubbleNodeData(
                        tag=tag,
                        category=row.category,
                        count=row.count,
                        coverage=row.coverage,
                        related=related_counts.get(tag, 0),
                    )
                )

            count_lookup = {n.tag: max(1, n.count) for n in nodes}
            edges: List[BubbleEdgeData] = []
            degree: Dict[str, int] = {tag: 0 for tag in node_set}
            for (a, b), count in edge_counts.items():
                if count < self.min_edge_count:
                    continue
                denom = float(min(count_lookup.get(a, 1), count_lookup.get(b, 1)))
                strength = count / max(1.0, denom)
                edges.append(BubbleEdgeData(a=a, b=b, count=count, strength=strength))
                degree[a] = degree.get(a, 0) + 1
                degree[b] = degree.get(b, 0) + 1

            edges.sort(key=lambda e: (e.count, e.strength), reverse=True)
            max_edges = max(self.max_nodes * 5, 80)
            edges = edges[:max_edges]

            if len(nodes) > self.max_nodes:
                nodes.sort(key=lambda n: (degree.get(n.tag, 0), n.related, n.count), reverse=True)
                nodes = nodes[: self.max_nodes]
                node_set = {n.tag for n in nodes}
                edges = [e for e in edges if e.a in node_set and e.b in node_set]

            self.finished.emit(nodes, edges, len(work_df), self.focus_tag)
            self.df = None
            gc.collect()
        except Exception as exc:  # pragma: no cover
            self.error.emit(str(exc))

    def _count_edges(self, df: pl.DataFrame, node_set: set) -> Dict[Tuple[str, str], int]:
        counts: Dict[Tuple[str, str], int] = {}
        if not node_set:
            return counts

        if "tag_string" in df.columns:
            iterable = df["tag_string"].fill_null("").to_list()
            for idx, tag_string in enumerate(iterable):
                if self.isInterruptionRequested():
                    break
                parts = [t for t in str(tag_string).split() if t in node_set]
                if len(parts) < 2:
                    continue
                uniq = sorted(set(parts))
                for a, b in combinations(uniq, 2):
                    counts[(a, b)] = counts.get((a, b), 0) + 1
                if idx and idx % 5000 == 0:
                    self.progress.emit(f"Computing tag relationships... {idx:,} posts scanned")
            return counts

        category_cols = [col for col, _, _ in TAG_COLUMNS if col in df.columns]
        if not category_cols:
            return counts

        row_iter = df.select(category_cols).iter_rows(named=True)
        for idx, row in enumerate(row_iter, start=1):
            if self.isInterruptionRequested():
                break
            active = set()
            for col in category_cols:
                value = row.get(col) or ""
                if value:
                    for tag in str(value).split():
                        if tag in node_set:
                            active.add(tag)
            if len(active) < 2:
                continue
            for a, b in combinations(sorted(active), 2):
                counts[(a, b)] = counts.get((a, b), 0) + 1
            if idx % 5000 == 0:
                self.progress.emit(f"Computing tag relationships... {idx:,} posts scanned")
        return counts


# ---------------------------------------------------------------------------
# Bubble graphics
# ---------------------------------------------------------------------------

class BubbleGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setStyleSheet(
            f"background-color: {THEME['crust']}; "
            f"border: 1px solid {THEME['surface0']}; "
            f"border-radius: 10px;"
        )

    def wheelEvent(self, event):
        factor = 1.18 if event.angleDelta().y() > 0 else 0.85
        self.scale(factor, factor)
        parent = self.parent()
        if parent is not None and hasattr(parent, "update_label_visibility_from_zoom"):
            parent.update_label_visibility_from_zoom()


class OutlinedTextItem(QGraphicsPathItem):
    """Small tag label with a readable outline/stroke."""

    def __init__(
        self,
        text: str,
        fill_color: QColor,
        outline_color: QColor,
        outline_width: float = 1.0,
        parent: Optional[QGraphicsItem] = None,
    ):
        super().__init__(parent)
        font = QFont("Segoe UI", 9)
        font.setBold(True)

        path = QPainterPath()
        path.addText(0.0, 0.0, font, text)
        bounds = path.boundingRect()

        normalized = QPainterPath()
        normalized.addPath(path)
        normalized.translate(-bounds.left(), -bounds.top())
        self.setPath(normalized)

        pen = QPen(outline_color, outline_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)
        self.setBrush(QBrush(fill_color))
        self.setZValue(6)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, False)


class BubbleNodeItem(QGraphicsEllipseItem):
    def __init__(
        self,
        dialog,
        node: BubbleNodeData,
        radius: float,
        label_mode: str,
        highlight: bool = False,
        selected: bool = False,
        connected: bool = False,
        label_visible: bool = True,
        dimmed: bool = False,
    ):
        super().__init__(-radius, -radius, radius * 2.0, radius * 2.0)
        self.dialog = dialog
        self.node = node
        color = QColor(CATEGORY_COLOR.get(node.category, "#cdd6f4"))
        if dimmed:
            color.setAlpha(50)
        else:
            color.setAlpha(220)
        self.setBrush(QBrush(color))

        if selected:
            pen = QPen(QColor("#f9e2af"), 5.0)
            self.setZValue(5)
        elif connected:
            pen = QPen(QColor("#a6e3a1"), 3.6)
            self.setZValue(4)
        elif highlight:
            pen = QPen(QColor("#f38ba8"), 3.0)
            self.setZValue(3)
        else:
            outline_color = QColor("#11111b")
            if dimmed:
                outline_color.setAlpha(80)
            pen = QPen(outline_color, 1.6)
            self.setZValue(2)
        self.setPen(pen)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._press_scene_pos: Optional[QPointF] = None

        self._label_item: Optional[OutlinedTextItem] = None
        if label_mode != "None":
            show_inside = radius >= 24
            text = node.tag if len(node.tag) <= 22 else (node.tag[:19] + "...")
            fill = QColor("#11111b" if show_inside else "#cdd6f4")
            outline = QColor("#cdd6f4" if show_inside else "#11111b")
            if dimmed:
                fill.setAlpha(120)
                outline.setAlpha(120)
            self._label_item = OutlinedTextItem(text, fill, outline, outline_width=(0.9 if show_inside else 1.2), parent=self)
            self._label_item.setZValue(7 if (selected or connected) else 6)
            self._label_item.setVisible(label_visible)
            rect = self._label_item.boundingRect()
            if show_inside:
                self._label_item.setPos(-rect.width() / 2.0, -rect.height() / 2.0)
            else:
                self._label_item.setPos(-rect.width() / 2.0, radius + 4.0)

        self.setToolTip(
            f"<b>{node.tag}</b><br>"
            f"<span style='color:{CATEGORY_COLOR.get(node.category, '#cdd6f4')}'>{node.category}</span><br>"
            f"Count: <b>{node.count:,}</b><br>"
            f"Coverage: <b>{node.coverage:.2f}%</b><br>"
            f"Related count: <b>{node.related:,}</b>"
        )

    def add_to_scene(self, scene: QGraphicsScene, pos: QPointF):
        self.setPos(pos)
        scene.addItem(self)

    def mousePressEvent(self, event):
        self._press_scene_pos = event.scenePos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        release_scene_pos = event.scenePos()
        press_scene_pos = self._press_scene_pos or release_scene_pos
        moved = (release_scene_pos - press_scene_pos).manhattanLength() > 4.0
        super().mouseReleaseEvent(event)
        self._press_scene_pos = None
        if not moved:
            tag = self.node.tag
            if event.button() == Qt.MouseButton.RightButton:
                global_pos = event.screenPos()
                QTimer.singleShot(0, lambda: self.dialog.show_node_context_menu(tag, global_pos))
            else:
                QTimer.singleShot(0, lambda: self.dialog.on_bubble_clicked(tag))

    def mouseDoubleClickEvent(self, event):
        event.accept()
        tag = self.node.tag
        QTimer.singleShot(0, lambda: self.dialog.on_bubble_double_clicked(tag))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.dialog is not None and hasattr(self.dialog, "update_edges_for_tag"):
                self.dialog.update_edges_for_tag(self.node.tag)
        return super().itemChange(change, value)


# ---------------------------------------------------------------------------
# Bubble Visualizer dialog
# ---------------------------------------------------------------------------

class BubbleVisualizerDialog(QDialog):
    def __init__(self, host_app, source_df: pl.DataFrame, suggested_focus: str = "", parent=None):
        super().__init__(parent or host_app)
        self.host_app = host_app
        self.source_df = source_df
        self.setWindowTitle("Bubble Visualizer")
        self.resize(1320, 920)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(_build_stylesheet())

        self._worker: Optional[BubbleMapWorker] = None
        self._nodes: List[BubbleNodeData] = []
        self._edges: List[BubbleEdgeData] = []
        self._focus_tag = suggested_focus.strip().lower()
        self._selected_tag = self._focus_tag
        self._node_label_items = []
        self._node_items: Dict[str, BubbleNodeItem] = {}
        self._edge_bindings: Dict[str, list] = {}
        self._node_positions: Dict[str, QPointF] = {}
        self._always_label_tags = set()
        self._node_search_term = ""
        self._edge_strength_threshold = 0  # 0–100 percent

        self._build_ui(suggested_focus)
        self._install_shortcuts()
        self.generate_map()

    def _build_ui(self, suggested_focus: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("🫧  Bubble Visualizer")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Bubble size = tag frequency · Lines = co-occurrence · "
            "Color: dim = weak, blue = medium, gold/pink = strong · "
            "Drag bubbles to rearrange"
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box, 1)

        self.status = make_status_pill("Ready", state="ok")
        header_row.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        root.addLayout(header_row)

        # Controls card
        controls_card = make_card()
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(10)

        controls_layout.addWidget(make_section_label("Map controls"))

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(QLabel("Focus tag:"))
        self.focus_edit = QLineEdit(suggested_focus)
        self.focus_edit.setPlaceholderText("Optional — leave blank for global map")
        self.focus_edit.returnPressed.connect(self.generate_map)
        top.addWidget(self.focus_edit, 5)

        top.addWidget(QLabel("Bubbles:"))
        self.node_spin = QSpinBox()
        self.node_spin.setRange(10, 300)
        self.node_spin.setSingleStep(10)
        self.node_spin.setValue(120)
        top.addWidget(self.node_spin)

        top.addWidget(QLabel("Min edge:"))
        self.edge_spin = QSpinBox()
        self.edge_spin.setRange(1, 1000)
        self.edge_spin.setValue(3)
        top.addWidget(self.edge_spin)

        top.addWidget(QLabel("Labels:"))
        self.label_combo = QComboBox()
        self.label_combo.addItems(["Major only", "All", "None"])
        self.label_combo.setCurrentText("Major only")
        self.label_combo.currentTextChanged.connect(lambda *_: self.update_label_visibility_from_zoom())
        top.addWidget(self.label_combo)

        top.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Structured (recommended)", "Force / organic"])
        self.layout_combo.setCurrentText("Structured (recommended)")
        top.addWidget(self.layout_combo)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setProperty("variant", "primary")
        self.generate_button.setShortcut(QKeySequence("Ctrl+Return"))
        self.generate_button.setToolTip("Rebuild map with current settings (Ctrl+Enter)")
        self.generate_button.clicked.connect(self.generate_map)
        top.addWidget(self.generate_button)

        controls_layout.addLayout(top)

        # Filter row: node search + edge strength slider
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        filter_row.addWidget(QLabel("🔍 Highlight:"))
        self.node_search = QLineEdit()
        self.node_search.setPlaceholderText("Highlight nodes containing... (Ctrl+F)")
        self.node_search.textChanged.connect(self._on_node_search_changed)
        filter_row.addWidget(self.node_search, 3)

        filter_row.addWidget(QLabel("Hide weak edges:"))
        self.edge_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_threshold_slider.setRange(0, 100)
        self.edge_threshold_slider.setValue(0)
        self.edge_threshold_slider.setToolTip("Hide edges below this strength %")
        self.edge_threshold_slider.valueChanged.connect(self._on_edge_threshold_changed)
        filter_row.addWidget(self.edge_threshold_slider, 2)

        self.edge_threshold_label = QLabel("0%")
        self.edge_threshold_label.setMinimumWidth(36)
        self.edge_threshold_label.setStyleSheet(f"color: {THEME['subtext0']};")
        filter_row.addWidget(self.edge_threshold_label)

        controls_layout.addLayout(filter_row)

        # Category row + buttons
        controls_layout.addWidget(make_section_label("Categories"))
        category_row = QGridLayout()
        category_row.setHorizontalSpacing(14)
        category_row.setVerticalSpacing(6)
        self.category_checks: Dict[str, QCheckBox] = {}
        for idx, category in enumerate(CATEGORY_ORDER):
            cb = QCheckBox(category.capitalize())
            cb.setChecked(category != "unknown")
            color = CATEGORY_COLOR.get(category, "#cdd6f4")
            cb.setStyleSheet(f"color: {color}; font-weight: 600;")
            self.category_checks[category] = cb
            category_row.addWidget(cb, idx // 4, idx % 4)
        controls_layout.addLayout(category_row)

        cat_buttons = QHBoxLayout()
        cat_buttons.setSpacing(8)
        self.btn_all_categories = QPushButton("Select All")
        self.btn_all_categories.setProperty("variant", "ghost")
        self.btn_all_categories.clicked.connect(self.select_all_categories)
        cat_buttons.addWidget(self.btn_all_categories)

        self.btn_no_categories = QPushButton("Clear All")
        self.btn_no_categories.setProperty("variant", "ghost")
        self.btn_no_categories.clicked.connect(self.clear_categories)
        cat_buttons.addWidget(self.btn_no_categories)
        cat_buttons.addStretch()
        controls_layout.addLayout(cat_buttons)

        root.addWidget(controls_card)

        # Graphics view with floating zoom controls
        view_container = QWidget()
        view_layout = QVBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor(THEME["crust"])))
        self.view = BubbleGraphicsView(self)
        self.view.setScene(self.scene)
        view_layout.addWidget(self.view, 1)

        # Floating zoom toolbar (overlay)
        self._zoom_toolbar = QFrame(self.view)
        self._zoom_toolbar.setStyleSheet(
            f"background-color: {THEME['mantle']}; "
            f"border: 1px solid {THEME['surface1']}; "
            f"border-radius: 8px;"
        )
        zoom_layout = QHBoxLayout(self._zoom_toolbar)
        zoom_layout.setContentsMargins(6, 4, 6, 4)
        zoom_layout.setSpacing(4)

        zoom_in = QToolButton()
        zoom_in.setText("＋")
        zoom_in.setToolTip("Zoom in (Ctrl+=)")
        zoom_in.clicked.connect(lambda: self._zoom(1.2))
        zoom_layout.addWidget(zoom_in)

        zoom_out = QToolButton()
        zoom_out.setText("－")
        zoom_out.setToolTip("Zoom out (Ctrl+-)")
        zoom_out.clicked.connect(lambda: self._zoom(0.83))
        zoom_layout.addWidget(zoom_out)

        zoom_reset = QToolButton()
        zoom_reset.setText("⤢")
        zoom_reset.setToolTip("Fit view (Ctrl+0)")
        zoom_reset.clicked.connect(self.fit_scene)
        zoom_layout.addWidget(zoom_reset)
        self._zoom_toolbar.adjustSize()
        # Position will be set in resizeEvent.

        root.addWidget(view_container, 1)

        # Bottom action row
        bottom_card = make_card()
        bottom_layout = QHBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(12, 8, 12, 8)
        bottom_layout.setSpacing(8)

        self.legend = CategoryLegend()
        bottom_layout.addWidget(self.legend, 1)

        self.fit_button = QPushButton("Fit View")
        self.fit_button.setProperty("variant", "ghost")
        self.fit_button.clicked.connect(self.fit_scene)
        bottom_layout.addWidget(self.fit_button)

        self.copy_button = QPushButton("Copy Tags")
        self.copy_button.setProperty("variant", "ghost")
        self.copy_button.setToolTip("Copy all visible bubble tags to clipboard")
        self.copy_button.clicked.connect(self.copy_visible_tags)
        bottom_layout.addWidget(self.copy_button)

        self.map_selected_button = QPushButton("Refocus on Selected")
        self.map_selected_button.setProperty("variant", "ghost")
        self.map_selected_button.clicked.connect(self.map_selected_bubble)
        bottom_layout.addWidget(self.map_selected_button)

        self.include_button = QPushButton("➕ Add to Include")
        self.include_button.setProperty("variant", "primary")
        self.include_button.clicked.connect(self.add_selected_to_include)
        bottom_layout.addWidget(self.include_button)

        root.addWidget(bottom_card)

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.node_search.setFocus())
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.fit_scene)
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self._zoom(1.2))
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self._zoom(1.2))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self._zoom(0.83))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_zoom_toolbar") and self._zoom_toolbar is not None:
            try:
                viewport = self.view.viewport()
                self._zoom_toolbar.adjustSize()
                tb = self._zoom_toolbar
                tb.move(viewport.width() - tb.width() - 12, 12)
            except RuntimeError:
                pass

    def _zoom(self, factor: float):
        self.view.scale(factor, factor)
        self.update_label_visibility_from_zoom()

    def select_all_categories(self):
        for cb in self.category_checks.values():
            cb.setChecked(True)

    def clear_categories(self):
        for cb in self.category_checks.values():
            cb.setChecked(False)

    def allowed_categories(self) -> set:
        return {category for category, cb in self.category_checks.items() if cb.isChecked()}

    def generate_map(self):
        if self.source_df is None or len(self.source_df) == 0:
            set_status(self.status, "Run a search first.", "warn")
            return

        allowed = self.allowed_categories()
        if not allowed:
            set_status(self.status, "Choose at least one category.", "warn")
            return

        focus = self.focus_edit.text().strip().lower()
        self._focus_tag = focus

        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(500)

        self.generate_button.setEnabled(False)
        set_status(self.status, "Building bubble visualizer…", "busy")
        self._worker = BubbleMapWorker(
            self.source_df,
            focus_tag=focus,
            max_nodes=self.node_spin.value(),
            min_edge_count=self.edge_spin.value(),
            allowed_categories=allowed,
        )
        self._worker.progress.connect(lambda msg: set_status(self.status, msg, "busy"))
        self._worker.finished.connect(self.on_worker_finished)
        self._worker.error.connect(self.on_worker_error)
        self._worker.start()

    def on_worker_finished(self, nodes, edges, post_count: int, focus_tag: str):
        self._nodes = list(nodes)
        self._edges = list(edges)
        self._focus_tag = focus_tag or ""
        self._selected_tag = self._focus_tag
        self._node_positions = {}
        self.render_graph()
        message = f"Rendered {len(self._nodes):,} bubbles · {len(self._edges):,} relationships · {post_count:,} posts"
        if self._focus_tag:
            message += f" · focus '{self._focus_tag}'"
        set_status(self.status, message, "ok")
        self.generate_button.setEnabled(True)

    def on_worker_error(self, message: str):
        set_status(self.status, f"Error: {message}", "error")
        self.generate_button.setEnabled(True)

    def _radius_range(self) -> Tuple[float, float]:
        n = max(1, len(self._nodes))
        if n <= 40:
            return 18.0, 56.0
        if n <= 120:
            return 14.0, 44.0
        return 10.0, 34.0

    def _radius_scale(self, count: int, min_count: int, max_count: int) -> float:
        min_r, max_r = self._radius_range()
        if max_count <= min_count:
            return (min_r + max_r) / 2.0
        normalized = (math.sqrt(count) - math.sqrt(min_count)) / max(0.0001, (math.sqrt(max_count) - math.sqrt(min_count)))
        return min_r + normalized * (max_r - min_r)

    def _category_angle_map(self, active_categories: List[str]) -> Dict[str, float]:
        if not active_categories:
            return {}
        preferred = {
            "artist": -2.35,
            "copyright": -1.05,
            "character": 0.25,
            "general": 1.55,
            "meta": 2.55,
            "mixed": -3.00,
            "unknown": -1.75,
        }
        if len(active_categories) == 1:
            return {active_categories[0]: 0.0}
        angle_map: Dict[str, float] = {}
        for idx, category in enumerate(active_categories):
            fallback = -math.pi + ((2.0 * math.pi * idx) / max(1, len(active_categories)))
            angle_map[category] = preferred.get(category, fallback)
        return angle_map

    def _resolve_overlaps(
        self,
        positions: Dict[str, List[float]],
        radii: Dict[str, float],
        fixed_tags: Optional[set] = None,
        iterations: int = 28,
    ) -> Dict[str, QPointF]:
        fixed_tags = set(fixed_tags or set())
        if not positions:
            return {}
        pos = {tag: [float(coords[0]), float(coords[1])] for tag, coords in positions.items()}
        tags = list(pos.keys())
        for _ in range(max(1, iterations)):
            moved = False
            for i, a in enumerate(tags):
                for b in tags[i + 1 :]:
                    dx = pos[b][0] - pos[a][0]
                    dy = pos[b][1] - pos[a][1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    min_sep = radii.get(a, 18.0) + radii.get(b, 18.0) + 10.0
                    if dist < min_sep:
                        overlap = (min_sep - dist) / 2.0
                        ux = dx / dist
                        uy = dy / dist
                        if a not in fixed_tags:
                            pos[a][0] -= ux * overlap
                            pos[a][1] -= uy * overlap
                        if b not in fixed_tags:
                            pos[b][0] += ux * overlap
                            pos[b][1] += uy * overlap
                        moved = True
            if not moved:
                break
        return {tag: QPointF(coords[0], coords[1]) for tag, coords in pos.items()}

    def _structured_layout(self, radii: Dict[str, float]) -> Dict[str, QPointF]:
        nodes = self._nodes
        n = len(nodes)
        if n == 0:
            return {}

        by_tag = {node.tag: node for node in nodes}
        degree: Dict[str, int] = {node.tag: 0 for node in nodes}
        edge_lookup: Dict[Tuple[str, str], BubbleEdgeData] = {}
        for edge in self._edges:
            key = tuple(sorted((edge.a, edge.b)))
            edge_lookup[key] = edge
            degree[edge.a] = degree.get(edge.a, 0) + 1
            degree[edge.b] = degree.get(edge.b, 0) + 1

        max_degree = max(degree.values(), default=1) or 1
        max_count = max((node.count for node in nodes), default=1) or 1

        active_categories = [category for category in CATEGORY_ORDER if any(node.category == category for node in nodes)]
        if not active_categories:
            active_categories = ["unknown"]
        category_angles = self._category_angle_map(active_categories)

        pos: Dict[str, List[float]] = {}
        fixed: set = set()
        center_tags: set = set()

        focus = self._focus_tag if self._focus_tag in by_tag else ""
        if focus:
            pos[focus] = [0.0, 0.0]
            fixed.add(focus)
            center_tags.add(focus)
        else:
            center_count = min(5, max(1, int(round(math.sqrt(max(1, n)) * 0.55))))
            anchors = sorted(nodes, key=lambda node: (degree.get(node.tag, 0), node.count), reverse=True)[:center_count]
            if len(anchors) == 1:
                pos[anchors[0].tag] = [0.0, 0.0]
                fixed.add(anchors[0].tag)
                center_tags.add(anchors[0].tag)
            else:
                anchor_radius = 82.0 + max(0, len(anchors) - 3) * 8.0
                for idx, node in enumerate(anchors):
                    angle = (-math.pi / 2.0) + ((2.0 * math.pi * idx) / max(1, len(anchors)))
                    pos[node.tag] = [math.cos(angle) * anchor_radius, math.sin(angle) * anchor_radius]
                    fixed.add(node.tag)
                    center_tags.add(node.tag)

        grouped: Dict[str, list] = {category: [] for category in active_categories}
        for node in nodes:
            if node.tag in center_tags:
                continue
            category = node.category if node.category in grouped else active_categories[0]
            direct_strength = 0.0
            direct_count = 0
            if focus:
                edge = edge_lookup.get(tuple(sorted((focus, node.tag))))
                if edge is not None:
                    direct_strength = float(edge.strength)
                    direct_count = int(edge.count)
            size_score = math.sqrt(max(1, node.count)) / math.sqrt(max(1, max_count))
            connectivity_score = degree.get(node.tag, 0) / max(1, max_degree)
            center_score = (size_score * 0.45) + (connectivity_score * 0.55)
            grouped.setdefault(category, []).append((node, direct_strength, direct_count, center_score))

        for category, items in grouped.items():
            if not items:
                continue
            angle_center = category_angles.get(category, 0.0)
            items.sort(key=lambda row: ((row[1] > 0.0), row[1], row[2], row[3], row[0].count), reverse=True)

            if focus:
                direct_items = [row for row in items if row[1] > 0.0]
                indirect_items = [row for row in items if row[1] <= 0.0]

                def place_bucket(bucket, start_radius: float, per_ring: int, layer_gap: float, use_direct_strength: bool):
                    total_bucket = len(bucket)
                    if total_bucket == 0:
                        return
                    for idx, row in enumerate(bucket):
                        node, direct_strength, direct_count, center_score = row
                        layer = idx // per_ring
                        slot = idx % per_ring
                        slots_in_layer = min(per_ring, total_bucket - (layer * per_ring))
                        angular_span = min(1.7, 0.55 + slots_in_layer * 0.09)
                        if slots_in_layer <= 1:
                            slot_offset = 0.0
                        else:
                            slot_offset = ((slot - ((slots_in_layer - 1) / 2.0)) * (angular_span / max(1.0, slots_in_layer - 1)))
                        radius_boost = (1.0 - max(0.0, min(1.0, direct_strength if use_direct_strength else center_score)))
                        radius = start_radius + (layer * layer_gap) + (radius_boost * (120.0 if use_direct_strength else 90.0))
                        angle = angle_center + slot_offset
                        pos[node.tag] = [math.cos(angle) * radius, math.sin(angle) * radius]

                place_bucket(direct_items, start_radius=150.0, per_ring=8, layer_gap=105.0, use_direct_strength=True)
                place_bucket(indirect_items, start_radius=430.0, per_ring=10, layer_gap=120.0, use_direct_strength=False)
            else:
                total_items = len(items)
                for idx, row in enumerate(items):
                    node, direct_strength, direct_count, center_score = row
                    per_ring = 10
                    layer = idx // per_ring
                    slot = idx % per_ring
                    slots_in_layer = min(per_ring, total_items - (layer * per_ring))
                    angular_span = min(1.8, 0.65 + slots_in_layer * 0.10)
                    if slots_in_layer <= 1:
                        slot_offset = 0.0
                    else:
                        slot_offset = ((slot - ((slots_in_layer - 1) / 2.0)) * (angular_span / max(1.0, slots_in_layer - 1)))
                    radius = 230.0 + (layer * 125.0) - (center_score * 95.0)
                    angle = angle_center + slot_offset
                    pos[node.tag] = [math.cos(angle) * radius, math.sin(angle) * radius]

        return self._resolve_overlaps(pos, radii, fixed_tags=fixed)

    def _compute_layout(self, radii: Dict[str, float]) -> Dict[str, QPointF]:
        layout_name = self.layout_combo.currentText() if hasattr(self, "layout_combo") else "Structured (recommended)"
        if layout_name.startswith("Force"):
            return self._force_layout(radii)
        return self._structured_layout(radii)

    def _force_layout(self, radii: Dict[str, float]) -> Dict[str, QPointF]:
        nodes = self._nodes
        edges = self._edges
        n = len(nodes)
        if n == 0:
            return {}

        pos: Dict[str, List[float]] = {}
        if self._focus_tag and any(node.tag == self._focus_tag for node in nodes):
            pos[self._focus_tag] = [0.0, 0.0]
            others = [node for node in nodes if node.tag != self._focus_tag]
            others.sort(key=lambda x: (x.related, x.count), reverse=True)
            total = max(1, len(others))
            for i, node in enumerate(others):
                angle = (2.0 * math.pi * i / total)
                distance = 260.0 + 28.0 * (i // 24)
                pos[node.tag] = [math.cos(angle) * distance, math.sin(angle) * distance]
        else:
            total = max(1, n)
            ordered = sorted(nodes, key=lambda x: x.count, reverse=True)
            for i, node in enumerate(ordered):
                angle = (2.0 * math.pi * i / total)
                distance = 120.0 + 16.0 * i
                pos[node.tag] = [math.cos(angle) * distance, math.sin(angle) * distance]

        edge_lookup = [(e.a, e.b, max(1.0, e.count), max(0.05, e.strength)) for e in edges]
        fixed = {self._focus_tag} if self._focus_tag and self._focus_tag in pos else set()

        area = 300000.0 + n * 2200.0
        k = math.sqrt(area / max(1, n))
        iterations = 110 if n <= 120 else 75
        temperature = 42.0 + min(25.0, n / 8.0)
        tags = [node.tag for node in nodes]

        for _ in range(iterations):
            disp = {tag: [0.0, 0.0] for tag in tags}

            for i, a in enumerate(tags):
                ax, ay = pos[a]
                ra = radii.get(a, 18.0)
                for b in tags[i + 1 :]:
                    bx, by = pos[b]
                    rb = radii.get(b, 18.0)
                    dx = ax - bx
                    dy = ay - by
                    dist_sq = dx * dx + dy * dy
                    if dist_sq < 0.01:
                        dx = 0.01
                        dy = 0.02
                        dist_sq = dx * dx + dy * dy
                    dist = math.sqrt(dist_sq)
                    min_sep = ra + rb + 18.0
                    repulse = (k * k) / dist
                    if dist < min_sep:
                        repulse += (min_sep - dist) * 2.4
                    fx = (dx / dist) * repulse
                    fy = (dy / dist) * repulse
                    disp[a][0] += fx
                    disp[a][1] += fy
                    disp[b][0] -= fx
                    disp[b][1] -= fy

            for a, b, edge_count, strength in edge_lookup:
                if a not in pos or b not in pos:
                    continue
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = max(1.0, math.sqrt(dx * dx + dy * dy))
                spring_target = radii.get(a, 18.0) + radii.get(b, 18.0) + (65.0 if self._focus_tag else 48.0)
                attract = ((dist - spring_target) * 0.08) * (1.0 + min(3.0, edge_count / 8.0))
                fx = (dx / dist) * attract
                fy = (dy / dist) * attract
                disp[a][0] -= fx
                disp[a][1] -= fy
                disp[b][0] += fx
                disp[b][1] += fy

            for tag in tags:
                x, y = pos[tag]
                center_pull = 0.0025 if tag not in fixed else 0.0
                disp[tag][0] += -x * center_pull
                disp[tag][1] += -y * center_pull

            for tag in tags:
                if tag in fixed:
                    pos[tag] = [0.0, 0.0]
                    continue
                dx, dy = disp[tag]
                length = math.sqrt(dx * dx + dy * dy)
                if length > 0:
                    scale = min(temperature, length) / length
                    pos[tag][0] += dx * scale
                    pos[tag][1] += dy * scale
            temperature *= 0.94

        for _ in range(10):
            moved = False
            for i, a in enumerate(tags):
                for b in tags[i + 1 :]:
                    dx = pos[b][0] - pos[a][0]
                    dy = pos[b][1] - pos[a][1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    min_sep = radii.get(a, 18.0) + radii.get(b, 18.0) + 8.0
                    if dist < min_sep:
                        overlap = (min_sep - dist) / 2.0
                        ux = dx / dist
                        uy = dy / dist
                        if a not in fixed:
                            pos[a][0] -= ux * overlap
                            pos[a][1] -= uy * overlap
                        if b not in fixed:
                            pos[b][0] += ux * overlap
                            pos[b][1] += uy * overlap
                        moved = True
            if not moved:
                break

        return {tag: QPointF(coords[0], coords[1]) for tag, coords in pos.items()}

    def _labels_to_show(self, radii: Dict[str, float]) -> set:
        mode = self.label_combo.currentText()
        if mode == "None":
            return set()
        if mode == "All":
            return {node.tag for node in self._nodes}

        important = set()
        if self._focus_tag:
            important.add(self._focus_tag)
        ranked = sorted(self._nodes, key=lambda n: (n.related, n.count), reverse=True)
        important.update(node.tag for node in ranked[: min(25, max(10, len(ranked) // 5))])
        important.update(tag for tag, radius in radii.items() if radius >= 24.0)
        return important

    def _interpolate_color(self, start_hex: str, end_hex: str, t: float) -> QColor:
        t = max(0.0, min(1.0, float(t)))
        start = QColor(start_hex)
        end = QColor(end_hex)
        r = int(start.red() + (end.red() - start.red()) * t)
        g = int(start.green() + (end.green() - start.green()) * t)
        b = int(start.blue() + (end.blue() - start.blue()) * t)
        return QColor(r, g, b)

    def _edge_visual_style(
        self,
        edge: BubbleEdgeData,
        min_edge: int,
        max_edge: int,
        selected: bool = False,
        dimmed: bool = False,
    ) -> Tuple[QColor, float]:
        if max_edge > min_edge:
            count_norm = (edge.count - min_edge) / max(1.0, float(max_edge - min_edge))
        else:
            count_norm = 1.0
        strength_norm = max(0.0, min(1.0, float(edge.strength)))
        score = max(0.0, min(1.0, (count_norm * 0.55) + (strength_norm * 0.45)))

        if score < 0.5:
            color = self._interpolate_color("#585b70", "#89b4fa", score / 0.5)
        else:
            color = self._interpolate_color("#89b4fa", "#f9e2af", (score - 0.5) / 0.5)

        if strength_norm >= 0.75:
            color = self._interpolate_color(color.name(), "#f38ba8", (strength_norm - 0.75) / 0.25)

        width = 0.8 + (score * 5.0)
        alpha = 75 + int(score * 170)

        if selected:
            color = self._interpolate_color(color.name(), "#a6e3a1", 0.55)
            width += 2.4
            alpha = min(255, alpha + 70)

        if dimmed:
            alpha = min(alpha, 35)
            width = max(0.4, width * 0.6)

        color.setAlpha(max(20, min(255, alpha)))
        return color, width

    def update_label_visibility_from_zoom(self):
        mode = self.label_combo.currentText() if hasattr(self, "label_combo") else "Major only"
        zoom = self.view.transform().m11() if hasattr(self, "view") else 1.0
        show_all_when_zoomed = zoom >= 1.55
        for tag, label_item in getattr(self, "_node_label_items", []):
            if label_item is None:
                continue
            if mode == "None":
                label_item.setVisible(False)
            elif mode == "All":
                label_item.setVisible(True)
            else:
                label_item.setVisible(tag in self._always_label_tags or show_all_when_zoomed)

    def _on_node_search_changed(self, text: str):
        self._node_search_term = text.strip().lower()
        self.render_graph(preserve_view=True)

    def _on_edge_threshold_changed(self, value: int):
        self._edge_strength_threshold = int(value)
        self.edge_threshold_label.setText(f"{value}%")
        self.render_graph(preserve_view=True)

    def _node_matches_search(self, tag: str) -> bool:
        if not self._node_search_term:
            return True
        return self._node_search_term in tag.lower()

    def render_graph(self, preserve_view: bool = False):
        old_transform = None
        old_center = None
        if preserve_view and hasattr(self, "view") and self.view is not None:
            old_transform = self.view.transform()
            viewport_rect = self.view.viewport().rect()
            old_center = self.view.mapToScene(viewport_rect.center())

        for saved_tag, saved_item in getattr(self, "_node_items", {}).items():
            try:
                self._node_positions[saved_tag] = QPointF(saved_item.pos())
            except RuntimeError:
                pass

        self.scene.clear()
        self._node_items = {}
        self._edge_bindings = {}
        if not self._nodes:
            placeholder = self.scene.addText("No tags to display for the chosen filters.")
            placeholder.setDefaultTextColor(QColor(THEME["subtext0"]))
            if not preserve_view:
                self.view.resetTransform()
            return

        max_count = max(node.count for node in self._nodes)
        min_count = min(node.count for node in self._nodes)
        radii = {node.tag: self._radius_scale(node.count, min_count, max_count) for node in self._nodes}
        positions = self._compute_layout(radii)
        for saved_tag, saved_pos in getattr(self, "_node_positions", {}).items():
            if saved_tag in positions:
                positions[saved_tag] = QPointF(saved_pos)
        labels_to_show = self._labels_to_show(radii)

        max_edge = max([edge.count for edge in self._edges], default=1)
        min_edge = min([edge.count for edge in self._edges], default=1)
        selected_neighbors = set()
        if self._selected_tag:
            for edge in self._edges:
                if edge.a == self._selected_tag:
                    selected_neighbors.add(edge.b)
                elif edge.b == self._selected_tag:
                    selected_neighbors.add(edge.a)

        # Compute search-matched tags and their direct neighbors so search can
        # dim the rest of the graph instead of hiding it (preserves layout).
        search_active = bool(self._node_search_term)
        match_tags: set = set()
        match_neighbors: set = set()
        if search_active:
            match_tags = {n.tag for n in self._nodes if self._node_matches_search(n.tag)}
            for edge in self._edges:
                if edge.a in match_tags:
                    match_neighbors.add(edge.b)
                if edge.b in match_tags:
                    match_neighbors.add(edge.a)

        threshold = self._edge_strength_threshold / 100.0

        for edge in self._edges:
            if edge.a not in positions or edge.b not in positions:
                continue
            if edge.strength < threshold:
                continue
            p1 = positions[edge.a]
            p2 = positions[edge.b]
            selected_edge = bool(self._selected_tag and (edge.a == self._selected_tag or edge.b == self._selected_tag))
            edge_dimmed = False
            if search_active:
                edge_dimmed = not (
                    edge.a in match_tags or edge.b in match_tags
                    or (edge.a in match_neighbors and edge.b in match_neighbors)
                )
            color, width = self._edge_visual_style(edge, min_edge, max_edge, selected=selected_edge, dimmed=edge_dimmed)
            line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
            line.setPen(QPen(color, width))
            line.setZValue(1)
            line.setToolTip(
                f"<b>{edge.a}</b> ↔ <b>{edge.b}</b><br>"
                f"Co-occurrence: <b>{edge.count:,}</b> posts<br>"
                f"Strength: <b>{edge.strength:.1%}</b> of the smaller tag"
            )
            line._edge_a = edge.a
            line._edge_b = edge.b
            self._edge_bindings.setdefault(edge.a, []).append(line)
            self._edge_bindings.setdefault(edge.b, []).append(line)
            self.scene.addItem(line)

        self._always_label_tags = set(labels_to_show)
        if self._selected_tag:
            self._always_label_tags.add(self._selected_tag)
            self._always_label_tags.update(selected_neighbors)
        if search_active:
            self._always_label_tags.update(match_tags)
        self._node_label_items = []

        label_setting = self.label_combo.currentText()
        for node in self._nodes:
            selected = node.tag == self._selected_tag
            connected = bool(self._selected_tag and node.tag in selected_neighbors)
            highlight = selected or connected or node.tag == self._focus_tag
            label_mode = "None" if label_setting == "None" else "All"
            label_visible = label_setting == "All" or node.tag in self._always_label_tags
            node_dimmed = bool(search_active and node.tag not in match_tags and node.tag not in match_neighbors)
            item = BubbleNodeItem(
                self,
                node,
                radii[node.tag],
                label_mode=label_mode,
                highlight=highlight,
                selected=selected,
                connected=connected,
                label_visible=label_visible,
                dimmed=node_dimmed,
            )
            item.add_to_scene(self.scene, positions.get(node.tag, QPointF(0.0, 0.0)))
            self._node_items[node.tag] = item
            self._node_positions[node.tag] = QPointF(item.pos())
            if item._label_item is not None:
                self._node_label_items.append((node.tag, item._label_item))

        self.update_label_visibility_from_zoom()

        rect = self.scene.itemsBoundingRect().adjusted(-120, -120, 120, 120)
        if rect.isNull():
            rect = QRectF(-400, -300, 800, 600)
        self.scene.setSceneRect(rect)
        if preserve_view and old_transform is not None:
            self.view.setTransform(old_transform)
            if old_center is not None:
                self.view.centerOn(old_center)
            self.update_label_visibility_from_zoom()
        else:
            self.fit_scene()

    def update_edges_for_tag(self, tag: str):
        item = getattr(self, "_node_items", {}).get(tag)
        if item is None:
            return
        try:
            p = item.pos()
        except RuntimeError:
            return
        self._node_positions[tag] = QPointF(p)

        for line in getattr(self, "_edge_bindings", {}).get(tag, []):
            try:
                edge_a = getattr(line, "_edge_a", None)
                edge_b = getattr(line, "_edge_b", None)
                item_a = getattr(self, "_node_items", {}).get(edge_a)
                item_b = getattr(self, "_node_items", {}).get(edge_b)
                if item_a is None or item_b is None:
                    continue
                pa = item_a.pos()
                pb = item_b.pos()
                line.setLine(pa.x(), pa.y(), pb.x(), pb.y())
            except RuntimeError:
                continue

    def fit_scene(self):
        rect = self.scene.sceneRect()
        if not rect.isNull():
            self.view.resetTransform()
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.update_label_visibility_from_zoom()

    def on_bubble_clicked(self, tag: str):
        self._selected_tag = tag
        self.focus_edit.setText(tag)
        set_status(self.status, f"Selected: {tag}", "info")
        self.render_graph(preserve_view=True)

    def on_bubble_double_clicked(self, tag: str):
        self._selected_tag = tag
        self.add_selected_to_include()

    def show_node_context_menu(self, tag: str, global_pos):
        menu = QMenu(self)
        include_action = QAction("➕  Add to Include", self)
        exclude_action = QAction("➖  Add to Exclude", self)
        focus_action = QAction("🎯  Refocus map on this", self)
        copy_action = QAction("📋  Copy tag", self)
        menu.addAction(include_action)
        menu.addAction(exclude_action)
        menu.addSeparator()
        menu.addAction(focus_action)
        menu.addSeparator()
        menu.addAction(copy_action)

        action = menu.exec(global_pos)
        if action == include_action:
            self._selected_tag = tag
            self.add_selected_to_include()
        elif action == exclude_action:
            if hasattr(self.host_app, "add_tag_to_exclude"):
                self.host_app.add_tag_to_exclude(tag)
                set_status(self.status, f"Added '{tag}' to Exclude", "ok")
        elif action == focus_action:
            self.focus_edit.setText(tag)
            self._focus_tag = tag
            self.generate_map()
        elif action == copy_action:
            QApplication.clipboard().setText(tag)
            set_status(self.status, f"Copied '{tag}'", "info")

    def add_selected_to_include(self):
        tag = self._selected_tag or self.focus_edit.text().strip()
        if tag and hasattr(self.host_app, "add_tag_to_include"):
            self.host_app.add_tag_to_include(tag)
            set_status(self.status, f"Added '{tag}' to Include", "ok")

    def map_selected_bubble(self):
        tag = self._selected_tag or self.focus_edit.text().strip()
        if not tag:
            set_status(self.status, "Select a bubble or type a focus tag.", "warn")
            return
        self.focus_edit.setText(tag)
        self.generate_map()

    def copy_visible_tags(self):
        tags = [node.tag for node in self._nodes]
        QApplication.clipboard().setText(", ".join(tags))
        set_status(self.status, f"Copied {len(tags):,} bubble tags", "info")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(700)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Interactive Tag Mapper dialog
# ---------------------------------------------------------------------------

class InteractiveTagMapperDialog(QDialog):
    def __init__(self, host_app, parent=None):
        super().__init__(parent or host_app)
        self.host_app = host_app
        self.setWindowTitle("Interactive Tag Mapper")
        self.resize(1080, 780)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(_build_stylesheet())

        self._all_rows: List[TagRow] = []
        self._visible_rows: List[TagRow] = []
        self._post_count = 0
        self._selected_related_tag = ""
        self._worker: Optional[TagMapWorker] = None
        self._bubble_dialog: Optional[BubbleVisualizerDialog] = None

        self._is_closing = False
        self._host_update_signal = None
        self._host_update_slot = None

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self.apply_client_filter)

        self._build_ui()
        self._install_shortcuts()
        self._wire_host_updates()
        self.refresh_from_host()

    # ----- UI construction -----
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("🧭  Interactive Tag Mapper")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Click a row to inspect related tags · double-click adds to Include · right-click for more"
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_row.addLayout(title_box, 1)

        self.status = make_status_pill("Ready", state="ok")
        header_row.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        root.addLayout(header_row)

        # Stats card
        stats_card = make_card()
        stats_layout = QHBoxLayout(stats_card)
        stats_layout.setContentsMargins(12, 10, 12, 10)
        stats_layout.setSpacing(10)

        self.chip_posts = make_stat_chip("📦 Posts: <b>—</b>")
        self.chip_total_tags = make_stat_chip("🏷  Tags: <b>—</b>")
        self.chip_visible = make_stat_chip("👁  Visible: <b>—</b>")
        self.chip_top_cat = make_stat_chip("🥇 Top: <b>—</b>")
        for chip in (self.chip_posts, self.chip_total_tags, self.chip_visible, self.chip_top_cat):
            stats_layout.addWidget(chip)
        stats_layout.addStretch()
        root.addWidget(stats_card)

        # Filters card
        filters_card = make_card()
        filters_layout = QVBoxLayout(filters_card)
        filters_layout.setContentsMargins(14, 12, 14, 12)
        filters_layout.setSpacing(10)
        filters_layout.addWidget(make_section_label("Filters"))

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Filter tags… e.g. hair, miku, rating  (Ctrl+F)")
        self.search_box.textChanged.connect(lambda: self._filter_timer.start(120))
        controls.addWidget(self.search_box, 4)

        controls.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(["All", "artist", "copyright", "character", "general", "meta", "mixed", "unknown"])
        self.category_combo.currentTextChanged.connect(self.apply_client_filter)
        controls.addWidget(self.category_combo, 1)

        controls.addWidget(QLabel("Min count:"))
        self.min_count = QSpinBox()
        self.min_count.setRange(1, 10_000_000)
        self.min_count.setValue(1)
        self.min_count.valueChanged.connect(self.apply_client_filter)
        controls.addWidget(self.min_count, 1)

        controls.addWidget(QLabel("Top:"))
        self.top_n = QSpinBox()
        self.top_n.setRange(100, 250_000)
        self.top_n.setSingleStep(500)
        self.top_n.setValue(5000)
        controls.addWidget(self.top_n, 1)

        self.only_related = QCheckBox("Related to selected")
        self.only_related.setToolTip("Re-count tags only in posts containing the selected tag.")
        controls.addWidget(self.only_related)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("variant", "primary")
        self.refresh_button.setToolTip("Re-run the tag map (F5)")
        self.refresh_button.clicked.connect(self.refresh_from_host)
        controls.addWidget(self.refresh_button)

        self.clear_filters_button = QPushButton("Clear")
        self.clear_filters_button.setProperty("variant", "ghost")
        self.clear_filters_button.setToolTip("Reset filters")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        controls.addWidget(self.clear_filters_button)

        filters_layout.addLayout(controls)

        # Category legend always visible to decode color cells
        legend_row = QHBoxLayout()
        legend_label = QLabel("Legend:")
        legend_label.setStyleSheet(f"color: {THEME['subtext0']};")
        legend_row.addWidget(legend_label)
        legend_row.addWidget(CategoryLegend(), 1)
        filters_layout.addLayout(legend_row)

        root.addWidget(filters_card)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tag", "Category", "Count", "Coverage"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemClicked.connect(self.on_item_clicked)
        self.table.itemDoubleClicked.connect(self.add_selected_to_include)
        self.table.setColumnWidth(0, 420)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 110)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        # Action row
        actions_card = make_card()
        actions = QHBoxLayout(actions_card)
        actions.setContentsMargins(12, 10, 12, 10)
        actions.setSpacing(8)

        self.copy_button = QPushButton("📋  Copy Visible")
        self.copy_button.setProperty("variant", "ghost")
        self.copy_button.clicked.connect(self.copy_visible_tags)
        actions.addWidget(self.copy_button)

        self.export_button = QPushButton("⬇  Export CSV")
        self.export_button.setProperty("variant", "ghost")
        self.export_button.clicked.connect(self.export_csv)
        actions.addWidget(self.export_button)

        actions.addStretch()

        self.related_button = QPushButton("🧭  Map Related")
        self.related_button.setProperty("variant", "ghost")
        self.related_button.setToolTip("Re-count tags within posts containing the selected tag")
        self.related_button.clicked.connect(self.map_related_to_selected)
        actions.addWidget(self.related_button)

        self.bubble_button = QPushButton("🫧  Bubble Visualizer")
        self.bubble_button.setProperty("variant", "ghost")
        self.bubble_button.clicked.connect(self.open_bubble_visualizer)
        actions.addWidget(self.bubble_button)

        self.reset_button = QPushButton("Reset to All")
        self.reset_button.setProperty("variant", "ghost")
        self.reset_button.clicked.connect(self.reset_related_filter)
        actions.addWidget(self.reset_button)

        self.exclude_button = QPushButton("➖  Exclude")
        self.exclude_button.setProperty("variant", "danger")
        self.exclude_button.clicked.connect(self.add_selected_to_exclude)
        actions.addWidget(self.exclude_button)

        self.include_button = QPushButton("➕  Include")
        self.include_button.setProperty("variant", "primary")
        self.include_button.setToolTip("Add the selected tag to Include (Enter)")
        self.include_button.clicked.connect(self.add_selected_to_include)
        actions.addWidget(self.include_button)

        root.addWidget(actions_card)

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.search_box.setFocus())
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_from_host)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_csv)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.open_bubble_visualizer)
        QShortcut(QKeySequence("Return"), self.table, activated=self.add_selected_to_include)
        QShortcut(QKeySequence("Enter"), self.table, activated=self.add_selected_to_include)
        QShortcut(QKeySequence("Delete"), self.table, activated=self.add_selected_to_exclude)

    def clear_filters(self):
        self.search_box.clear()
        self.category_combo.setCurrentText("All")
        self.min_count.setValue(1)
        self.apply_client_filter()

    # ----- Host wiring (unchanged) -----
    def _wire_host_updates(self):
        signal = getattr(self.host_app, "data_updated", None)
        if signal is None:
            return
        self._host_update_signal = signal
        self._host_update_slot = self._on_host_data_updated
        try:
            signal.connect(self._host_update_slot)
        except Exception:
            self._host_update_signal = None
            self._host_update_slot = None

    def _disconnect_host_updates(self):
        signal = getattr(self, "_host_update_signal", None)
        slot = getattr(self, "_host_update_slot", None)
        if signal is not None and slot is not None:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._host_update_signal = None
        self._host_update_slot = None

    def _qt_object_alive(self) -> bool:
        try:
            self.isVisible()
            return True
        except RuntimeError:
            return False

    def _on_host_data_updated(self, _df=None):
        if self._is_closing or not self._qt_object_alive():
            return
        self.refresh_from_host()

    def _disconnect_worker_signals(self, worker):
        if worker is None:
            return
        for signal, slot in (
            (worker.progress, self._on_worker_progress),
            (worker.finished, self.on_worker_finished),
            (worker.error, self.on_worker_error),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

    def _stop_worker(self, wait_ms: int = 700):
        worker = self._worker
        if worker is None:
            return
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(wait_ms)
        self._disconnect_worker_signals(worker)
        self._worker = None

    def _source_df(self) -> Optional[pl.DataFrame]:
        getter = getattr(self.host_app, "get_current_df", None)
        if getter is None:
            return None
        df = getter()
        if df is None or len(df) == 0:
            return None

        wanted = ["tag_string"] + [col for col, _, _ in TAG_COLUMNS]
        available = [col for col in wanted if col in df.columns]
        if not available:
            return None
        return df.select(available)

    def refresh_from_host(self):
        if self._is_closing or not self._qt_object_alive():
            return

        df = self._source_df()
        if df is None:
            self._all_rows = []
            self._visible_rows = []
            self.render_table([])
            self._update_stats()
            set_status(self.status, "Run a search first, then refresh.", "warn")
            return

        try:
            keep_related = self.only_related.isChecked()
        except RuntimeError:
            return

        self._selected_related_tag = self._selected_related_tag if keep_related else ""
        self.start_worker(df, selected_tag=self._selected_related_tag)

    def start_worker(self, df: pl.DataFrame, selected_tag: str = ""):
        if self._is_closing or not self._qt_object_alive():
            return

        self._stop_worker(wait_ms=500)

        self.refresh_button.setEnabled(False)
        self.related_button.setEnabled(False)
        self.bubble_button.setEnabled(False)
        set_status(self.status, "Building tag map…", "busy")

        self._worker = TagMapWorker(df, selected_tag=selected_tag, top_n=self.top_n.value())
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self.on_worker_finished)
        self._worker.error.connect(self.on_worker_error)
        self._worker.start()

    def _on_worker_progress(self, msg: str):
        set_status(self.status, msg, "busy")

    def on_worker_finished(self, rows: List[TagRow], post_count: int):
        self._all_rows = rows
        self._post_count = post_count
        label = f"Mapped {len(rows):,} tags · {post_count:,} posts"
        if self._selected_related_tag:
            label += f" · related to '{self._selected_related_tag}'"
        set_status(self.status, label, "ok")
        self.refresh_button.setEnabled(True)
        self.related_button.setEnabled(True)
        self.bubble_button.setEnabled(True)
        self.apply_client_filter()

    def on_worker_error(self, message: str):
        set_status(self.status, f"Mapper error: {message}", "error")
        self.refresh_button.setEnabled(True)
        self.related_button.setEnabled(True)
        self.bubble_button.setEnabled(True)

    def apply_client_filter(self):
        text = self.search_box.text().strip().lower()
        category = self.category_combo.currentText()
        min_count = self.min_count.value()

        rows = self._all_rows
        if text:
            rows = [row for row in rows if text in row.tag]
        if category != "All":
            rows = [row for row in rows if row.category == category]
        if min_count > 1:
            rows = [row for row in rows if row.count >= min_count]

        self._visible_rows = rows
        self.render_table(rows)
        self._update_stats()

    def _update_stats(self):
        # Posts
        if self._post_count:
            self.chip_posts.setText(f"📦 Posts: <b>{self._post_count:,}</b>")
        else:
            self.chip_posts.setText("📦 Posts: <b>—</b>")
        # Total tags
        self.chip_total_tags.setText(f"🏷  Tags: <b>{len(self._all_rows):,}</b>")
        # Visible
        self.chip_visible.setText(f"👁  Visible: <b>{len(self._visible_rows):,}</b>")
        # Top category among visible
        if self._visible_rows:
            counts: Dict[str, int] = {}
            for r in self._visible_rows:
                counts[r.category] = counts.get(r.category, 0) + 1
            top_cat, top_n = max(counts.items(), key=lambda kv: kv[1])
            color = CATEGORY_COLOR.get(top_cat, "#cdd6f4")
            self.chip_top_cat.setText(
                f"🥇 Top: <b><span style='color:{color}'>{top_cat}</span></b> ({top_n:,})"
            )
        else:
            self.chip_top_cat.setText("🥇 Top: <b>—</b>")

    def render_table(self, rows: Iterable[TagRow]):
        rows = list(rows)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for idx, row in enumerate(rows):
            tag_item = QTableWidgetItem(row.tag)
            tag_item.setData(Qt.ItemDataRole.UserRole, row.tag)

            # Category cell as a colored "pill" (text uses category color, with a dot prefix)
            color = CATEGORY_COLOR.get(row.category, "#cdd6f4")
            category_item = QTableWidgetItem(f"●  {row.category}")
            category_item.setForeground(QColor(color))
            font = category_item.font()
            font.setBold(True)
            category_item.setFont(font)

            count_item = NumericItem(row.count, f"{row.count:,}")
            coverage_item = NumericItem(row.coverage, f"{row.coverage:.2f}%")
            # Soft color for coverage: teal-ish for higher values
            cov = max(0.0, min(1.0, row.coverage / 100.0))
            cov_color = QColor(THEME["text"])
            if cov >= 0.5:
                cov_color = QColor(THEME["green"])
            elif cov >= 0.1:
                cov_color = QColor(THEME["sky"])
            else:
                cov_color = QColor(THEME["subtext1"])
            coverage_item.setForeground(cov_color)

            self.table.setItem(idx, 0, tag_item)
            self.table.setItem(idx, 1, category_item)
            self.table.setItem(idx, 2, count_item)
            self.table.setItem(idx, 3, coverage_item)

        self.table.setSortingEnabled(True)

    def selected_tag(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def on_item_clicked(self, _item):
        if self.only_related.isChecked():
            self._selected_related_tag = self.selected_tag()

    def map_related_to_selected(self):
        tag = self.selected_tag()
        if not tag:
            set_status(self.status, "Select a tag first.", "warn")
            return
        df = self._source_df()
        if df is None:
            set_status(self.status, "No current result set is available.", "warn")
            return
        self._selected_related_tag = tag
        self.only_related.setChecked(True)
        self.start_worker(df, selected_tag=tag)

    def _bubble_dialog_is_alive(self) -> bool:
        if self._bubble_dialog is None:
            return False
        try:
            self._bubble_dialog.isVisible()
            return True
        except RuntimeError:
            self._bubble_dialog = None
            return False

    def _on_bubble_dialog_destroyed(self, *_args):
        self._bubble_dialog = None

    def open_bubble_visualizer(self):
        df = self._source_df()
        if df is None:
            set_status(self.status, "No current result set is available.", "warn")
            return
        suggested_focus = self.selected_tag() or self._selected_related_tag
        if not self._bubble_dialog_is_alive() or not self._bubble_dialog.isVisible():
            self._bubble_dialog = BubbleVisualizerDialog(self.host_app, df, suggested_focus=suggested_focus, parent=self)
            self._bubble_dialog.destroyed.connect(self._on_bubble_dialog_destroyed)
        else:
            self._bubble_dialog.source_df = df
            if suggested_focus:
                self._bubble_dialog.focus_edit.setText(suggested_focus)
            self._bubble_dialog.generate_map()
        self._bubble_dialog.show()
        self._bubble_dialog.raise_()
        self._bubble_dialog.activateWindow()

    def reset_related_filter(self):
        df = self._source_df()
        self._selected_related_tag = ""
        self.only_related.setChecked(False)
        if df is not None:
            self.start_worker(df, selected_tag="")

    def add_selected_to_include(self, *_args):
        tag = self.selected_tag()
        if tag and hasattr(self.host_app, "add_tag_to_include"):
            self.host_app.add_tag_to_include(tag)
            set_status(self.status, f"Added '{tag}' to Include", "ok")

    def add_selected_to_exclude(self):
        tag = self.selected_tag()
        if tag and hasattr(self.host_app, "add_tag_to_exclude"):
            self.host_app.add_tag_to_exclude(tag)
            set_status(self.status, f"Added '{tag}' to Exclude", "ok")

    def copy_visible_tags(self):
        tags = [row.tag for row in self._visible_rows]
        QApplication.clipboard().setText(", ".join(tags))
        set_status(self.status, f"Copied {len(tags):,} visible tags", "info")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Tag Map", "tag_map.csv", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["tag", "category", "count", "coverage_percent"])
            for row in self._visible_rows:
                writer.writerow([row.tag, row.category, row.count, f"{row.coverage:.4f}"])
        set_status(self.status, f"Exported {len(self._visible_rows):,} rows", "ok")

    def show_context_menu(self, pos):
        tag = self.selected_tag()
        if not tag:
            return

        menu = QMenu(self)
        include_action = QAction("➕  Add to Include", self)
        exclude_action = QAction("➖  Add to Exclude", self)
        related_action = QAction("🧭  Map Related Tags", self)
        bubble_action = QAction("🫧  Open in Bubble Visualizer", self)
        copy_action = QAction("📋  Copy Tag", self)
        menu.addAction(include_action)
        menu.addAction(exclude_action)
        menu.addSeparator()
        menu.addAction(related_action)
        menu.addAction(bubble_action)
        menu.addSeparator()
        menu.addAction(copy_action)

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == include_action:
            self.add_selected_to_include()
        elif action == exclude_action:
            self.add_selected_to_exclude()
        elif action == related_action:
            self.map_related_to_selected()
        elif action == bubble_action:
            self.open_bubble_visualizer()
        elif action == copy_action:
            QApplication.clipboard().setText(tag)
            set_status(self.status, f"Copied '{tag}'", "info")

    def closeEvent(self, event):
        self._is_closing = True
        self._disconnect_host_updates()

        try:
            self._filter_timer.stop()
        except RuntimeError:
            pass

        self._stop_worker(wait_ms=700)

        if self._bubble_dialog_is_alive():
            try:
                if self._bubble_dialog.isVisible():
                    self._bubble_dialog.close()
            except RuntimeError:
                self._bubble_dialog = None
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Extension entry point
# ---------------------------------------------------------------------------

class InteractiveTagMapperExtension:
    def __init__(self, app):
        self.app = app
        self.dialog: Optional[InteractiveTagMapperDialog] = None

        self.button = QPushButton("Interactive Tag Mapper")
        self.button.setToolTip("Explore tag counts, related tags, and bubble relationships from the current search results.")
        self.button.clicked.connect(self.open_dialog)
        app.add_extension_button(self.button)

        signal = getattr(app, "data_updated", None)
        if signal is not None:
            signal.connect(self._enable_if_data)
        self._enable_if_data(getattr(app, "current_df", None))

    def _enable_if_data(self, df):
        self.button.setEnabled(df is not None and len(df) > 0)

    def _on_dialog_destroyed(self, *_args):
        self.dialog = None

    def _dialog_is_alive(self) -> bool:
        if self.dialog is None:
            return False
        try:
            self.dialog.isVisible()
            return True
        except RuntimeError:
            self.dialog = None
            return False

    def open_dialog(self):
        df = self.app.get_current_df() if hasattr(self.app, "get_current_df") else None
        if df is None or len(df) == 0:
            QMessageBox.information(self.app, "Interactive Tag Mapper", "Run a search first so the mapper has tags to analyze.")
            return

        if not self._dialog_is_alive():
            self.dialog = InteractiveTagMapperDialog(self.app, self.app)
            self.dialog.destroyed.connect(self._on_dialog_destroyed)

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()


def setup(app):
    """Entry point called by the host app's ExtensionManager."""
    app.interactive_tag_mapper_extension = InteractiveTagMapperExtension(app)
