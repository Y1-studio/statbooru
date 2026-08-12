"""Theme switcher extension for Statbooru.

Drop this file in ``extensions/`` (where it already lives in this project).
The host discovers it automatically through ``setup(app)``.
"""

import importlib.util
import json
import os
from functools import lru_cache

THEME_DIRECTORY = os.path.join(os.path.dirname(__file__), "themes")
_RUNTIME_MODULES = {}


def load_runtime_module(module_name, optional=False):
    """Load a private theme runtime without exposing it as an extension."""
    if module_name in _RUNTIME_MODULES:
        return _RUNTIME_MODULES[module_name]
    path = os.path.join(THEME_DIRECTORY, f"{module_name}.py")
    if not os.path.isfile(path):
        if optional:
            return None
        raise RuntimeError(f"Theme support file is missing: {path}")
    spec = importlib.util.spec_from_file_location(
        f"statbooru_theme_{module_name}",
        path,
    )
    if spec is None or spec.loader is None:
        if optional:
            return None
        raise RuntimeError(f"Unable to load theme runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        if optional:
            print(f"Skipped unavailable theme runtime {module_name}: {exc}")
            return None
        raise
    _RUNTIME_MODULES[module_name] = module
    return module


AERO_RUNTIME = load_runtime_module("windows_7_aero", optional=True)
WIN31_RUNTIME = load_runtime_module("windows_31", optional=True)
METRO_RUNTIME = load_runtime_module("windows_8_metro", optional=True)
RETRO_RUNTIME = load_runtime_module("retro_dither", optional=True)
STYLE_RUNTIME = load_runtime_module("stylesheet_renderer")
XP_CLASSIC_RUNTIME = load_runtime_module(
    "windows_xp_luna_classic",
    optional=True,
)

RUNTIME_DEPENDENCIES = {
    "aero": ("windows_7_aero", AERO_RUNTIME),
    "metro": ("windows_8_metro", METRO_RUNTIME),
    "win31": ("windows_31", WIN31_RUNTIME),
    "xp_classic": ("windows_xp_luna_classic", XP_CLASSIC_RUNTIME),
    "retro": ("retro_dither", RETRO_RUNTIME),
}


def _runtime_style(runtime, attribute):
    return getattr(runtime, attribute, None) if runtime is not None else None

BUTTON_OVERRIDE_STYLES = {
    mode: style
    for mode, style in (
        ("dithered", _runtime_style(RETRO_RUNTIME, "BUTTON_STYLE")),
        ("aero", _runtime_style(AERO_RUNTIME, "BUTTON_STYLE")),
        ("win31", _runtime_style(WIN31_RUNTIME, "BUTTON_STYLE")),
        (
            "xpclassic",
            _runtime_style(XP_CLASSIC_RUNTIME, "BUTTON_STYLE"),
        ),
    )
    if style is not None
}

STATS_OVERRIDE_STYLES = {
    mode: style
    for mode, style in (
        ("dithered", _runtime_style(RETRO_RUNTIME, "STATS_STYLE")),
        ("aero", _runtime_style(AERO_RUNTIME, "STATS_STYLE")),
        ("metro", _runtime_style(METRO_RUNTIME, "STATS_STYLE")),
        ("win31", _runtime_style(WIN31_RUNTIME, "STATS_STYLE")),
        (
            "xpclassic",
            _runtime_style(XP_CLASSIC_RUNTIME, "STATS_STYLE"),
        ),
    )
    if style is not None
}

from PyQt6.QtCore import QEvent, QObject, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

REQUIRED_THEME_KEYS = {
    "bg",
    "surface",
    "surface_alt",
    "border",
    "border_hover",
    "text",
    "muted",
    "accent",
    "accent_hover",
    "accent_text",
    "success",
}


def load_theme_catalog(
    theme_directory=THEME_DIRECTORY,
    runtime_availability=None,
):
    """Load ordered theme definitions from extensions/themes/*.json."""
    if not os.path.isdir(theme_directory):
        raise RuntimeError(f"Theme directory is missing: {theme_directory}")

    if runtime_availability is None:
        runtime_availability = {
            module_name: runtime is not None
            for module_name, runtime in RUNTIME_DEPENDENCIES.values()
        }

    catalog = {}
    errors = []
    filenames = sorted(
        filename
        for filename in os.listdir(theme_directory)
        if filename.lower().endswith(".json")
    )
    for filename in filenames:
        path = os.path.join(theme_directory, filename)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                definition = json.load(handle)
            if not isinstance(definition, dict):
                raise ValueError("root value must be an object")
            name = str(definition.pop("name", "")).strip()
            if not name:
                raise ValueError("missing non-empty 'name'")
            missing = sorted(REQUIRED_THEME_KEYS - definition.keys())
            if missing:
                raise ValueError(
                    "missing required keys: " + ", ".join(missing)
                )
            if name in catalog:
                raise ValueError(f"duplicate theme name: {name}")

            unavailable = [
                module_name
                for flag, (
                    module_name,
                    _runtime,
                ) in RUNTIME_DEPENDENCIES.items()
                if definition.get(flag)
                and not runtime_availability.get(module_name, False)
            ]
            if unavailable:
                raise ValueError(
                    "required runtime file is unavailable: "
                    + ", ".join(f"{name}.py" for name in unavailable)
                )

            # Color-map controls are optional for non-retro themes. If the
            # shared dither helper was removed, keep those themes usable and
            # simply hide their image-processing controls.
            if (
                definition.get("color_map_options")
                and not runtime_availability.get("retro_dither", False)
            ):
                definition["color_map_options"] = False
            catalog[name] = definition
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{filename}: {exc}")

    if errors:
        print("Skipped invalid theme files:\n  " + "\n  ".join(errors))
    if not catalog:
        raise RuntimeError(
            f"No valid theme JSON files were found in {theme_directory}"
        )
    return catalog


THEMES = load_theme_catalog()


@lru_cache(maxsize=len(THEMES))
def stylesheet_for_theme(name):
    """Build each large theme stylesheet only once per process."""
    return STYLE_RUNTIME.build_stylesheet(THEMES[name], RETRO_RUNTIME)


class InactiveThemeController:
    """No-op controller used when an optional theme runtime was removed."""

    def enabled_for(self, *_args):
        return False

    def stylesheet_suffix(self, *_args):
        return ""

    def style_for_button(self, *_args):
        return ""

    def apply_theme(self, *_args):
        pass

    def set_enabled(self, *_args):
        pass

    def prepare_theme_change(self, *_args):
        pass

    def handle_widget_show(self, *_args):
        pass

    def refresh_readability(self, *_args):
        pass

    def refresh_autocomplete(self, *_args):
        pass

    def refresh_groups(self, *_args):
        pass

    def refresh_widget_roles(self, *_args):
        pass


class ThemeDialog(QDialog):
    def __init__(self, app, switcher):
        super().__init__(app)
        self.setObjectName("themeChooserDialog")
        self.switcher = switcher
        self.setWindowTitle("Choose Theme")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Theme changes are previewed immediately:"))

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES)
        current = getattr(app, "current_theme_name", next(iter(THEMES)))
        self.theme_combo.setCurrentText(current)
        layout.addWidget(self.theme_combo)

        self.enable_dither = QCheckBox(
            "Enable color-map dithering for icons and images"
        )
        self.enable_dither.toggled.connect(self._sync_control_enabled)
        layout.addWidget(self.enable_dither)

        self.color_count_label = QLabel()
        layout.addWidget(self.color_count_label)

        self.color_count_slider = QSlider(Qt.Orientation.Horizontal)
        self.color_count_slider.setRange(2, 256)
        self.color_count_slider.setSingleStep(1)
        self.color_count_slider.setPageStep(16)
        self.color_count_slider.setTickInterval(32)
        self.color_count_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.color_count_slider.valueChanged.connect(self._color_count_changed)
        layout.addWidget(self.color_count_slider)

        self.dither_thumbnails = QCheckBox("Dither result thumbnails")
        layout.addWidget(self.dither_thumbnails)

        self.dither_opened_pictures = QCheckBox(
            "Dither images opened in the picture viewer"
        )
        layout.addWidget(self.dither_opened_pictures)

        self.apply_dither_button = QPushButton("Apply Dither Settings")
        self.apply_dither_button.clicked.connect(self._apply_dither_settings)
        layout.addWidget(self.apply_dither_button)

        layout.addWidget(QLabel("Maximum dithered full-image resolution:"))
        self.full_image_resolution = QComboBox()
        self.full_image_resolution.addItem("256 px", 256)
        self.full_image_resolution.addItem("512 px", 512)
        self.full_image_resolution.addItem("720 px", 720)
        self.full_image_resolution.addItem("1024 px", 1024)
        self.full_image_resolution.addItem("1440 px", 1440)
        self.full_image_resolution.addItem("2048 px", 2048)
        self.full_image_resolution.addItem("4096 px", 4096)
        self.full_image_resolution.addItem(
            "Unlimited (original resolution)", 0
        )
        resolution_index = self.full_image_resolution.findData(
            self.switcher.full_image_max_resolution
        )
        self.full_image_resolution.setCurrentIndex(
            max(0, resolution_index)
        )
        self.full_image_resolution.setToolTip(
            "Caps the longest edge before dithering. The viewer always uses "
            "sharp nearest-neighbor scaling."
        )
        layout.addWidget(self.full_image_resolution)

        self.force_theme = QCheckBox(
            "Force theme on extension windows, charts, and hard-coded text"
        )
        self.force_theme.setChecked(self.switcher.force_theme)
        layout.addWidget(self.force_theme)

        self.apply_display_button = QPushButton("Apply Display Settings")
        self.apply_display_button.clicked.connect(
            self._apply_display_settings
        )
        layout.addWidget(self.apply_display_button)

        self.switcher.aero.add_dialog_controls(self, layout)

        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        self._load_dither_controls(current)
        self.switcher.aero.sync_dialog_controls(self, current)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def _theme_changed(self, name):
        self.switcher.apply(name)
        self._load_dither_controls(name)
        self.switcher.aero.sync_dialog_controls(self, name)

    def _color_count_changed(self, value):
        self.color_count_label.setText(f"Dither color map: {value} colors")

    def _load_dither_controls(self, name):
        theme = THEMES.get(name, {})
        visible = theme.get("color_map_options", False)
        options = self.switcher.get_dither_options(name)

        controls = (
            self.enable_dither,
            self.color_count_label,
            self.color_count_slider,
            self.dither_thumbnails,
            self.dither_opened_pictures,
            self.apply_dither_button,
        )
        for control in controls:
            control.setVisible(visible)
        if not visible:
            return

        self.enable_dither.setChecked(options["enabled"])
        self.color_count_slider.setValue(options["color_count"])
        self.dither_thumbnails.setChecked(options["thumbnails"])
        self.dither_opened_pictures.setChecked(options["opened_pictures"])
        self._color_count_changed(options["color_count"])
        self._sync_control_enabled(options["enabled"])

    def _sync_control_enabled(self, enabled):
        self.color_count_label.setEnabled(enabled)
        self.color_count_slider.setEnabled(enabled)
        self.dither_thumbnails.setEnabled(enabled)
        self.dither_opened_pictures.setEnabled(enabled)
        self.apply_dither_button.setEnabled(True)

    def _apply_dither_settings(self):
        self.switcher.apply_dither_settings(
            self.theme_combo.currentText(),
            self.color_count_slider.value(),
            self.enable_dither.isChecked(),
            self.dither_thumbnails.isChecked(),
            self.dither_opened_pictures.isChecked(),
        )
        self.apply_dither_button.setText("Applied")
        QTimer.singleShot(
            900,
            lambda: self.apply_dither_button.setText("Apply Dither Settings"),
        )

    def _apply_display_settings(self):
        self.switcher.apply_display_settings(
            int(self.full_image_resolution.currentData()),
            self.force_theme.isChecked(),
        )
        self.apply_display_button.setText("Applied")
        QTimer.singleShot(
            900,
            lambda: self.apply_display_button.setText(
                "Apply Display Settings"
            ),
        )

