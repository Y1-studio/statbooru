import os
import sys
import re
import polars as pl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QLineEdit, QPushButton, QGroupBox, QMessageBox, QComboBox,
    QCheckBox, QSpinBox, QDateEdit, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate

# Matplotlib for generating the chart
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class GlobalChartWorker(QThread):
    """Background worker to process millions of rows without freezing the UI"""
    # Emits: x_axis (list), y_data_dict (dict mapping query_str -> list), totals (list)
    finished = pyqtSignal(list, dict, list)
    error = pyqtSignal(str)

    def __init__(self, queries_to_process, date_from, date_to, interval="Month", compute_totals=True):
        super().__init__()
        self.queries = queries_to_process
        self.date_from = date_from
        self.date_to = date_to
        self.interval = interval
        self.compute_totals = compute_totals

    def run(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            paths = []
            for p in ["danbooru2026_clean.parquet", "danbooru_api_clean.parquet"]:
                full_path = os.path.join(base_dir, "data", p)
                if os.path.exists(full_path):
                    paths.append(full_path)

            if not paths:
                self.error.emit("No parquet databases found in the data/ folder.")
                return

            lf = pl.scan_parquet(paths)

            if self.interval == "Year":
                slice_len = 4
            elif self.interval == "Month":
                slice_len = 7
            else: # Day
                slice_len = 10

            time_col_name = "date_unit"

            # Base filtered frame (Date constraints applied globally)
            lf_base = (
                lf.filter(
                    (pl.col("created_at") >= self.date_from) &
                    (pl.col("created_at") <= self.date_to)
                )
                .with_columns(
                    pl.col("created_at").cast(pl.Utf8).str.slice(0, slice_len).alias(time_col_name)
                )
                .filter(
                    pl.col(time_col_name).is_not_null() & (pl.col(time_col_name).str.len_chars() == slice_len)
                )
            )

            def build_tag_filter(lazy_frame, tag_str):
                # Auto-convert 'rating:safe' to modern Danbooru 'General' and 'Sensitive'
                tag_str = re.sub(r'rating:safe', 'rating:g,s', tag_str, flags=re.IGNORECASE)

                # Try to use the Advanced Parser from the main app so users can use score:>=, OR, -, etc.
                main_module = sys.modules.get('__main__')
                QueryParser = getattr(main_module, 'QueryParser', None)

                if QueryParser:
                    exprs = QueryParser.build_polars_expr(tag_str)
                    for expr in exprs:
                        lazy_frame = lazy_frame.filter(expr)
                    return lazy_frame
                
                # Fallback parser if main app parser is unavailable
                normalized = tag_str.replace(",", " ")
                tags = [t.strip().lower() for t in normalized.split() if t.strip()]
                for tag in tags:
                    lazy_frame = lazy_frame.filter(pl.col("tag_string").str.split(" ").list.contains(tag))
                return lazy_frame

            all_units = lf_base.select(time_col_name).unique()

            # Only calculate global totals if they are missing from the cache
            if self.compute_totals:
                counts_total = lf_base.group_by(time_col_name).agg(pl.len().alias("total"))
                merged = all_units.join(counts_total, on=time_col_name, how="left")
            else:
                merged = all_units

            # Process dynamically ONLY for queries that need calculation
            for i, query in enumerate(self.queries):
                if query:
                    lf_q = build_tag_filter(lf_base, query)
                else:
                    lf_q = lf_base.filter(pl.lit(False))

                counts_q = lf_q.group_by(time_col_name).agg(pl.len().alias(f"count_{i}"))
                merged = merged.join(counts_q, on=time_col_name, how="left")

            merged = merged.fill_null(0).sort(time_col_name).collect()

            x_axis = merged[time_col_name].to_list()
            totals = merged["total"].to_list() if self.compute_totals else []

            y_data_dict = {}
            for i, query in enumerate(self.queries):
                y_data_dict[query] = merged[f"count_{i}"].to_list()

            self.finished.emit(x_axis, y_data_dict, totals)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class TagCompareDialog(QDialog):
    def __init__(self, date_from, date_to, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Tags Over Time")
        self.resize(1300, 850) # Larger default window size

        self.app = parent
        self.date_from = date_from
        self.date_to = date_to

        # Color palette (Catppuccin style) for dynamic lines
        self.palette = [
            "#89b4fa", "#f38ba8", "#a6e3a1", "#f9e2af", "#cba6f7", 
            "#fab387", "#94e2d5", "#b4befe", "#74c7ec", "#eba0ac", 
        ]

        # --- DATA CACHE ---
        self.raw_x = None
        self.raw_y_dict = {}
        self.raw_total = None

        # Smart Memory logic
        self.chart_cache = {}        # Maps: query_str -> y_data
        self.chart_cache_key = None  # Caches constraint key (date_from, date_to, interval)
        self.cached_x_axis = None
        self.cached_totals = None

        self.query_inputs = []

        self.init_ui()

    def create_input(self, placeholder):
        main_module = sys.modules.get('__main__')
        TagAutocompleteTextEdit = getattr(main_module, 'TagAutocompleteTextEdit', None)

        if TagAutocompleteTextEdit and hasattr(self.app, 'tag_data'):
            inp = TagAutocompleteTextEdit(self.app.tag_data)
            inp.setFixedHeight(34)
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet("padding: 4px; border-radius: 4px; background: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a;")
            return inp
        else:
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet("padding: 4px; border-radius: 4px; background: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a;")
            return inp

    def get_input_text(self, widget):
        if hasattr(widget, 'toPlainText'):
            return widget.toPlainText().strip()
        return widget.text().strip()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Use a splitter to allow resizing the sidebar vs the chart
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # ==========================================
        # LEFT PANEL (Controls)
        # ==========================================
        left_panel = QWidget()
        left_panel.setMaximumWidth(400)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # --- CONFIGURATION GROUP ---
        config_group = QGroupBox("Chart Configuration")
        config_layout = QVBoxLayout(config_group)

        # Date Row
        date_row1 = QHBoxLayout()
        date_row1.addWidget(QLabel("📅 <b>Active Time Range:</b>"))
        config_layout.addLayout(date_row1)

        date_row2 = QHBoxLayout()
        self.date_from_edit = QDateEdit(QDate.fromString(self.date_from, "yyyy-MM-dd"))
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4; border: 1px solid #45475a;")

        self.date_to_edit = QDateEdit(QDate.fromString(self.date_to, "yyyy-MM-dd"))
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4; border: 1px solid #45475a;")

        date_row2.addWidget(self.date_from_edit)
        date_row2.addWidget(QLabel("→"))
        date_row2.addWidget(self.date_to_edit)
        config_layout.addLayout(date_row2)

        # Settings
        settings_grid = QVBoxLayout()

        int_row = QHBoxLayout()
        int_row.addWidget(QLabel("Interval:"))
        self.combo_interval = QComboBox()
        self.combo_interval.addItems(["Year", "Month", "Day"])
        self.combo_interval.setCurrentIndex(1)
        self.combo_interval.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4;")
        int_row.addWidget(self.combo_interval)
        settings_grid.addLayout(int_row)

        self.chk_normalize = QCheckBox("Normalize (Percentage of Total)")
        self.chk_normalize.setStyleSheet("color: #cdd6f4;")
        self.chk_normalize.toggled.connect(self.update_visuals)
        settings_grid.addWidget(self.chk_normalize)

        smooth_row = QHBoxLayout()
        self.chk_smooth = QCheckBox("Smooth")
        self.chk_smooth.setStyleSheet("color: #cdd6f4;")
        self.chk_smooth.toggled.connect(self.update_visuals)
        smooth_row.addWidget(self.chk_smooth)

        self.spin_smooth = QSpinBox()
        self.spin_smooth.setRange(1, 365)
        self.spin_smooth.setValue(7)
        self.spin_smooth.setStyleSheet("padding: 4px; background: #313244; color: #cdd6f4;")
        self.spin_smooth.setFixedWidth(50)
        self.spin_smooth.valueChanged.connect(self.update_visuals)
        smooth_row.addWidget(QLabel("Win:"))
        smooth_row.addWidget(self.spin_smooth)
        settings_grid.addLayout(smooth_row)

        config_layout.addLayout(settings_grid)
        left_layout.addWidget(config_group)

        # --- COMPARISON GROUPS ---
        groups_box = QGroupBox("Tag Groups (Dynamic)")
        groups_box_layout = QVBoxLayout(groups_box)
        groups_box_layout.setContentsMargins(5, 10, 5, 5)

        # Scroll area for inputs to handle 3+ items elegantly
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        self.inputs_layout = QVBoxLayout(scroll_content)
        self.inputs_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.inputs_layout.setContentsMargins(0, 0, 0, 0)
        self.inputs_layout.setSpacing(6)

        scroll.setWidget(scroll_content)
        groups_box_layout.addWidget(scroll)

        self.btn_add_group = QPushButton("➕ Add Tag Group")
        self.btn_add_group.setStyleSheet("background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 6px; border-radius: 4px;")
        self.btn_add_group.clicked.connect(lambda: self.add_input_group(""))
        groups_box_layout.addWidget(self.btn_add_group)

        left_layout.addWidget(groups_box)

        # Run Action
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #f9e2af; font-weight: bold; font-size: 11px;")
        left_layout.addWidget(self.lbl_status)

        self.btn_generate = QPushButton("▶ Generate Chart")
        self.btn_generate.setFixedHeight(40)
        self.btn_generate.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; font-size: 14px; border-radius: 4px;")
        self.btn_generate.clicked.connect(self.start_generation)
        left_layout.addWidget(self.btn_generate)

        splitter.addWidget(left_panel)

        # ==========================================
        # RIGHT PANEL (Chart)
        # ==========================================
        chart_panel = QWidget()
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(dpi=100, facecolor="#1e1e2e")
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#313244")
        self.ax.tick_params(colors="#cdd6f4")
        for spine in self.ax.spines.values():
            spine.set_color("#6c7086")

        chart_layout.addWidget(self.canvas)
        splitter.addWidget(chart_panel)

        # Set stretch factor so chart takes up most space
        splitter.setSizes([300, 1000])

        # Init with 2 groups by default
        self.add_input_group("")
        self.add_input_group("")

    def add_input_group(self, text=""):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        idx = len(self.query_inputs)
        color = self.palette[idx % len(self.palette)]

        color_lbl = QLabel("■")
        color_lbl.setStyleSheet(f"color: {color}; font-size: 18px;")
        row_layout.addWidget(color_lbl)

        inp = self.create_input(f"Group {idx+1} tags...")
        if text:
            if hasattr(inp, 'setPlainText'): inp.setPlainText(text)
            else: inp.setText(text)
        row_layout.addWidget(inp)

        btn_remove = QPushButton("❌")
        btn_remove.setFixedSize(26, 26)
        btn_remove.setStyleSheet("background: transparent; border: none; font-size: 12px;")
        btn_remove.clicked.connect(lambda: self.remove_input_group(row_widget))
        row_layout.addWidget(btn_remove)

        self.inputs_layout.addWidget(row_widget)

        item_data = {
            'widget': row_widget,
            'input': inp,
            'color': color,
            'btn_remove': btn_remove
        }
        self.query_inputs.append(item_data)
        self.update_remove_buttons()

    def remove_input_group(self, row_widget):
        if len(self.query_inputs) <= 1:
            return

        for item in self.query_inputs:
            if item['widget'] == row_widget:
                self.query_inputs.remove(item)
                row_widget.deleteLater()
                break

        # Reassign colors and placeholders based on new positions
        for idx, item in enumerate(self.query_inputs):
            item['color'] = self.palette[idx % len(self.palette)]
            item['widget'].layout().itemAt(0).widget().setStyleSheet(f"color: {item['color']}; font-size: 18px;")
            if not self.get_input_text(item['input']):
                item['input'].setPlaceholderText(f"Group {idx+1} tags...")

        self.update_remove_buttons()

        # Update chart based on the new array of queries (if data is populated)
        queries = [self.get_input_text(item['input']) for item in self.query_inputs]
        if self.cached_x_axis is not None:
            self.assemble_and_draw(queries)

    def update_remove_buttons(self):
        visible = len(self.query_inputs) > 1
        for item in self.query_inputs:
            item['btn_remove'].setVisible(visible)

    def apply_smoothing(self, data, window):
        if window <= 1: return data
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window + 1)
            subset = data[start : i + 1]
            smoothed.append(sum(subset) / len(subset))
        return smoothed

    def update_visuals(self):
        """Triggers redraw if data is cached"""
        if self.raw_x is not None:
            self.draw_chart()

    def start_generation(self):
        # All currently entered tags
        queries = [self.get_input_text(item['input']) for item in self.query_inputs]

        if all(not q for q in queries):
            QMessageBox.information(self, "Info", "Please enter tags in at least one group.")
            return

        interval = self.combo_interval.currentText()
        date_from_str = self.date_from_edit.date().toString("yyyy-MM-dd")
        date_to_str = self.date_to_edit.date().toString("yyyy-MM-dd")

        # Cache Invalidation: Clear cache if time constraints are changed
        new_cache_key = (date_from_str, date_to_str, interval)
        if new_cache_key != self.chart_cache_key:
            self.chart_cache.clear()
            self.cached_x_axis = None
            self.cached_totals = None
            self.chart_cache_key = new_cache_key

        # Optimization: Only calculate queries that aren't already cached
        queries_to_process = []
        for q in set(queries): 
            if q and q not in self.chart_cache:
                queries_to_process.append(q)

        need_totals = self.cached_totals is None

        # If no work is needed, immediately assemble the arrays from memory and draw
        if not queries_to_process and not need_totals:
            self.lbl_status.setText("Loaded from memory instantly!")
            self.assemble_and_draw(queries)
            return

        self.btn_generate.setEnabled(False)
        self.btn_add_group.setEnabled(False)
        self.lbl_status.setText(f"Scanning global database for missing queries...")

        self.worker = GlobalChartWorker(queries_to_process, date_from_str, date_to_str, interval, need_totals)
        # Lambda closure passes the original ordered queries so we can draw them in the right color/order
        self.worker.finished.connect(lambda x, y, t, qs=queries: self.on_generation_success(x, y, t, qs))
        self.worker.error.connect(self.on_generation_error)
        self.worker.start()

    def on_generation_success(self, x_axis, y_data_dict, totals, original_queries):
        self.btn_generate.setEnabled(True)
        self.btn_add_group.setEnabled(True)
        self.lbl_status.setText("Chart generated successfully!")

        # Update base constraint cache 
        if self.cached_x_axis is None and x_axis:
            self.cached_x_axis = x_axis
        if self.cached_totals is None and totals:
            self.cached_totals = totals

        # Merge new calculations directly into the dictionary cache
        for q_str, data in y_data_dict.items():
            self.chart_cache[q_str] = data

        # Push to visual render
        self.assemble_and_draw(original_queries)

    def assemble_and_draw(self, original_queries):
        """Assembles the final dictionary to accurately match the UI box ordering."""
        self.raw_x = self.cached_x_axis
        self.raw_total = self.cached_totals
        self.raw_y_dict = {}

        for i, q in enumerate(original_queries):
            if q and q in self.chart_cache:
                self.raw_y_dict[i] = self.chart_cache[q]

        self.draw_chart()

    def on_generation_error(self, error_msg):
        self.btn_generate.setEnabled(True)
        self.btn_add_group.setEnabled(True)
        self.lbl_status.setText("Error occurred.")
        QMessageBox.critical(self, "Error", error_msg)

    def draw_chart(self):
        if self.raw_x is None:
            return

        interval = self.combo_interval.currentText()
        self.ax.clear()

        marker_style = 'o' if not self.chk_smooth.isChecked() else None
        m_size = 4 if marker_style else None

        has_plotted = False

        for i, item in enumerate(self.query_inputs):
            query_str = self.get_input_text(item['input'])
            if not query_str or i not in self.raw_y_dict:
                continue

            y_vals = list(self.raw_y_dict[i])

            # 1. Normalization
            if self.chk_normalize.isChecked() and self.raw_total:
                y_vals = [(val / tot * 100) if tot > 0 else 0 for val, tot in zip(y_vals, self.raw_total)]

            # 2. Smoothing
            if self.chk_smooth.isChecked():
                window = self.spin_smooth.value()
                y_vals = self.apply_smoothing(y_vals, window)

            # Cap label length to keep legend clean
            display_label = query_str if len(query_str) < 30 else query_str[:27] + "..."

            self.ax.plot(
                self.raw_x, y_vals,
                marker=marker_style, markersize=m_size,
                color=item['color'],
                label=display_label,
                linewidth=2
            )
            has_plotted = True

        self.ax.set_title(f"Dynamic Tag Comparison ({interval})", color="#cdd6f4", fontsize=14, pad=12)
        self.ax.set_xlabel(interval.capitalize(), color="#cdd6f4")

        y_label = "Percentage of Total Posts (%)" if self.chk_normalize.isChecked() else "Number of Posts"
        self.ax.set_ylabel(y_label, color="#cdd6f4")

        # Smart X-axis ticking to prevent overlap
        tick_spacing = max(1, len(self.raw_x) // 15)
        self.ax.set_xticks(self.raw_x[::tick_spacing])
        self.ax.tick_params(axis="x", colors="#cdd6f4", rotation=45)
        self.ax.tick_params(axis="y", colors="#cdd6f4")

        for spine in self.ax.spines.values():
            spine.set_color("#6c7086")

        self.ax.grid(axis="y", linestyle="--", alpha=0.25)
        self.ax.grid(axis="x", linestyle="--", alpha=0.1)

        if has_plotted:
            self.ax.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4", loc="upper left")

        # Use tight layout with padding for aesthetics
        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()


class TagComparePlugin:
    def __init__(self, app):
        self.app = app
        self.btn = QPushButton("📈 Compare Tags Globally")
        self.btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        self.btn.clicked.connect(self.show_dialog)
        self.app.add_extension_button(self.btn)

    def show_dialog(self):
        date_from_str = self.app.date_from.date().toString("yyyy-MM-dd")
        date_to_str = self.app.date_to.date().toString("yyyy-MM-dd")
        dialog = TagCompareDialog(date_from_str, date_to_str, self.app)
        dialog.exec()

def setup(app):
    plugin = TagComparePlugin(app)
    if not hasattr(app, "loaded_plugins"):
        app.loaded_plugins = []
    app.loaded_plugins.append(plugin)