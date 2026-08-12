"""First-run, replayable guided tour for StatBooru.

This extension intentionally depends only on the public ``app`` attributes/API
already exposed by main.py. It stores its completion flag alongside the lesson
files in ``extension_tutorials/``; it does not use the Windows Registry.
Extension-specific lessons are loaded dynamically so they can be maintained
independently.
"""

import importlib.util
import json
from pathlib import Path

from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QApplication,
    QDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


TUTORIAL_VERSION = 3
TUTORIAL_STATE_KEY = "welcome_tutorial_completed_version"

# Main instructions and More Info content. Titles are automatically larger.
TUTORIAL_TEXT_SIZE = 16
# Navigation buttons use the program's original, more compact text size.
TUTORIAL_BUTTON_TEXT_SIZE = 13
# Maximum More Info speech-bubble size on larger windows.
TUTORIAL_BUBBLE_MAX_WIDTH = 640
TUTORIAL_BUBBLE_MAX_HEIGHT = 500


def load_theme_color_catalog():
    """Read the same color tokens used by the optional theme extension."""
    catalog = {}
    theme_folder = Path(__file__).resolve().parent / "themes"
    for path in theme_folder.glob("*.json"):
        try:
            definition = json.loads(path.read_text(encoding="utf-8"))
            name = definition.get("name")
            if name:
                catalog[name] = definition
        except (OSError, ValueError, TypeError):
            continue
    return catalog


THEME_COLORS = load_theme_color_catalog()
TUTORIAL_FOLDER = Path(__file__).resolve().parent / "extension_tutorials"
TUTORIAL_STATE_FILE = TUTORIAL_FOLDER / "tutorial_state.json"
MASCOT_FOLDER = TUTORIAL_FOLDER / "mascot"


