import os
import polars as pl
import gc
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QLabel, 
    QTableWidget, QTableWidgetItem, QHBoxLayout, QProgressBar, 
    QHeaderView, QPushButton, QComboBox, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt

# Ensure Matplotlib uses the strict QtAgg backend to prevent memory leaks
import matplotlib
matplotlib.use('qtagg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


class TagAnalyticsDialog(QDialog):
    TOP_N_TAGS = 100

    def __init__(self, lazy_df, total_posts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tag Analytics Dashboard")
        self.resize(1150, 750)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # We store the LAZY dataframe pipeline, not the data itself.
        self.lazy_df = lazy_df
        self.total_posts = total_posts
        
        self.cached_dates = None
        self.raw_x_vals = []
        self.raw_y_vals = []
        self.raw_totals = None
        self.cached_global_totals = {}
        
        self.init_ui()
        self.calculate_stats()

    def init_ui(self):
        layout = QVBoxLayout(self)

        header_lbl = QLabel(f"📊 Dashboard: Analyzing {self.total_posts:,} Posts")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa; padding-bottom: 10px;")
        layout.addWidget(header_lbl)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tab_date = QWidget()
        self.tab_rating = QWidget()
        self.tab_char = QWidget()
        self.tab_copy = QWidget()
        self.tab_artist = QWidget()
        self.tab_general = QWidget()

        self.tabs.addTab(self.tab_date, "Date Analysis")
        self.tabs.addTab(self.tab_rating, "Ratings")
        self.tabs.addTab(self.tab_char, "Characters")
        self.tabs.addTab(self.tab_copy, "Copyrights")
        self.tabs.addTab(self.tab_artist, "Artists")
        self.tabs.addTab(self.tab_general, "General Tags")

    def calculate_stats(self):
        if self.total_posts == 0 or self.lazy_df is None:
            return

        # 1. Date Tab
        self.build_date_tab(self.tab_date)

        # 2. Ratings Tab - Streaming directly from disk/cache
        ratings = (
            self.lazy_df
            .select("rating")
            .filter(pl.col("rating").is_not_null())
            .group_by("rating")
            .len(name="count")
            .sort("count", descending=True)
            .collect(streaming=True) # Stream in batches
        )
        self.build_table_tab(
            self.tab_rating, ratings, "rating",
            {"g": "General", "s": "Sensitive", "q": "Questionable", "e": "Explicit"}
        )

        # 3. Tags Tabs - Streaming directly from disk/cache
        self.build_tag_tab(self.tab_char, "tag_string_character")
        self.build_tag_tab(self.tab_copy, "tag_string_copyright")
        self.build_tag_tab(self.tab_artist, "tag_string_artist")
        self.build_tag_tab(self.tab_general, "tag_string_general")

        # Destroy the pipeline reference to completely free any memory
        self.lazy_df = None
        gc.collect()

    # ==========================================
    # INTERACTIVE DATE TAB
    # ==========================================
    def build_date_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)

        schema = self.lazy_df.collect_schema().names()
        if "created_at" not in schema:
            layout.addWidget(QLabel("No created_at column found."))
            return

        # Collect ONLY the lightweight date strings into memory for rapid UI toggling
        self.cached_dates = self.lazy_df.select("created_at").drop_nulls().collect(streaming=True)

        # --- Controls ---
        ctrl_layout = QHBoxLayout()
        
        ctrl_layout.addWidget(QLabel("Interval:"))
        self.date_combo = QComboBox()
        self.date_combo.addItems(["Year", "Month", "Day"])
        self.date_combo.setCurrentIndex(1)
        self.date_combo.setMinimumWidth(100)
        self.date_combo.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4; border: 1px solid #45475a;")
        self.date_combo.currentTextChanged.connect(self.on_interval_changed)
        ctrl_layout.addWidget(self.date_combo)
        
        ctrl_layout.addSpacing(15)

        ctrl_layout.addWidget(QLabel("Chart Type:"))
        self.chart_combo = QComboBox()
        self.chart_combo.addItems(["Columns", "Line"])
        self.chart_combo.setCurrentIndex(0)
        self.chart_combo.setMinimumWidth(100)
        self.chart_combo.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4; border: 1px solid #45475a;")
        self.chart_combo.currentTextChanged.connect(self.redraw_chart)
        ctrl_layout.addWidget(self.chart_combo)
        
        ctrl_layout.addSpacing(15)
        
        self.date_norm = QCheckBox("Normalize (% of Total)")
        self.date_norm.setStyleSheet("color: #cdd6f4;")
        self.date_norm.toggled.connect(self.redraw_chart)
        ctrl_layout.addWidget(self.date_norm)
        
        ctrl_layout.addSpacing(15)
        
        self.date_smooth = QCheckBox("Smooth Data")
        self.date_smooth.setStyleSheet("color: #cdd6f4;")
        self.date_smooth.toggled.connect(self.redraw_chart)
        ctrl_layout.addWidget(self.date_smooth)
        
        ctrl_layout.addWidget(QLabel("Window:"))
        self.date_window = QSpinBox()
        self.date_window.setRange(1, 365)
        self.date_window.setValue(7)
        self.date_window.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4; border: 1px solid #45475a;")
        self.date_window.valueChanged.connect(self.redraw_chart)
        ctrl_layout.addWidget(self.date_window)
        
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # --- Figure ---
        self.date_fig = Figure(figsize=(10, 4.5), dpi=100, facecolor="#1e1e2e")
        self.date_canvas = FigureCanvas(self.date_fig)
        self.date_ax = self.date_fig.add_subplot(111)
        self.date_ax.set_facecolor("#313244")
        self.date_ax.tick_params(colors="#cdd6f4")
        for spine in self.date_ax.spines.values():
            spine.set_color("#6c7086")
        layout.addWidget(self.date_canvas)

        # --- Table ---
        self.date_table = QTableWidget(0, 2)
        self.date_table.setHorizontalHeaderLabels(["Date Unit", "Posts"])
        self.date_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.date_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.date_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.date_table.verticalHeader().setVisible(False)
        layout.addWidget(self.date_table)

        # Initial calculation
        self.on_interval_changed()

    def on_interval_changed(self):
        if self.cached_dates is None or len(self.cached_dates) == 0:
            return

        interval = self.date_combo.currentText()
        slice_len = 4 if interval == "Year" else 7 if interval == "Month" else 10

        counts_df = (
            self.cached_dates.lazy()
            .with_columns(pl.col("created_at").cast(pl.Utf8).str.slice(0, slice_len).alias("unit"))
            .group_by("unit")
            .len(name="count")
            .sort("unit")
            .collect()
        )

        # Fill holes in the timeline with 0s
        if len(counts_df) > 0:
            try:
                min_unit = counts_df["unit"][0]
                max_unit = counts_df["unit"][-1]

                all_units = []
                if interval == "Year":
                    min_y, max_y = int(min_unit), int(max_unit)
                    all_units = [str(y) for y in range(min_y, max_y + 1)]
                elif interval == "Month":
                    min_y, min_m = map(int, min_unit.split('-'))
                    max_y, max_m = map(int, max_unit.split('-'))
                    y, m = min_y, min_m
                    while (y, m) <= (max_y, max_m):
                        all_units.append(f"{y:04d}-{m:02d}")
                        m += 1
                        if m > 12:
                            m = 1
                            y += 1
                else:  # Day
                    d1 = datetime.strptime(min_unit, "%Y-%m-%d")
                    d2 = datetime.strptime(max_unit, "%Y-%m-%d")
                    curr = d1
                    while curr <= d2:
                        all_units.append(curr.strftime("%Y-%m-%d"))
                        curr += timedelta(days=1)
                
                full_df = pl.DataFrame({"unit": all_units}).with_columns(pl.col("unit").cast(pl.Utf8))
                counts_df = full_df.join(counts_df, on="unit", how="left").fill_null(0)
            except Exception as e:
                print(f"Failed to fill date gaps: {e}")

        self.raw_x_vals = counts_df["unit"].to_list()
        self.raw_y_vals = counts_df["count"].to_list()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paths = []
        for p in ["danbooru2026_clean.parquet", "danbooru_api_clean.parquet"]:
            full_path = os.path.join(base_dir, "data", p)
            if os.path.exists(full_path):
                paths.append(full_path)

        self.raw_totals = None
        if paths:
            try:
                if interval in self.cached_global_totals:
                    global_totals = self.cached_global_totals[interval]
                else:
                    lf = pl.scan_parquet(paths)
                    global_totals = (
                        lf.select("created_at")
                        .drop_nulls()
                        .with_columns(pl.col("created_at").cast(pl.Utf8).str.slice(0, slice_len).alias("unit"))
                        .group_by("unit")
                        .len(name="total")
                        .collect()
                    )
                    self.cached_global_totals[interval] = global_totals

                merged = counts_df.join(global_totals, on="unit", how="left").fill_null(0)
                self.raw_totals = merged["total"].to_list()
            except Exception as e:
                print(f"Failed to fetch global background totals: {e}")
                self.raw_totals = None

        self.date_table.setRowCount(len(counts_df))
        for i, row in enumerate(counts_df.iter_rows(named=True)):
            self.date_table.setItem(i, 0, QTableWidgetItem(str(row["unit"])))

        self.redraw_chart()

    def apply_smoothing(self, data, window):
        if window <= 1: return data
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window + 1)
            subset = data[start : i + 1]
            smoothed.append(sum(subset) / len(subset))
        return smoothed

    def redraw_chart(self):
        if not self.raw_x_vals:
            return

        x_vals = self.raw_x_vals
        y_vals = list(self.raw_y_vals)
        interval = self.date_combo.currentText()
        
        is_norm = self.date_norm.isChecked()
        is_smooth = self.date_smooth.isChecked()

        if is_norm and self.raw_totals is not None:
            y_vals = [(val / tot * 100) if tot > 0 else 0 for val, tot in zip(y_vals, self.raw_totals)]
            y_label = "Percentage of Total Posts (%)"
            table_header = "Percentage"
        else:
            y_label = "Number of Posts"
            table_header = "Posts"

        if is_smooth:
            y_vals = self.apply_smoothing(y_vals, self.date_window.value())

        self.date_table.setHorizontalHeaderLabels(["Date Unit", table_header])
        for i, val in enumerate(y_vals):
            if is_norm and self.raw_totals is not None:
                val_item = QTableWidgetItem(f"{val:.3f}%")
            else:
                if is_smooth:
                    val_item = QTableWidgetItem(f"{val:.1f}")
                else:
                    val_item = QTableWidgetItem(f"{int(val):,}")
            
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.date_table.setItem(i, 1, val_item)

        self.date_ax.clear()

        marker_style = 'o' if not is_smooth else None
        m_size = 4 if marker_style else None
        chart_type = self.chart_combo.currentText()
        
        if chart_type == "Line":
            self.date_ax.plot(x_vals, y_vals, marker=marker_style, markersize=m_size, color="#89b4fa", linewidth=2)
        else:
            self.date_ax.bar(x_vals, y_vals, color="#89b4fa")

        self.date_ax.set_title(f"Post Activity ({interval})", color="#cdd6f4", fontsize=14, pad=12)
        self.date_ax.set_xlabel(interval, color="#cdd6f4")
        self.date_ax.set_ylabel(y_label, color="#cdd6f4")

        tick_spacing = max(1, len(x_vals) // 15)
        self.date_ax.set_xticks(x_vals[::tick_spacing])
        self.date_ax.tick_params(axis="x", colors="#cdd6f4", rotation=45)
        self.date_ax.tick_params(axis="y", colors="#cdd6f4")
        self.date_ax.grid(axis="y", linestyle="--", alpha=0.25)
        
        self.date_fig.tight_layout()
        self.date_canvas.draw()


    # ==========================================
    # STATIC TABS (TAGS, RATINGS)
    # ==========================================
    def build_tag_tab(self, parent_widget, column_name):
        schema = self.lazy_df.collect_schema().names()
        if column_name not in schema: return

        counts = (
            self.lazy_df
            .select(column_name)
            .filter(pl.col(column_name).is_not_null())
            .select(pl.col(column_name).str.split(" ").alias("tags"))
            .explode("tags")
            .filter(pl.col("tags").str.len_chars() > 0)
            .group_by("tags")
            .len(name="count")
            .sort("count", descending=True)
            .head(self.TOP_N_TAGS)
            .collect(streaming=True) # Stream in batches
        )
        self.build_table_tab(parent_widget, counts, "tags")

    def build_table_tab(self, parent_widget, data_df, key_col, name_mapping=None):
        layout = QVBoxLayout(parent_widget)

        title = QLabel(f"Top {len(data_df):,} results")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #a6e3a1; padding-bottom: 6px;")
        layout.addWidget(title)

        table = QTableWidget(len(data_df), 3)
        table.setHorizontalHeaderLabels(["Name / Tag", "Count", "Frequency"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 110)
        table.setColumnWidth(2, 220)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        for i, row in enumerate(data_df.iter_rows(named=True)):
            raw_name = row[key_col]
            display_name = name_mapping.get(raw_name, raw_name) if name_mapping else raw_name
            count = row["count"]
            percentage = (count / self.total_posts) * 100 if self.total_posts else 0

            name_item = QTableWidgetItem(str(display_name))
            
            count_item = QTableWidgetItem(f"{count:,}")
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            prog_widget = QWidget()
            prog_layout = QHBoxLayout(prog_widget)
            prog_layout.setContentsMargins(5, 2, 10, 2)
            prog_layout.setSpacing(8)

            prog_bar = QProgressBar()
            prog_bar.setRange(0, 100)
            prog_bar.setValue(min(int(round(percentage)), 100))
            prog_bar.setTextVisible(False)

            lbl_pct = QLabel(f"{percentage:.1f}%")
            lbl_pct.setFixedWidth(45)
            lbl_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_pct.setStyleSheet("color: #cdd6f4; font-weight: bold;")

            prog_layout.addWidget(prog_bar)
            prog_layout.addWidget(lbl_pct)

            table.setItem(i, 0, name_item)
            table.setItem(i, 1, count_item)
            table.setCellWidget(i, 2, prog_widget)
            table.setRowHeight(i, 38)

        layout.addWidget(table)


    # ==========================================
    # MEMORY CLEANUP
    # ==========================================
    def closeEvent(self, event):
        self.lazy_df = None
        self.cached_dates = None
        self.raw_x_vals = []
        self.raw_y_vals = []
        self.raw_totals = None
        self.cached_global_totals = {}
        
        if hasattr(self, 'date_fig') and self.date_fig is not None:
            self.date_fig.clf()
            plt.close(self.date_fig)
            self.date_fig = None
            
        if hasattr(self, 'date_canvas'):
            self.date_canvas.setParent(None)
            self.date_canvas = None

        gc.collect()
        super().closeEvent(event)


class AnalyticsExtensionPlugin:
    def __init__(self, app):
        self.app = app
        self.btn = QPushButton("📊 Tag Analytics")
        self.btn.setEnabled(False)
        self.btn.setStyleSheet("background-color: #cba6f7; color: #11111b;")
        self.btn.clicked.connect(self.show_analytics)
        self.app.add_extension_button(self.btn)
        self.app.data_updated.connect(self.on_data_updated)

    def on_data_updated(self, df):
        # Enable the button if we have an unlimited data stream available, OR if the UI table has data
        has_unlimited = hasattr(self.app, 'get_unlimited_lazy_df') and self.app.get_unlimited_lazy_df() is not None
        has_local = df is not None and len(df) > 0
        self.btn.setEnabled(has_unlimited or has_local)

    def show_analytics(self):
        lazy_df = None
        
        # 1. Try to fetch the full unlimited pipeline
        if hasattr(self.app, 'get_unlimited_lazy_df') and self.app.get_unlimited_lazy_df() is not None:
            lazy_df = self.app.get_unlimited_lazy_df()
        # 2. Fallback to UI table if unlimited pipeline doesn't exist (backward compatibility)
        elif self.app.get_current_df() is not None:
            lazy_df = self.app.get_current_df().lazy()

        if lazy_df is not None:
            try:
                # Ask the hard drive exactly how many posts match our rules globally
                total_posts = lazy_df.select(pl.len()).collect().item()
                
                if total_posts > 0:
                    dialog = TagAnalyticsDialog(lazy_df, total_posts, self.app)
                    dialog.exec()
                    del dialog
                    gc.collect()
            except Exception as e:
                print(f"Error launching Tag Analytics: {e}")

def setup(app):
    plugin = AnalyticsExtensionPlugin(app)
    if not hasattr(app, "loaded_plugins"):
        app.loaded_plugins = []
    app.loaded_plugins.append(plugin)