class ThemeWindowEventFilter(QObject):
    """Handle theme-neutral widgets created after extension startup."""

    def __init__(self, switcher):
        super().__init__(switcher.app)
        self.switcher = switcher

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.Resize
            and watched.__class__.__name__ == "ImageViewerDialog"
        ):
            QTimer.singleShot(
                0,
                lambda viewer=watched:
                self.switcher._render_viewer_with_sharp_pixels(viewer),
            )
        if event.type() == QEvent.Type.Show:
            self.switcher.win31.handle_widget_show(watched)
            self.switcher.xp_classic.handle_widget_show(watched)
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            QTimer.singleShot(
                0,
                lambda window=watched:
                self.switcher._refresh_widget_overrides(window),
            )
            QTimer.singleShot(0, self.switcher._apply_force_theme)
        return False


class ThemeSwitcher:
    def __init__(self, app):
        self.app = app
        self.settings = QSettings("Statbooru", "ThemeSwitcher")
        self.dialog = None
        self.full_image_max_resolution = max(
            0,
            self.settings.value(
                "full_image_max_resolution", 0, type=int
            ),
        )
        self.force_theme = self.settings.value(
            "force_theme", False, type=bool
        )
        saved_color_count = self.settings.value("dither_color_count", 4, type=int)
        self.dither_color_count = max(2, min(256, saved_color_count))
        self._button_styles = {}
        self._label_styles = {}
        self._control_styles = {}
        self._rich_text_states = {}
        self._autocomplete_styles = {}
        self._forced_widget_styles = {}
        self._forced_chart_states = {}
        self._forced_window_signatures = {}
        self._style_epoch = 0
        self._initial_refresh_scheduled = False
        self._button_overrides_active = False
        self._stats_style = app.lbl_stats.styleSheet() if hasattr(app, "lbl_stats") else ""
        self._thumbnail_states = {}
        self._thumbnail_timer = QTimer(app)
        self._thumbnail_timer.setInterval(350)
        self._thumbnail_timer.timeout.connect(self._refresh_thumbnails)
        self._picture_states = {}
        self._picture_timer = QTimer(app)
        self._picture_timer.setInterval(350)
        self._picture_timer.timeout.connect(self._refresh_opened_pictures)
        self._force_timer = QTimer(app)
        self._force_timer.setInterval(1250)
        self._force_timer.timeout.connect(self._apply_force_theme)
        self._window_event_filter = ThemeWindowEventFilter(self)
        QApplication.instance().installEventFilter(self._window_event_filter)
        self.win31 = (
            WIN31_RUNTIME.Win31Controller(self)
            if WIN31_RUNTIME is not None
            else InactiveThemeController()
        )
        self.metro = (
            METRO_RUNTIME.MetroController(self)
            if METRO_RUNTIME is not None
            else InactiveThemeController()
        )
        self.xp_classic = (
            XP_CLASSIC_RUNTIME.XPClassicController(self)
            if XP_CLASSIC_RUNTIME is not None
            else InactiveThemeController()
        )
        self.aero = (
            AERO_RUNTIME.AeroController(self, THEMES)
            if AERO_RUNTIME is not None
            else InactiveThemeController()
        )

        saved_theme = self.settings.value("theme", "Midnight Sakura", type=str)
        if saved_theme not in THEMES:
            saved_theme = (
                "Midnight Sakura"
                if "Midnight Sakura" in THEMES
                else next(iter(THEMES))
            )
        self.apply(saved_theme)

        self.button = QPushButton("Theme")
        self.button.setToolTip("Change the Statbooru color theme")
        self.button.clicked.connect(self.open_dialog)
        app.add_extension_button(self.button)

    def _aero_enabled_for(self, name):
        return self.aero.enabled_for(name)

    def _stylesheet_for_name(self, name):
        xp_suffix = (
            XP_CLASSIC_RUNTIME.stylesheet_suffix(
                bool(THEMES.get(name, {}).get("xp_classic"))
            )
            if XP_CLASSIC_RUNTIME is not None
            else ""
        )
        return (
            stylesheet_for_theme(name)
            + self.aero.stylesheet_suffix(name)
            + xp_suffix
        )

    def apply(self, name):
        if name not in THEMES:
            return
        self._style_epoch += 1
        self._thumbnail_timer.stop()
        self._picture_timer.stop()
        self._restore_thumbnails()
        self._restore_opened_pictures()
        self.xp_classic.prepare_theme_change(name)
        self.app.setStyleSheet(self._stylesheet_for_name(name))
        self.app.current_theme_name = name
        self.settings.setValue("theme", name)
        self.dither_color_count = self.get_dither_options(name)["color_count"]
        self.aero.apply_theme(name)
        self._refresh_widget_overrides()
        self.xp_classic.apply_theme(name)
        self._sync_effect_timers()
        self._sync_force_theme()
        # One deferred pass catches extensions loaded after this one. Later
        # theme changes already update every existing widget synchronously.
        if not self._initial_refresh_scheduled:
            self._initial_refresh_scheduled = True
            QTimer.singleShot(0, self._refresh_widget_overrides)

    def apply_display_settings(self, max_resolution, force_theme):
        """Persist the two global display controls from the theme dialog."""
        self._style_epoch += 1
        self.full_image_max_resolution = max(0, int(max_resolution))
        self.force_theme = bool(force_theme)
        self.settings.setValue(
            "full_image_max_resolution",
            self.full_image_max_resolution,
        )
        self.settings.setValue("force_theme", self.force_theme)

        # Rebuild active viewer pictures from their saved full-color originals.
        self._picture_timer.stop()
        self._restore_opened_pictures()
        self._sync_effect_timers()
        self._sync_force_theme()

    def apply_aero_transparency(self, enabled):
        """Compatibility entry point for older callers."""
        self.aero.set_enabled(enabled)

    def _sync_force_theme(self):
        if self.force_theme:
            self._force_timer.start()
            self._apply_force_theme()
        else:
            self._force_timer.stop()
            self._restore_forced_theme()
            self._refresh_widget_overrides()

    def _apply_force_theme(self):
        """Override hard-coded extension styles and Matplotlib canvases."""
        if not self.force_theme:
            return
        self._prune_dead_widget_references()
        name = getattr(self.app, "current_theme_name", "")
        colors = THEMES.get(name)
        if not colors:
            return
        stylesheet = self._stylesheet_for_name(name)

        for window in QApplication.topLevelWidgets():
            if not isinstance(window, QDialog) or window is self.dialog:
                continue
            if window.__class__.__name__ == "ThemeDialog":
                continue

            widgets = [window] + window.findChildren(QWidget)
            for widget in widgets:
                if widget.objectName() == "_aeroGlassBacking":
                    continue
                if widget.property("tutorialManagedStyle"):
                    continue
                key = id(widget)
                if key not in self._forced_widget_styles:
                    original_style = widget.styleSheet()
                    if key in self._control_styles:
                        original_style = self._control_styles[key][1]
                    elif key in self._label_styles:
                        original_style = self._label_styles[key][1]
                    elif key in self._button_styles:
                        original_style = self._button_styles[key][1]
                    self._forced_widget_styles[key] = (
                        widget,
                        original_style,
                    )
                if widget is not window and widget.styleSheet():
                    widget.setStyleSheet("")
            signature = (name, self._style_epoch)
            if self._forced_window_signatures.get(id(window)) != signature:
                window.setStyleSheet(stylesheet)
                self._forced_window_signatures[id(window)] = signature

            for widget in widgets:
                if hasattr(widget, "figure") and hasattr(widget, "draw_idle"):
                    signature = (name, len(widget.figure.axes))
                    self._force_chart_theme(
                        widget,
                        colors,
                        redraw=(
                            getattr(
                                widget,
                                "_forced_theme_signature",
                                None,
                            )
                            != signature
                        ),
                    )

    def _force_chart_theme(self, canvas, colors, redraw=True):
        """Apply the active palette to a Matplotlib canvas and future redraws."""
        figure = getattr(canvas, "figure", None)
        if figure is None:
            return
        key = id(canvas)
        if key not in self._forced_chart_states:
            axes_state = []
            for axis in figure.axes:
                text_artists = [
                    axis.title,
                    axis.xaxis.label,
                    axis.yaxis.label,
                    *axis.get_xticklabels(),
                    *axis.get_yticklabels(),
                    *axis.texts,
                ]
                axes_state.append(
                    (
                        axis,
                        axis.get_facecolor(),
                        [(artist, artist.get_color()) for artist in text_artists],
                        [
                            (spine, spine.get_edgecolor())
                            for spine in axis.spines.values()
                        ],
                    )
                )
            self._forced_chart_states[key] = (
                canvas,
                figure.get_facecolor(),
                axes_state,
            )

        surface = colors.get("surface", colors["bg"])
        plot_surface = colors.get("surface_alt", surface)
        text = colors.get("text", "#000000")
        border = colors.get("border", text)
        figure.set_facecolor(surface)
        for axis in figure.axes:
            axis.set_facecolor(plot_surface)
            axis.tick_params(colors=text)
            axis.title.set_color(text)
            axis.xaxis.label.set_color(text)
            axis.yaxis.label.set_color(text)
            for label in (
                *axis.get_xticklabels(),
                *axis.get_yticklabels(),
                *axis.texts,
            ):
                label.set_color(text)
            for spine in axis.spines.values():
                spine.set_color(border)
            for gridline in (
                *axis.get_xgridlines(),
                *axis.get_ygridlines(),
            ):
                gridline.set_color(border)
            legend = axis.get_legend()
            if legend is not None:
                legend.get_frame().set_facecolor(surface)
                legend.get_frame().set_edgecolor(border)
                for label in legend.get_texts():
                    label.set_color(text)

        theme_signature = (
            getattr(self.app, "current_theme_name", ""),
            len(figure.axes),
        )
        canvas._forced_theme_signature = theme_signature
        if not hasattr(canvas, "_forced_theme_draw_connection"):
            canvas._forced_theme_draw_connection = canvas.mpl_connect(
                "draw_event",
                lambda event, target=canvas:
                self._force_chart_after_redraw(target),
            )
        if redraw:
            canvas._forced_theme_draw_guard = True
            canvas.draw_idle()

    def _force_chart_after_redraw(self, canvas):
        if not self.force_theme:
            return
        if getattr(canvas, "_forced_theme_draw_guard", False):
            canvas._forced_theme_draw_guard = False
            return
        name = getattr(self.app, "current_theme_name", "")
        colors = THEMES.get(name)
        if not colors:
            return
        self._force_chart_theme(canvas, colors, redraw=False)
        canvas._forced_theme_draw_guard = True
        canvas.draw_idle()

    def _restore_forced_theme(self):
        for widget, original_style in self._forced_widget_styles.values():
            try:
                widget.setStyleSheet(original_style)
            except RuntimeError:
                pass
        self._forced_widget_styles.clear()
        self._forced_window_signatures.clear()

        for canvas, figure_color, axes_state in self._forced_chart_states.values():
            try:
                figure = canvas.figure
                figure.set_facecolor(figure_color)
                for axis, facecolor, text_states, spine_states in axes_state:
                    axis.set_facecolor(facecolor)
                    for artist, color in text_states:
                        artist.set_color(color)
                    for spine, color in spine_states:
                        spine.set_color(color)
                canvas._forced_theme_signature = None
                canvas.draw_idle()
            except (RuntimeError, AttributeError):
                pass
        self._forced_chart_states.clear()

    def get_dither_options(self, name):
        theme = THEMES.get(name, {})
        supported = bool(
            RETRO_RUNTIME is not None
            and theme.get("color_map_options", False)
        )
        default_enabled = bool(theme.get("dithered") or theme.get("color_map"))
        prefix = f"theme_options/{name}"
        if not supported:
            return {
                "enabled": False,
                "color_count": self.dither_color_count,
                "thumbnails": False,
                "opened_pictures": False,
            }
        return {
            "enabled": self.settings.value(
                f"{prefix}/enabled", default_enabled, type=bool
            ),
            "color_count": max(
                2,
                min(
                    256,
                    self.settings.value(
                        f"{prefix}/color_count",
                        self.dither_color_count,
                        type=int,
                    ),
                ),
            ),
            "thumbnails": self.settings.value(
                f"{prefix}/thumbnails",
                bool(theme.get("dither_thumbnails")),
                type=bool,
            ),
            "opened_pictures": self.settings.value(
                f"{prefix}/opened_pictures", False, type=bool
            ),
        }

    def apply_dither_settings(
        self,
        name,
        color_count,
        enabled,
        thumbnails,
        opened_pictures,
    ):
        if not THEMES.get(name, {}).get("color_map_options"):
            return
        color_count = max(2, min(256, int(color_count)))
        prefix = f"theme_options/{name}"
        self.settings.setValue(f"{prefix}/enabled", bool(enabled))
        self.settings.setValue(f"{prefix}/color_count", color_count)
        self.settings.setValue(f"{prefix}/thumbnails", bool(thumbnails))
        self.settings.setValue(
            f"{prefix}/opened_pictures", bool(opened_pictures)
        )
        self.settings.setValue("dither_color_count", color_count)

        if getattr(self.app, "current_theme_name", "") == name:
            self._style_epoch += 1
            self.dither_color_count = color_count
            self._refresh_widget_overrides()
            self._restore_thumbnails()
            self._restore_opened_pictures()
            self._sync_effect_timers()

    def _sync_effect_timers(self):
        current = getattr(self.app, "current_theme_name", "")
        options = self.get_dither_options(current)
        use_thumbnails = options["enabled"] and options["thumbnails"]
        use_opened_pictures = (
            options["enabled"] and options["opened_pictures"]
        )

        if use_thumbnails:
            self._thumbnail_timer.start()
            QTimer.singleShot(0, self._refresh_thumbnails)
        else:
            self._thumbnail_timer.stop()
            self._restore_thumbnails()

        if use_opened_pictures:
            self._picture_timer.start()
            QTimer.singleShot(0, self._refresh_opened_pictures)
        else:
            self._picture_timer.stop()
            self._restore_opened_pictures()

    def _refresh_widget_overrides(self, root=None):
        """Apply small inline overrides that cannot be expressed by host QSS."""
        if root is not None:
            try:
                root.objectName()
            except RuntimeError:
                return
        if root is None:
            self._prune_dead_widget_references()
        current_name = getattr(self.app, "current_theme_name", "")
        theme = THEMES.get(current_name, {})
        mode = self._theme_override_mode(theme)
        palette_kind = theme.get("color_map_kind", "xp")
        use_color_map = self.get_dither_options(current_name)["enabled"]
        self.win31.refresh_readability(mode == "win31", root)
        if root is None:
            self.win31.refresh_autocomplete()
        self.metro.refresh_groups(mode == "metro", root)
        self._refresh_button_overrides(
            mode,
            use_color_map,
            palette_kind,
            root,
        )
        self.xp_classic.refresh_widget_roles(mode == "xpclassic", root)
        if root is None:
            self._refresh_stats_override(mode)

    def _prune_dead_widget_references(self):
        """Drop Qt wrappers whose C++ widgets were already destroyed."""
        mappings = (
            self._button_styles,
            self._label_styles,
            self._control_styles,
            self._rich_text_states,
            self._autocomplete_styles,
            self._forced_widget_styles,
            self._forced_chart_states,
        )
        for mapping in mappings:
            for key, state in list(mapping.items()):
                widget = state[0]
                try:
                    widget.objectName()
                except RuntimeError:
                    del mapping[key]

    @staticmethod
    def _theme_override_mode(theme):
        for mode in (
            "dithered",
            "aero",
            "metro",
            "win31",
            "xpclassic",
        ):
            flag = "xp_classic" if mode == "xpclassic" else mode
            if theme.get(flag, False):
                return mode
        return "default"

    def _refresh_button_overrides(
        self,
        mode,
        use_color_map,
        palette_kind,
        root=None,
    ):
        needs_override = (
            mode in BUTTON_OVERRIDE_STYLES
            or mode == "metro"
            or use_color_map
        )
        if not needs_override and not self._button_overrides_active:
            return
        if needs_override:
            self._button_overrides_active = True
        owner = root or self.app
        buttons = owner.findChildren(QPushButton)
        if isinstance(owner, QPushButton):
            buttons.insert(0, owner)
        for button_index, button in enumerate(buttons):
            if button.property("tutorialManagedStyle"):
                continue
            key = id(button)
            if key not in self._button_styles:
                self._button_styles[key] = (
                    button,
                    button.styleSheet(),
                    button.text(),
                    button.icon(),
                    button.iconSize(),
                )

            (
                _,
                original_style,
                original_text,
                original_icon,
                original_icon_size,
            ) = self._button_styles[key]
            first_part, separator, remaining_text = original_text.partition(" ")
            has_symbol = any(ord(char) >= 0x2300 for char in first_part)
            signature = "|".join(
                (
                    str(self._style_epoch),
                    mode,
                    str(button_index if mode == "metro" else -1),
                    str(int(use_color_map)),
                    str(self.dither_color_count if use_color_map else 0),
                    palette_kind,
                    str(int(has_symbol)),
                )
            )
            if button.property("_themeSwitcherSignature") == signature:
                continue

            button.setProperty("emojiButton", has_symbol)
            button.setText(original_text)
            button.setIcon(original_icon)
            button.setIconSize(original_icon_size)

            if mode in BUTTON_OVERRIDE_STYLES:
                button.setStyleSheet(BUTTON_OVERRIDE_STYLES[mode])
            elif mode == "metro":
                button.setStyleSheet(
                    self.metro.style_for_button(button_index)
                )
            else:
                button.setStyleSheet(original_style)

            if use_color_map and has_symbol:
                button.setText(remaining_text if separator else original_text)
                button.setIcon(
                    RETRO_RUNTIME.dithered_emoji_icon(
                        first_part,
                        self.dither_color_count,
                        palette_kind,
                    )
                )
                button.setIconSize(QSize(20, 20))

            button.setProperty("_themeSwitcherSignature", signature)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        if not needs_override and root is None:
            self._button_overrides_active = False
            self._button_styles.clear()

    def _refresh_stats_override(self, mode):
        if not hasattr(self.app, "lbl_stats"):
            return
        desired = STATS_OVERRIDE_STYLES.get(mode, self._stats_style)
        if self.app.lbl_stats.styleSheet() != desired:
            self.app.lbl_stats.setStyleSheet(desired)

    def _refresh_thumbnails(self):
        """Dither newly loaded ThumbnailWidget pixmaps without touching source data."""
        current_name = getattr(self.app, "current_theme_name", "")
        current_theme = THEMES.get(current_name, {})
        options = self.get_dither_options(current_name)
        if not (options["enabled"] and options["thumbnails"]):
            return
        palette_kind = current_theme.get("color_map_kind", "xp")

        labels = [
            label
            for label in self.app.findChildren(QLabel)
            if label.__class__.__name__ == "ThumbnailWidget"
        ]
        active_ids = {id(label) for label in labels}
        for key in list(self._thumbnail_states):
            if key not in active_ids:
                del self._thumbnail_states[key]

        # Limit work per timer tick. Previously all 100 thumbnails could be
        # quantized in one GUI-thread burst, which made the app look frozen.
        processed_this_tick = 0
        for label in labels:
            key = id(label)
            pixmap = label.pixmap()
            if pixmap is None or pixmap.isNull():
                continue

            state = self._thumbnail_states.get(key)
            if state is not None and pixmap.cacheKey() == state[2]:
                continue

            original = QPixmap(pixmap)
            processed = RETRO_RUNTIME.dithered_thumbnail(
                original,
                self.dither_color_count,
                palette_kind,
            )
            label.setPixmap(processed)
            self._thumbnail_states[key] = (label, original, processed.cacheKey())
            processed_this_tick += 1
            if processed_this_tick >= 2:
                break

    def _restore_thumbnails(self):
        """Restore cached full-color pixmaps when leaving the thumbnail theme."""
        for label, original, _ in self._thumbnail_states.values():
            try:
                label.setPixmap(original)
            except RuntimeError:
                pass
        self._thumbnail_states.clear()

    def _refresh_opened_pictures(self):
        """Dither full pictures loaded by ImageViewerDialog."""
        current_name = getattr(self.app, "current_theme_name", "")
        current_theme = THEMES.get(current_name, {})
        options = self.get_dither_options(current_name)
        if not (options["enabled"] and options["opened_pictures"]):
            return
        palette_kind = current_theme.get("color_map_kind", "xp")

        active_ids = set()
        for viewer in QApplication.topLevelWidgets():
            if viewer.__class__.__name__ != "ImageViewerDialog":
                continue
            key = id(viewer)
            active_ids.add(key)
            pixmap = getattr(viewer, "original_pixmap", None)
            if pixmap is None or pixmap.isNull():
                continue

            state = self._picture_states.get(key)
            if state is not None and pixmap.cacheKey() == state[2]:
                continue

            original = QPixmap(pixmap)
            processing_source = original
            max_resolution = self.full_image_max_resolution
            if (
                max_resolution > 0
                and max(original.width(), original.height()) > max_resolution
            ):
                processing_source = original.scaled(
                    max_resolution,
                    max_resolution,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            processed = RETRO_RUNTIME.dithered_picture(
                processing_source,
                self.dither_color_count,
                palette_kind,
            )
            viewer.original_pixmap = processed
            self._picture_states[key] = (
                viewer,
                original,
                processed.cacheKey(),
            )
            self._render_viewer_with_sharp_pixels(viewer)

        for key in list(self._picture_states):
            if key not in active_ids:
                del self._picture_states[key]

    def _restore_opened_pictures(self):
        """Put full-color images back into every open picture viewer."""
        for viewer, original, _ in self._picture_states.values():
            try:
                viewer.original_pixmap = original
                viewer.update_image()
            except RuntimeError:
                pass
        self._picture_states.clear()

    def _render_viewer_with_sharp_pixels(self, viewer):
        """Use nearest-neighbor scaling for an actively dithered picture."""
        state = self._picture_states.get(id(viewer))
        if state is None:
            return
        pixmap = getattr(viewer, "original_pixmap", None)
        label = getattr(viewer, "image_label", None)
        if (
            pixmap is None
            or pixmap.isNull()
            or label is None
            or pixmap.cacheKey() != state[2]
        ):
            return
        try:
            label.setPixmap(
                pixmap.scaled(
                    label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            )
        except RuntimeError:
            pass

    def set_dither_color_count(self, value):
        """Persist and immediately re-render color-mapped theme assets."""
        value = max(2, min(256, int(value)))
        current_name = getattr(self.app, "current_theme_name", "")
        options = self.get_dither_options(current_name)
        self.apply_dither_settings(
            current_name,
            value,
            options["enabled"],
            options["thumbnails"],
            options["opened_pictures"],
        )

    def open_dialog(self):
        if self.dialog is None:
            self.dialog = ThemeDialog(self.app, self)
            self.dialog.finished.connect(self._dialog_closed)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _dialog_closed(self):
        self.dialog = None


def setup(app):
    switcher = ThemeSwitcher(app)
    if not hasattr(app, "loaded_plugins"):
        app.loaded_plugins = []
    app.loaded_plugins.append(switcher)
    app.theme_switcher_extension = switcher