def load_tutorial_state():
    """Load portable tutorial state without touching platform settings."""
    try:
        state = json.loads(TUTORIAL_STATE_FILE.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def completed_tutorial_version():
    try:
        return int(load_tutorial_state().get(TUTORIAL_STATE_KEY, 0))
    except (TypeError, ValueError):
        return 0


def save_completed_tutorial_version(version):
    """Atomically save completion state beside the extension tutorials."""
    state = load_tutorial_state()
    state[TUTORIAL_STATE_KEY] = int(version)
    temporary = TUTORIAL_STATE_FILE.with_suffix(".tmp")
    try:
        TUTORIAL_FOLDER.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(TUTORIAL_STATE_FILE)
        return True
    except OSError as exc:
        print(f"Could not save tutorial completion state: {exc}")
        return False


class MascotInfoPanel(QWidget):
    """Responsive Clippy-style mascot and speech bubble for extra context."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tutorialMascotPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.surface = QColor("#ffffff")
        self.text_color = QColor("#111111")
        self.accent = QColor("#2b72d6")
        self.border = QColor("#2b72d6")
        self.square = False
        self.bubble_rect = QRect()
        self.floor_y = None
        self._mouth_ratio = (0.515, 0.335)

        self.title_label = QLabel(self)
        title_font = QFont()
        title_font.setPointSize(TUTORIAL_TEXT_SIZE + 2)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)

        self.info_label = QTextBrowser(self)
        self.info_label.setOpenExternalLinks(False)
        self.info_label.setFrameStyle(0)
        self.info_label.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.close_button = QPushButton("Got it", self)
        self.close_button.setMinimumWidth(86)

        self.mascot_label = QLabel(self)
        self.mascot_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        )
        self.mascot_label.setStyleSheet("background: transparent; border: none;")
        self._original_pixmap = QPixmap()

        for widget in (self, *self.findChildren(QWidget)):
            widget.setProperty("tutorialManagedStyle", True)

    def set_content(self, title, html, page_index=0):
        self.title_label.setText(title)
        self.info_label.setHtml(html)
        pose = "RMQ2_1.png" if page_index == 0 else "RMQ2.png"
        # Both mascot poses use the same face location to within a few pixels.
        # Keep this explicit so the speech-tail tip follows the mouth after any
        # responsive scaling instead of pointing at the image's center.
        self._mouth_ratio = (
            (0.515, 0.335) if pose == "RMQ2_1.png" else (0.515, 0.33)
        )
        pixmap = QPixmap(str(MASCOT_FOLDER / pose))
        if pixmap.isNull():
            pixmap = QPixmap(str(MASCOT_FOLDER / "RMQ2.png"))
        self._original_pixmap = pixmap
        self.relayout()

    def set_floor_y(self, floor_y=None):
        """Set the y coordinate the mascot must stand directly above."""
        self.floor_y = floor_y
        self.relayout()

    def set_theme(self, surface, surface_alt, text, accent, border, square):
        self.surface = QColor(surface_alt if surface_alt.isValid() else surface)
        self.text_color = QColor(text)
        self.accent = QColor(accent)
        self.border = QColor(border)
        self.square = bool(square)
        radius = 0 if square else 7
        label_style = (
            f"color: {text.name()}; background: transparent; border: none;"
        )
        self.title_label.setStyleSheet(label_style + " font-weight: bold;")
        self.info_label.setStyleSheet(
            label_style
            + f" font-size: {TUTORIAL_TEXT_SIZE}px; padding: 0px; "
            "selection-background-color: "
            + accent.name()
            + ";"
        )
        hover = surface.lighter(112) if surface.lightness() < 150 else surface.darker(108)
        pressed = hover.darker(110) if hover.lightness() >= 80 else hover.lighter(110)
        self.close_button.setStyleSheet(
            f"QPushButton {{ min-height: 32px; padding: 3px 14px; "
            f"border-radius: {radius}px; background: {surface.name()}; "
            f"color: {text.name()}; border: 1px solid {border.name()}; "
            f"font-size: {TUTORIAL_BUTTON_TEXT_SIZE}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {hover.name()}; "
            f"color: {text.name()}; }}"
            f"QPushButton:pressed {{ background: {pressed.name()}; "
            f"color: {text.name()}; }}"
        )
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.relayout()

    def relayout(self):
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        margin = max(12, min(28, width // 35))
        floor = height - margin if self.floor_y is None else int(self.floor_y)
        floor = max(margin + 180, min(height, floor))
        usable_height = max(180, floor - margin)
        wide = width >= 680

        source_w = self._original_pixmap.width() or 156
        source_h = self._original_pixmap.height() or 238
        if wide:
            available_mascot_w = max(80, width // 3)
            available_mascot_h = usable_height
        else:
            available_mascot_w = max(80, width - margin * 2)
            # Reserve a useful speech area above the mascot on stacked layouts.
            available_mascot_h = max(80, floor - margin - 164)

        # Pixel art stays at its exact 1x source resolution whenever possible.
        # Very small windows use only nearest-neighbor reductions; the mascot
        # is never enlarged to a fractional size.
        mascot_scale = 1.0
        for candidate in (1.0, 0.5, 0.25):
            if (
                source_w * candidate <= available_mascot_w
                and source_h * candidate <= available_mascot_h
            ):
                mascot_scale = candidate
                break

        mascot_w = max(1, round(source_w * mascot_scale))
        mascot_h = max(1, round(source_h * mascot_scale))
        self._rendered_scale = mascot_scale

        if wide:
            mascot_x = width - mascot_w - margin
            mascot_y = floor - mascot_h
            bubble_right = mascot_x - 16
            bubble_w = min(
                TUTORIAL_BUBBLE_MAX_WIDTH,
                max(320, bubble_right - margin),
            )
            bubble_h = min(
                TUTORIAL_BUBBLE_MAX_HEIGHT,
                max(180, usable_height),
            )
            bubble_x = max(margin, bubble_right - bubble_w)
            bubble_y = max(margin, (floor - bubble_h) // 2)
        else:
            mascot_x = width - mascot_w - margin
            mascot_y = floor - mascot_h
            bubble_x = margin
            bubble_y = margin
            bubble_w = max(160, width - margin * 2)
            bubble_h = max(150, mascot_y - bubble_y - 14)

        self.bubble_rect = QRect(bubble_x, bubble_y, bubble_w, bubble_h)
        self.mascot_label.setGeometry(mascot_x, mascot_y, mascot_w, mascot_h)
        if not self._original_pixmap.isNull():
            if mascot_scale == 1.0:
                rendered = self._original_pixmap
            else:
                rendered = self._original_pixmap.scaled(
                    mascot_w,
                    mascot_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
            self.mascot_label.setPixmap(rendered)

        content = self.bubble_rect.adjusted(24, 18, -24, -18)
        title_h = min(52, max(30, self.title_label.sizeHint().height()))
        button_h = 38
        self.title_label.setGeometry(content.x(), content.y(), content.width(), title_h)
        self.close_button.setGeometry(
            content.right() - 86,
            content.bottom() - button_h,
            86,
            button_h,
        )
        self.info_label.setGeometry(
            content.x(),
            content.y() + title_h + 8,
            content.width(),
            max(50, content.height() - title_h - button_h - 20),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.bubble_rect.isValid():
            return

        # Even square-edged application themes keep a small balloon curve; the
        # controls remain theme-correct while this still reads as speech.
        radius = 10 if self.square else 18
        mouth = self.mascot_mouth_point()
        rect = QRectF(self.bubble_rect)
        left, top, right, bottom = (
            rect.left(),
            rect.top(),
            rect.right(),
            rect.bottom(),
        )
        base_right_x = right - max(18.0, radius)
        base_left_x = base_right_x - 32.0
        base_center = QPointF((base_left_x + base_right_x) / 2.0, bottom)
        tip = self.mascot_silhouette_tip(base_center, mouth)

        # Build the rounded box and triangular pointer as one outline. This
        # deliberately omits the box line between the two tail base points, so
        # there is no seam running through the speech bubble.
        bubble_path = QPainterPath(QPointF(left + radius, top))
        bubble_path.lineTo(right - radius, top)
        bubble_path.quadTo(QPointF(right, top), QPointF(right, top + radius))
        bubble_path.lineTo(right, bottom - radius)
        bubble_path.quadTo(
            QPointF(right, bottom), QPointF(right - radius, bottom)
        )
        bubble_path.lineTo(base_right_x, bottom)
        bubble_path.lineTo(tip)
        bubble_path.lineTo(base_left_x, bottom)
        bubble_path.lineTo(left + radius, bottom)
        bubble_path.quadTo(
            QPointF(left, bottom), QPointF(left, bottom - radius)
        )
        bubble_path.lineTo(left, top + radius)
        bubble_path.quadTo(QPointF(left, top), QPointF(left + radius, top))
        bubble_path.closeSubpath()

        painter.fillPath(bubble_path, self.surface)
        outline = QPen(self.border, 2)
        outline.setCapStyle(Qt.PenCapStyle.RoundCap)
        outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline)
        painter.drawPath(bubble_path)

    def mascot_mouth_point(self):
        """Return the rendered mascot mouth in panel coordinates."""
        label_rect = self.mascot_label.geometry()
        pixmap = self.mascot_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return QPointF(label_rect.center())

        pixmap_x = label_rect.x() + (label_rect.width() - pixmap.width()) / 2
        pixmap_y = label_rect.bottom() + 1 - pixmap.height()
        return QPointF(
            pixmap_x + pixmap.width() * self._mouth_ratio[0],
            pixmap_y + pixmap.height() * self._mouth_ratio[1],
        )

    def mascot_silhouette_tip(self, start, mouth):
        """Stop the pointer at the mascot silhouette on its way to the mouth."""
        label_rect = self.mascot_label.geometry()
        pixmap = self.mascot_label.pixmap()
        if pixmap is None or pixmap.isNull():
            return mouth

        image = pixmap.toImage()
        pixmap_x = label_rect.x() + (label_rect.width() - pixmap.width()) / 2
        pixmap_y = label_rect.bottom() + 1 - pixmap.height()
        delta_x = mouth.x() - start.x()
        delta_y = mouth.y() - start.y()
        steps = max(1, int(max(abs(delta_x), abs(delta_y)) * 2))
        previous = QPointF(start)
        for step in range(1, steps + 1):
            amount = step / steps
            point = QPointF(
                start.x() + delta_x * amount,
                start.y() + delta_y * amount,
            )
            image_x = int(point.x() - pixmap_x)
            image_y = int(point.y() - pixmap_y)
            if (
                0 <= image_x < image.width()
                and 0 <= image_y < image.height()
                and image.pixelColor(image_x, image_y).alpha() > 32
            ):
                return previous
            previous = point
        return mouth



class TutorialOverlay(QWidget):
    """A dimmed overlay with a spotlight around the control being explained."""

    def __init__(self, app, pages, on_finished):
        container = app.centralWidget() if hasattr(app, "centralWidget") else None
        self.container = container or app
        super().__init__(self.container)
        self.app = app
        self.pages = pages
        self.on_finished = on_finished
        self.index = 0
        self._finishing = False
        self.target_rect = QRect()
        self.target_rects = []
        self.accent_color = QColor("#89b4fa")
        self.card_surface_color = QColor("#20222b")
        self.card_border_color = QColor("#89b4fa")
        self.classic_win31 = False
        self.card_radius = 14
        self.shade_alpha = 145

        self.setObjectName("welcomeTutorialOverlay")
        # The main application applies a dark background to every QWidget.
        # Explicit translucency prevents that global rule from turning the
        # spotlight hole into an opaque black rectangle.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            "QWidget#welcomeTutorialOverlay { background: transparent; border: none; }"
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.container.installEventFilter(self)
        self.app.installEventFilter(self)

        self.card = QWidget(self)
        self.card.setObjectName("tutorialCard")
        # The overlay paints the card panel itself. This prevents aggressive
        # theme engines from clearing or replacing its background.
        self.card.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.card.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.card.setAutoFillBackground(False)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(10)

        self.step_label = QLabel()
        self.step_label.setObjectName("tutorialStep")
        layout.addWidget(self.step_label)

        self.title_label = QLabel()
        title_font = QFont()
        title_font.setPointSize(TUTORIAL_TEXT_SIZE + 3)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setTextFormat(Qt.TextFormat.RichText)
        self.body_label.setOpenExternalLinks(False)
        self.body_label.setStyleSheet(
            f"font-size: {TUTORIAL_TEXT_SIZE}px; line-height: 1.35;"
        )
        layout.addWidget(self.body_label, 1)

        nav = QHBoxLayout()
        self.skip_button = QPushButton("Skip tutorial")
        self.skip_button.setObjectName("tutorialSkip")
        self.skip_button.clicked.connect(self.finish)
        nav.addWidget(self.skip_button)
        self.more_info_button = QPushButton("More info on this topic")
        self.more_info_button.setObjectName("tutorialMoreInfo")
        self.more_info_button.setToolTip(
            "Ask the tutorial mascot for more information about this topic"
        )
        self.more_info_button.clicked.connect(self.show_more_info)
        nav.addWidget(self.more_info_button)
        nav.addStretch()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.previous)
        nav.addWidget(self.back_button)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("tutorialNext")
        self.next_button.clicked.connect(self.next)
        nav.addWidget(self.next_button)
        layout.addLayout(nav)

        # ThemeSwitcher deliberately leaves this subtree alone. The tutorial
        # owns these styles because it must preserve contrast over an overlay.
        self.setProperty("tutorialManagedStyle", True)
        self.card.setProperty("tutorialManagedStyle", True)
        for widget in self.card.findChildren(QWidget):
            widget.setProperty("tutorialManagedStyle", True)

        self.info_panel = MascotInfoPanel(self)
        self.info_panel.close_button.clicked.connect(self.close_more_info)
        self.info_panel.hide()

        self.update_theme()
        self.sync_to_visible_window()
        self.show()
        self.raise_()
        self.setFocus()
        self.show_page()

    def eventFilter(self, watched, event):
        if watched in (self.app, self.container) and event.type() in (
            QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show
        ):
            # Wait until Qt has completed the corresponding layout pass.
            QTimer.singleShot(0, self.refresh_geometry)
        elif watched in (self.app, self.container) and event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationPaletteChange,
        ):
            QTimer.singleShot(0, self.update_theme)
        return super().eventFilter(watched, event)

    def active_theme_name(self):
        widget = self.app
        while widget is not None:
            name = getattr(widget, "current_theme_name", "")
            if name:
                return name
            widget = widget.parentWidget()
        return ""

    def update_theme(self):
        """Derive tutorial colors and geometry from the current Qt theme."""
        # Some extensions use an instance attribute named ``palette`` for
        # chart colors, shadowing QWidget.palette(). Call the Qt method through
        # its class so those dialogs cannot crash tutorial startup.
        palette = QWidget.palette(self.container)
        surface = palette.color(QPalette.ColorRole.Window)
        surface_alt = palette.color(QPalette.ColorRole.AlternateBase)
        text = palette.color(QPalette.ColorRole.WindowText)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        accent = palette.color(QPalette.ColorRole.Highlight)
        accent_text = palette.color(QPalette.ColorRole.HighlightedText)
        button = palette.color(QPalette.ColorRole.Button)
        button_text = palette.color(QPalette.ColorRole.ButtonText)
        border = palette.color(QPalette.ColorRole.Mid)

        # Some stylesheet-only themes leave one or more palette roles at the
        # platform default. Link is a useful theme-aware accent fallback.
        if accent == surface or accent.alpha() == 0:
            accent = palette.color(QPalette.ColorRole.Link)
        if surface_alt.alpha() == 0:
            surface_alt = surface
        if muted.alpha() == 0:
            muted = text

        active_theme = self.active_theme_name()
        # The built-in main stylesheet has no ``current_theme_name`` attribute.
        # Its colors are the Original Catppuccin palette, so use that catalog
        # entry instead of unreliable platform palette roles (which can report
        # a white Button surface with light ButtonText on Windows).
        definition = THEME_COLORS.get(active_theme) or THEME_COLORS.get(
            "Original (Catppuccin)", {}
        )

        def theme_color(key, fallback):
            candidate = QColor(definition.get(key, ""))
            return candidate if candidate.isValid() else fallback

        surface = theme_color("surface", surface)
        surface_alt = theme_color("surface_alt", surface_alt)
        text = theme_color("text", text)
        muted = theme_color("muted", muted)
        accent = theme_color("accent", accent)
        accent_text = theme_color("accent_text", accent_text)
        button = surface_alt
        button_text = text
        border = theme_color("border", border)

        theme_name = active_theme.lower()
        classic_win31 = "windows 3.1" in theme_name
        if classic_win31:
            button = surface
        square = any(
            marker in theme_name
            for marker in ("windows 3.1", "windows 8", "8-bit", "dithered")
        )
        card_radius = 0 if square else 14
        button_radius = 0 if square else 6
        hover = button.lighter(112) if button.lightness() < 150 else button.darker(108)
        pressed = hover.darker(110) if hover.lightness() >= 80 else hover.lighter(110)
        disabled_button = (
            button.darker(112) if button.lightness() >= 80 else button.lighter(108)
        )
        disabled_text = muted
        accent_hover = theme_color(
            "accent_hover",
            accent.lighter(112) if accent.lightness() < 150 else accent.darker(108),
        )
        accent_pressed = (
            accent_hover.darker(110)
            if accent_hover.lightness() >= 80
            else accent_hover.lighter(110)
        )

        self.accent_color = QColor(accent)
        self.card_surface_color = QColor(surface)
        self.card_border_color = QColor(border if square else accent)
        self.classic_win31 = classic_win31
        self.card_radius = card_radius
        self.shade_alpha = 105 if surface.lightness() >= 145 else 145
        step_color = accent_text if self.classic_win31 else accent
        self.card.setStyleSheet(
            f"""
            QWidget#tutorialCard {{
                background: transparent;
                color: {text.name()};
                border: none;
            }}
            QWidget#tutorialCard QLabel {{
                color: {text.name()};
                background: transparent;
                border: none;
            }}
            QLabel#tutorialStep {{
                color: {step_color.name()};
                font-size: {max(11, TUTORIAL_TEXT_SIZE - 2)}px;
                font-weight: bold;
            }}
            QWidget#tutorialCard QPushButton {{
                min-height: 34px;
                padding: 4px 14px;
                font-size: {TUTORIAL_BUTTON_TEXT_SIZE}px;
                border-radius: {button_radius}px;
                background: {button.name()};
                color: {button_text.name()};
                border: 1px solid {border.name()};
            }}
            QWidget#tutorialCard QPushButton:hover {{
                background: {hover.name()};
            }}
            QWidget#tutorialCard QPushButton:pressed {{
                background: {pressed.name()};
                color: {button_text.name()};
            }}
            QWidget#tutorialCard QPushButton:disabled {{
                background: {disabled_button.name()};
                color: {disabled_text.name()};
                border-color: {border.name()};
            }}
            QPushButton#tutorialNext {{
                background: {accent.name()};
                color: {accent_text.name()};
                font-weight: bold;
            }}
            QPushButton#tutorialNext:hover {{
                background: {accent_hover.name()};
                color: {accent_text.name()};
            }}
            QPushButton#tutorialSkip {{
                background: transparent;
                border: none;
                color: {muted.name()};
            }}
            """
        )
        label_style = (
            f"color: {text.name()}; background: transparent; border: none;"
        )
        self.title_label.setStyleSheet(label_style)
        self.body_label.setStyleSheet(
            label_style
            + f" font-size: {TUTORIAL_TEXT_SIZE}px; line-height: 1.35;"
        )
        self.step_label.setStyleSheet(
            f"color: {step_color.name()}; background: transparent; "
            f"border: none; font-size: {max(11, TUTORIAL_TEXT_SIZE - 2)}px; "
            "font-weight: bold;"
        )
        common_button_style = (
            f"QPushButton {{ min-height: 34px; padding: 4px 14px; "
            f"font-size: {TUTORIAL_BUTTON_TEXT_SIZE}px; "
            f"border-radius: {button_radius}px; background: {button.name()}; "
            f"color: {button_text.name()}; border: 1px solid {border.name()}; }}"
            f"QPushButton:hover {{ background: {hover.name()}; "
            f"color: {button_text.name()}; }}"
            f"QPushButton:pressed {{ background: {pressed.name()}; "
            f"color: {button_text.name()}; }}"
            f"QPushButton:disabled {{ background: {disabled_button.name()}; "
            f"color: {disabled_text.name()}; border-color: {border.name()}; }}"
        )
        self.back_button.setStyleSheet(common_button_style)
        self.skip_button.setStyleSheet(
            common_button_style if self.classic_win31 else (
                f"QPushButton {{ min-height: 34px; padding: 4px 14px; "
                f"font-size: {TUTORIAL_BUTTON_TEXT_SIZE}px; "
                f"background: transparent; color: {muted.name()}; border: none; }}"
                f"QPushButton:hover {{ background: {button.name()}; "
                f"color: {text.name()}; }}"
                f"QPushButton:pressed {{ background: {pressed.name()}; "
                f"color: {text.name()}; }}"
            )
        )
        self.next_button.setStyleSheet(
            f"QPushButton {{ min-height: 34px; padding: 4px 14px; "
            f"font-size: {TUTORIAL_BUTTON_TEXT_SIZE}px; "
            f"border-radius: {button_radius}px; background: {accent.name()}; "
            f"color: {accent_text.name()}; border: 1px solid {border.name()}; "
            "font-weight: bold; }"
            f"QPushButton:hover {{ background: {accent_hover.name()}; "
            f"color: {accent_text.name()}; }}"
            f"QPushButton:pressed {{ background: {accent_pressed.name()}; "
            f"color: {accent_text.name()}; }}"
        )
        self.more_info_button.setStyleSheet(common_button_style)
        self.info_panel.set_theme(
            surface, surface_alt, text, accent, border, square
        )
        self.card.update()
        self.update()

    def refresh_geometry(self):
        if not self.isVisible():
            return
        try:
            self.sync_to_visible_window()
            self.position_card()
            self.layout_info_panel()
            self.update()
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"Tutorial geometry refresh failed: {exc}")

    def info_floor_y(self):
        """Return the toolbar top in overlay coordinates when one is present."""
        layout = getattr(self.app, "ext_button_layout", None)
        if layout is None:
            return None

        visible_tops = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is None or not widget.isVisible():
                continue
            top = self.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0))).y()
            if self.height() // 2 < top <= self.height():
                visible_tops.append(top)
        # Button borders and the themed row background begin a few pixels above
        # the widget's reported content edge. This clearance keeps even
        # antialiased foot pixels completely off the bar.
        return min(visible_tops) - 7 if visible_tops else None

    def layout_info_panel(self):
        self.info_panel.setGeometry(self.rect())
        self.info_panel.set_floor_y(self.info_floor_y())

    def sync_to_visible_window(self):
        """Cover the part of the oversized app window that is on the monitor.

        The extension button row can give the main window a minimum width wider
        than the physical display. Using parent.rect() would center tutorial
        cards in that off-screen area.
        """
        parent = self.parentWidget()
        screen = self.app.screen()
        if screen is None:
            self.setGeometry(parent.rect())
            return
        parent_global = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
        visible_global = parent_global.intersected(screen.availableGeometry())
        if visible_global.isEmpty():
            self.setGeometry(parent.rect())
            return
        local_top_left = parent.mapFromGlobal(visible_global.topLeft())
        self.setGeometry(QRect(local_top_left, visible_global.size()))

    def target_widgets(self):
        target = self.pages[self.index].get("target")
        try:
            resolved = target() if callable(target) else target
            if isinstance(resolved, (list, tuple)):
                return [item for item in resolved if isinstance(item, QWidget)]
            return [resolved] if isinstance(resolved, QWidget) else []
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"Tutorial target resolution failed: {exc}")
            return []

    def target_widget(self):
        """Backward-compatible first target used by diagnostics."""
        targets = self.target_widgets()
        return targets[0] if targets else None

    def show_page(self):
        page = self.pages[self.index]
        self.update_theme()
        prepare = page.get("prepare")
        if callable(prepare):
            try:
                prepare()
            except (RuntimeError, AttributeError, TypeError) as exc:
                print(f"Tutorial page preparation failed: {exc}")
        self.step_label.setText(f"STEP {self.index + 1} OF {len(self.pages)}")
        self.title_label.setText(page["title"])
        self.body_label.setText(page["body"])
        self.back_button.setEnabled(self.index > 0)
        last = self.index == len(self.pages) - 1
        self.next_button.setText("Finish" if last else "Next")
        self.skip_button.setVisible(not last)
        self.more_info_button.setVisible(True)
        self.close_more_info()
        self.position_card()
        self.update()
        QTimer.singleShot(0, self.refresh_geometry)

    def position_card(self):
        if not self.pages:
            return
        targets = self.target_widgets()
        self.target_rect = QRect()
        self.target_rects = []
        for target in targets:
            if not target.isVisible():
                continue
            # Global coordinates safely bridge sibling widgets and DPI scaling.
            target_global = target.mapToGlobal(QPoint(0, 0))
            top_left = self.mapFromGlobal(target_global)
            candidate = QRect(top_left, target.size()).adjusted(-7, -7, 7, 7)
            # Do not draw misleading slivers for controls beyond the monitor.
            visible_part = candidate.intersected(self.rect())
            min_visible_width = min(40, candidate.width())
            min_visible_height = min(20, candidate.height())
            if (
                visible_part.width() >= min_visible_width
                and visible_part.height() >= min_visible_height
            ):
                self.target_rects.append(visible_part)
        for visible_rect in self.target_rects:
            self.target_rect = (
                visible_rect
                if self.target_rect.isNull()
                else self.target_rect.united(visible_rect)
            )

        margin = 22
        card_width = min(480, max(320, self.width() - margin * 2))
        self.card.setFixedWidth(card_width)
        self.card.adjustSize()
        card_height = min(self.card.sizeHint().height(), max(260, self.height() - margin * 2))
        self.card.resize(card_width, card_height)

        if self.target_rect.isValid():
            centered_x = self.target_rect.center().x() - card_width // 2
            centered_y = self.target_rect.center().y() - card_height // 2
            max_x = max(margin, self.width() - card_width - margin)
            max_y = max(margin, self.height() - card_height - margin)
            candidates = [
                (self.target_rect.right() + margin,
                 min(max(margin, centered_y), max_y)),
                (self.target_rect.left() - card_width - margin,
                 min(max(margin, centered_y), max_y)),
                (min(max(margin, centered_x), max_x),
                 self.target_rect.bottom() + margin),
                (min(max(margin, centered_x), max_x),
                 self.target_rect.top() - card_height - margin),
            ]
            # A large target (the results table in step 9, for example) can
            # leave no position that is both on-screen and outside the target.
            # Clamp every option into the viewport before scoring it. This
            # guarantees the card stays visible, then minimizes unavoidable
            # overlap with the highlighted control.
            candidates = [
                (
                    min(max(margin, raw_x), max_x),
                    min(max(margin, raw_y), max_y),
                )
                for raw_x, raw_y in candidates
            ]
            x, y = min(
                candidates,
                key=lambda pos: (
                    QRect(pos[0], pos[1], card_width, card_height).intersected(
                        self.target_rect
                    ).width()
                    * QRect(pos[0], pos[1], card_width, card_height).intersected(
                        self.target_rect
                    ).height(),
                ),
            )
        else:
            x = max(margin, (self.width() - card_width) // 2)
            y = max(margin, (self.height() - card_height) // 2)
        self.card.move(x, y)
        self.card.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        if self.target_rects:
            for target_rect in self.target_rects:
                hole = QPainterPath()
                hole.addRoundedRect(QRectF(target_rect), 9, 9)
                shade = shade.subtracted(hole)
        # Keep the rest of the program visible enough for the user to retain
        # context, while the subtracted target area remains fully transparent.
        painter.fillPath(shade, QColor(0, 0, 0, self.shade_alpha))
        if self.target_rects:
            painter.setPen(QPen(self.accent_color, 3))
            for target_rect in self.target_rects:
                painter.drawRoundedRect(target_rect, 9, 9)

        # Paint the card after the spotlight so neither the transparent hole
        # nor its outline can show through a card that overlaps a large target.
        card_rect = self.card.geometry()
        if self.card.isVisible() and card_rect.isValid():
            painter.save()
            if self.classic_win31:
                painter.fillRect(card_rect, self.card_surface_color)
                painter.setPen(QPen(QColor("#000000"), 2))
                painter.drawRect(card_rect.adjusted(0, 0, -1, -1))

                inner = card_rect.adjusted(3, 3, -3, -3)
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawLine(inner.topLeft(), inner.topRight())
                painter.drawLine(inner.topLeft(), inner.bottomLeft())
                painter.setPen(QPen(QColor("#606060"), 2))
                painter.drawLine(inner.bottomLeft(), inner.bottomRight())
                painter.drawLine(inner.topRight(), inner.bottomRight())

                title_bar = QRect(
                    card_rect.x() + 5,
                    card_rect.y() + 5,
                    max(0, card_rect.width() - 10),
                    36,
                )
                painter.fillRect(title_bar, self.accent_color)
            else:
                card_path = QPainterPath()
                card_path.addRoundedRect(
                    QRectF(card_rect), self.card_radius, self.card_radius
                )
                painter.fillPath(card_path, self.card_surface_color)
                painter.setPen(QPen(self.card_border_color, 2))
                painter.drawPath(card_path)
            painter.restore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.info_panel.isVisible():
            self.close_more_info()
            return
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.next()
        elif event.key() == Qt.Key.Key_Left:
            self.previous()
        elif event.key() == Qt.Key.Key_Escape:
            self.finish()
        else:
            super().keyPressEvent(event)

    def more_info_html(self, page):
        overview = page.get("body", "")
        detailed = page.get("more_info", "")
        if detailed:
            return (
                "<b>What this topic does</b><br>"
                + overview
                + "<br><br><b>Extra details and practical guidance</b><br>"
                + detailed
                + "<br><br><b>How to use this page</b><br>The outlined control "
                "is the part of the interface affected by this topic. You can "
                "scroll this message for all available details, then press "
                "<b>Got it</b> to return without changing the tutorial step."
            )
        return (
            "<b>What this topic does</b><br>"
            + overview
            + "<br><br><b>Mascot tip:</b> The outlined control is the part of "
            "the interface this topic affects. You can safely return to the "
            "tutorial without changing its current step."
        )

    def show_more_info(self):
        if not self.pages or self._finishing:
            return
        page = self.pages[self.index]
        self.layout_info_panel()
        self.info_panel.set_content(
            f"More about: {page['title']}",
            self.more_info_html(page),
            self.index,
        )
        self.card.hide()
        self.info_panel.show()
        self.info_panel.raise_()
        self.info_panel.setFocus()
        self.update()

    def close_more_info(self):
        if not hasattr(self, "info_panel"):
            return
        self.info_panel.hide()
        if not self._finishing:
            self.card.show()
            self.card.raise_()
            self.setFocus()
        self.update()

    def next(self):
        if self.info_panel.isVisible():
            self.close_more_info()
        if self.index >= len(self.pages) - 1:
            self.finish()
            return
        self.index += 1
        try:
            self.show_page()
        except Exception as exc:
            print(f"Tutorial could not show the next page: {exc}")
            self.finish()

    def previous(self):
        if self.info_panel.isVisible():
            self.close_more_info()
        if self.index > 0:
            self.index -= 1
            try:
                self.show_page()
            except Exception as exc:
                print(f"Tutorial could not show the previous page: {exc}")
                self.finish()

    def finish(self):
        if self._finishing:
            return
        self._finishing = True
        try:
            self.container.removeEventFilter(self)
            self.app.removeEventFilter(self)
            self.hide()
            self.deleteLater()
        except RuntimeError:
            pass
        try:
            self.on_finished()
        except Exception as exc:
            print(f"Tutorial cleanup failed: {exc}")


class WelcomeTutorialExtension(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.overlay = None
        self.tutorial_dialog = None
        self.tutorial_original_pos = None
        self.tutorial_window_was_panned = False
        self.tutorials = self.load_extension_tutorials()
        self.dialog_help_buttons = {}
        self.button = QPushButton("❔ Welcome Tutorial")
        self.button.setToolTip("Replay the guided tour")
        self.button.clicked.connect(self.start)
        app.add_extension_button(self.button)

        QApplication.instance().installEventFilter(self)
        QTimer.singleShot(650, self.start_if_first_run)

    def load_extension_tutorials(self):
        """Load validated tutorial dictionaries from extension_tutorials/."""
        tutorials = []
        folder = Path(__file__).resolve().parent / "extension_tutorials"
        if not folder.is_dir():
            return tutorials

        for path in sorted(folder.rglob("tutorial.py")):
            try:
                relative_name = "_".join(path.relative_to(folder).parts[:-1])
                module_name = f"statbooru_extension_tutorial_{relative_name}"
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                tutorial = getattr(module, "TUTORIAL", None)
                if not isinstance(tutorial, dict):
                    continue
                required = ("id", "name", "matches", "summary", "steps")
                if not all(tutorial.get(key) for key in required):
                    print(f"Skipped incomplete extension tutorial: {path.name}")
                    continue
                tutorial["_source"] = str(path)
                tutorials.append(tutorial)
            except Exception as exc:
                print(f"Failed to load extension tutorial {path.name}: {exc}")
        return sorted(tutorials, key=lambda item: item.get("order", 999))

    def start_if_first_run(self):
        if completed_tutorial_version() < TUTORIAL_VERSION:
            self.start()

    @staticmethod
    def clean_button_text(text):
        return " ".join(str(text or "").lower().split())

    def tutorial_for_button(self, button):
        text = self.clean_button_text(button.text())
        for tutorial in self.tutorials:
            if any(fragment.lower() in text for fragment in tutorial["matches"]):
                return tutorial
        return None

    def find_extension_buttons(self):
        found = []
        for i in range(self.app.ext_button_layout.count()):
            widget = self.app.ext_button_layout.itemAt(i).widget()
            if not isinstance(widget, QPushButton) or widget is self.button:
                continue
            if widget.property("extensionTutorialReplay"):
                continue
            text = widget.text().strip()
            normalized = self.clean_button_text(text)
            if "updater" in normalized or "export image urls" in normalized:
                continue
            found.append((text, widget))
        return found

    def eventFilter(self, watched, event):
        if isinstance(watched, QDialog):
            if event.type() == QEvent.Type.Show:
                QTimer.singleShot(
                    0, lambda dialog=watched: self.safe_attach_tutorial_to_dialog(dialog)
                )
            elif (
                event.type() == QEvent.Type.Close
                and watched is self.tutorial_dialog
                and self.overlay is not None
            ):
                self.overlay.finish()
        return False

    def safe_attach_tutorial_to_dialog(self, dialog):
        try:
            self.attach_tutorial_to_dialog(dialog)
        except (RuntimeError, AttributeError, TypeError) as exc:
            print(f"Could not attach extension tutorial: {exc}")

    def tutorial_for_dialog(self, dialog):
        title = self.clean_button_text(dialog.windowTitle())
        for tutorial in self.tutorials:
            matches = tutorial.get("window_matches", ())
            if any(fragment.lower() in title for fragment in matches):
                return tutorial
        return None

    def attach_tutorial_to_dialog(self, dialog):
        """Put the replay control inside a matching extension dialog."""
        if dialog in self.dialog_help_buttons:
            return
        tutorial = self.tutorial_for_dialog(dialog)
        if tutorial is None:
            return

        help_button = QPushButton("? Tutorial", dialog)
        help_button.setObjectName("extensionTutorialHelp")
        help_button.setMinimumWidth(88)
        help_button.setFixedHeight(30)
        help_button.setToolTip(f"Show the {tutorial['name']} tutorial")
        help_button.setAccessibleName(f"{tutorial['name']} tutorial")
        help_button.clicked.connect(
            lambda _checked=False, item=tutorial, host=dialog:
                self.safe_start_extension_tutorial(item, host)
        )

        layout = dialog.layout()
        if layout is not None and hasattr(layout, "insertWidget"):
            layout.insertWidget(0, help_button, 0, Qt.AlignmentFlag.AlignRight)
        else:
            help_button.move(max(8, dialog.width() - 40), 8)
            help_button.raise_()
        help_button.show()
        self.dialog_help_buttons[dialog] = help_button
        dialog.destroyed.connect(
            lambda _obj=None, host=dialog: self.dialog_help_buttons.pop(host, None)
        )

    @staticmethod
    def resolve_dialog_targets(dialog, step):
        names = step.get("targets", ())
        if isinstance(names, str):
            names = (names,)
        resolved = []
        for name in names:
            target = dialog
            for part in name.split("."):
                target = (
                    target.get(part)
                    if isinstance(target, dict)
                    else getattr(target, part, None)
                )
                if target is None:
                    break
            if isinstance(target, QWidget):
                resolved.append(target)
        return resolved

    @classmethod
    def resolve_dialog_target(cls, dialog, step):
        """Backward-compatible first target used by diagnostics."""
        targets = cls.resolve_dialog_targets(dialog, step)
        return targets[0] if targets else None

    def prepare_dialog_step(self, dialog, step):
        tab = step.get("tab")
        if tab:
            tab_widget = getattr(dialog, tab[0], None)
            if tab_widget is not None and hasattr(tab_widget, "setCurrentIndex"):
                tab_widget.setCurrentIndex(tab[1])

        targets = self.resolve_dialog_targets(dialog, step)
        target = targets[0] if targets else None
        ancestor = target
        scrolled = False
        while ancestor is not None and ancestor is not dialog:
            if isinstance(ancestor, QScrollArea):
                ancestor.ensureWidgetVisible(target, 24, 24)
                scrolled = True
                break
            ancestor = ancestor.parentWidget()
        if targets and not scrolled:
            self.pan_dialog_to_targets(dialog, targets)

    def pan_dialog_to_targets(self, dialog, targets):
        """Move an oversized non-scrollable dialog just enough to show targets."""
        screen = dialog.screen()
        if screen is None:
            return
        target_bounds = QRect()
        for target in targets:
            if not target.isVisible():
                continue
            rect = QRect(target.mapToGlobal(QPoint(0, 0)), target.size())
            target_bounds = rect if target_bounds.isNull() else target_bounds.united(rect)
        if target_bounds.isNull():
            return

        safe = screen.availableGeometry().adjusted(18, 18, -18, -18)
        dx = 0
        dy = 0
        if target_bounds.left() < safe.left():
            dx = safe.left() - target_bounds.left()
        elif target_bounds.right() > safe.right():
            dx = safe.right() - target_bounds.right()
        if target_bounds.top() < safe.top():
            dy = safe.top() - target_bounds.top()
        elif target_bounds.bottom() > safe.bottom():
            dy = safe.bottom() - target_bounds.bottom()
        if dx or dy:
            dialog.move(dialog.pos() + QPoint(dx, dy))
            self.tutorial_window_was_panned = True

    def safe_start_extension_tutorial(self, tutorial, dialog):
        try:
            self.start_extension_tutorial(tutorial, dialog)
        except Exception as exc:
            self.overlay = None
            print(f"Could not start {tutorial.get('name', 'extension')} tutorial: {exc}")

    def start_extension_tutorial(self, tutorial, dialog):
        if self.overlay is not None:
            return
        self.tutorial_dialog = dialog
        self.tutorial_original_pos = QPoint(dialog.pos())
        self.tutorial_window_was_panned = False
        pages = []
        for step in tutorial["steps"]:
            pages.append(
                {
                    "title": step["title"],
                    "body": step["body"],
                    "more_info": step.get("more_info", ""),
                    "target": lambda host=dialog, item=step:
                        self.resolve_dialog_targets(host, item),
                    "prepare": lambda host=dialog, item=step:
                        self.prepare_dialog_step(host, item),
                }
            )
        self.overlay = TutorialOverlay(dialog, pages, self.extension_tutorial_closed)

    def extension_tutorial_closed(self):
        self.overlay = None
        dialog = self.tutorial_dialog
        if (
            dialog is not None
            and self.tutorial_window_was_panned
            and self.tutorial_original_pos is not None
        ):
            try:
                dialog.move(self.tutorial_original_pos)
            except RuntimeError:
                pass
        self.tutorial_dialog = None
        self.tutorial_original_pos = None
        self.tutorial_window_was_panned = False

    def build_pages(self):
        pages = [
            {
                "title": "Welcome to StatBooru",
                "body": (
                    "This short tour shows you the normal search workflow and the "
                    "installed extensions.<br><br>Use <b>Next</b> and <b>Back</b>, "
                    "or the left/right arrow keys. Press <b>Esc</b> to leave at any time."
                ),
                "more_info": (
                    "<b>How the guide works</b><br>Each page outlines the control "
                    "it discusses. More info opens this mascot helper without "
                    "advancing the tutorial. Extension windows have their own "
                    "<b>? Tutorial</b> button and more detailed lessons."
                ),
            },
            {
                "title": "1. Enter a Danbooru query",
                "body": (
                    "Type tags here, separated by spaces. You can also use "
                    "<b>tag1 OR tag2</b>, <b>-tag</b> to exclude, wildcards such "
                    "as <b>*miku*</b>, and metatags such as <b>source:</b> or "
                    "<b>order:score</b>. An empty query updates tag counts."
                ),
                "more_info": (
                    "<b>Useful query patterns</b><br>Spaces mean AND. Use uppercase "
                    "OR between alternatives, a leading minus to exclude, and "
                    "wildcards for partial tag names. Autocomplete helps use the "
                    "exact underscore-separated names stored by Danbooru."
                ),
                "target": lambda: self.app.search_input,
            },
            {
                "title": "2. Choose an optional threshold",
                "body": (
                    "Keep <b>No Threshold</b> to include everything, or limit the "
                    "results by minimum score or favorites. The number box becomes "
                    "available when its matching option is selected."
                ),
                "more_info": (
                    "Score reflects voting; favorites count users who saved a post. "
                    "A threshold is applied in addition to the text query, dates, "
                    "ratings, and image properties. Begin without one when exploring, "
                    "then raise it when you need a smaller high-interest set."
                ),
                "target": lambda: self.app.radio_none.parentWidget(),
            },
            {
                "title": "3. Set sorting and ratings",
                "body": (
                    "Choose how results are sorted and whether the order is "
                    "ascending or descending. Select the rating categories you "
                    "want included; General and Sensitive start enabled."
                ),
                "more_info": (
                    "Sorting changes presentation, not which posts match. Descending "
                    "Score or Favorites surfaces popular posts; ascending can reveal "
                    "low-engagement material. Rating checkboxes are inclusive: a post "
                    "is kept when its rating is one of the checked categories."
                ),
                "target": lambda: self.app.sort_combo.parentWidget(),
            },
            {
                "title": "4. Refine image properties",
                "body": (
                    "Filter by orientation, remove duplicate MD5s, or enable "
                    "thumbnails. Thumbnails require a network connection and can "
                    "make displaying a large result set slower."
                ),
                "more_info": (
                    "Orientation is calculated from image width and height. MD5 "
                    "deduplication keeps one copy of identical files. Thumbnail loading "
                    "contacts remote image servers, so leave it disabled for maximum "
                    "speed, offline work, or very large searches."
                ),
                "target": lambda: self.app.orientation_combo.parentWidget(),
            },
            {
                "title": "5. Pick the upload date range",
                "body": (
                    "Limit the search to posts uploaded between these dates. The "
                    "default range covers the dataset's full history."
                ),
                "more_info": (
                    "Dates refer to Danbooru upload time, not the artwork's creation "
                    "date. A narrow range reduces work and makes daily analysis clearer. "
                    "Use the full range when studying long-term trends or rare tags."
                ),
                "target": lambda: self.app.date_from.parentWidget(),
            },
            {
                "title": "6. Select a search mode",
                "body": (
                    "<b>Fast in-process</b> is best for normal use. Choose the "
                    "memory-safe isolated mode for very large searches when "
                    "releasing temporary memory matters more than speed."
                ),
                "more_info": (
                    "Fast mode keeps processing in the application and usually has "
                    "less overhead. Isolated mode performs heavy work in a separate "
                    "process so its temporary native memory can be returned to Windows "
                    "when the search finishes."
                ),
                "target": lambda: self.app.search_mode_combo.parentWidget(),
            },
            {
                "title": "7. Run the search",
                "body": (
                    "Click <b>Search</b>. The result count appears above the table. "
                    "You can double-click a result or use its right-click menu for "
                    "available post actions."
                ),
                "more_info": (
                    "Search builds a lazy Polars query, applies every selected filter, "
                    "then materializes the display results. Avoid repeatedly clicking "
                    "while it is running. If a query returns nothing, broaden one filter "
                    "at a time to identify the restrictive condition."
                ),
                "target": lambda: self.app.btn_search,
            },
            {
                "title": "8. Review and export results",
                "body": (
                    "Results show a thumbnail (when enabled), post ID, rating, "
                    "score, favorites, and a tag preview. After a successful search, "
                    "use <b>Export Image URLs to TXT</b> below the table."
                ),
                "more_info": (
                    "The table is a preview of the matching data. Tag colors identify "
                    "categories, and tag links can help refine the query. Export writes "
                    "available image URLs—not image files—so another downloader or script "
                    "can process them later."
                ),
                "target": lambda: self.app.table,
            },
        ]

        for text, button in self.find_extension_buttons():
            tutorial = self.tutorial_for_button(button)
            if tutorial is not None:
                title = tutorial["name"]
                body = (
                    tutorial["summary"]
                    + "<br><br>Open the extension, then use the <b>?</b> inside "
                    "its window to replay its detailed tutorial at any time."
                )
                more_info = tutorial.get(
                    "more_info",
                    tutorial["summary"]
                    + "<br><br>Open the extension and press <b>? Tutorial</b> for its "
                    "complete control-by-control workflow.",
                )
            else:
                title = text
                body = (
                    f"Open <b>{text}</b> for its additional tools. "
                    "Follow the controls in its window."
                )
                more_info = (
                    f"{body}<br><br>This extension does not currently provide a "
                    "separate detailed tutorial module."
                )
            pages.append(
                {
                    "title": title,
                    "body": body,
                    "more_info": more_info,
                    "target": button,
                }
            )

        pages.append(
            {
                "title": "You’re ready",
                "body": (
                    "Start with a query, adjust only the filters you need, and run "
                    "the search. You can replay this guide any time with the "
                    "<b>Welcome Tutorial</b> button."
                ),
                "more_info": (
                    "A reliable workflow is: start broad, verify the result count, "
                    "tighten one filter at a time, then open an analysis extension. "
                    "The Welcome Tutorial and every extension's ? Tutorial button can "
                    "be replayed without resetting your data."
                ),
                "target": self.button,
            }
        )
        return pages

    def start(self):
        if self.overlay is not None:
            return
        self.overlay = TutorialOverlay(self.app, self.build_pages(), self.completed)

    def completed(self):
        save_completed_tutorial_version(TUTORIAL_VERSION)
        self.overlay = None


def setup(app):
    app.welcome_tutorial_extension = WelcomeTutorialExtension(app)
