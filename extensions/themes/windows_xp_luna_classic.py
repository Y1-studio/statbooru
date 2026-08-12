"""Windows XP Luna styling and classic-layout runtime behavior."""

import re

from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton


THEME_NAME = "Windows XP Luna Classic"
AUTOCOMPLETE_POPUP_NAMES = {
    "AutocompletePopup",
    "ExtAutocompletePopup",
}
COLOR_PATTERN = re.compile(r"color\s*:\s*(#[0-9a-fA-F]{6})")

TAG_COLORS = {
    "#f38ba8": "#9b1b30",
    "#cba6f7": "#6a2ca0",
    "#a6e3a1": "#237a2f",
    "#89b4fa": "#164a9c",
    "#fab387": "#8a5a00",
    "#9b1b30": "#9b1b30",
    "#6a2ca0": "#6a2ca0",
    "#237a2f": "#237a2f",
    "#164a9c": "#164a9c",
    "#8a5a00": "#8a5a00",
}

SELECTED_TAG_COLORS = {
    "#f38ba8": "#ffb0b8",
    "#cba6f7": "#efb0ff",
    "#a6e3a1": "#b0ffb8",
    "#89b4fa": "#b8e8ff",
    "#fab387": "#fff0a0",
    "#9b1b30": "#ffb0b8",
    "#6a2ca0": "#efb0ff",
    "#237a2f": "#b0ffb8",
    "#164a9c": "#b8e8ff",
    "#8a5a00": "#fff0a0",
}

UNSELECTED_TAG_COLORS = {
    "#ffb0b8": "#9b1b30",
    "#efb0ff": "#6a2ca0",
    "#b0ffb8": "#237a2f",
    "#b8e8ff": "#164a9c",
    "#fff0a0": "#8a5a00",
}

ORIGINAL_TAG_COLORS = {
    "#9b1b30": "#f38ba8",
    "#6a2ca0": "#cba6f7",
    "#237a2f": "#a6e3a1",
    "#164a9c": "#89b4fa",
    "#8a5a00": "#fab387",
    "#ffb0b8": "#f38ba8",
    "#efb0ff": "#cba6f7",
    "#b0ffb8": "#a6e3a1",
    "#b8e8ff": "#89b4fa",
    "#fff0a0": "#fab387",
}

BUTTON_STYLE = """
QPushButton {
    color: #000000;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:0.48 #f7f5e9,
        stop:0.52 #e3dfcf,
        stop:1 #f3f0df
    );
    border: 1px solid #003c74;
    border-radius: 5px;
    padding: 7px 11px;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    font-weight: normal;
}
QPushButton:hover {
    border: 2px solid #ff8c00;
    padding: 6px 10px;
}
QPushButton:pressed {
    background-color: #d6d2c2;
    border: 2px solid #003c74;
    padding: 8px 10px 6px 12px;
}
QPushButton:disabled {
    color: #808080;
    background-color: #ece9d8;
    border-color: #aca899;
}
"""

STATS_STYLE = (
    "color: #ffffff; background-color: #245edb; "
    "font-family: 'Tahoma', 'Segoe UI'; font-size: 14px; "
    "font-weight: bold; border: 1px solid #003c74; "
    "border-radius: 3px; padding: 4px 8px;"
)

AUTOCOMPLETE_STYLE = """
QListWidget {
    border: 1px solid #003c74;
    background-color: #ffffff;
    color: #000000;
    border-radius: 2px;
}
QListWidget::item { padding: 2px; }
QListWidget::item:selected {
    background-color: #c4ddff;
    color: #000000;
}
QLabel {
    color: #000000;
    background-color: transparent;
    font-family: 'Tahoma', 'Segoe UI';
}
"""

AUTOCOMPLETE_LABEL_STYLE = (
    "color: #333333; background: transparent; font-size: 12px;"
)

START_SEARCH_BUTTON_STYLE = """
QPushButton {
    color: #ffffff;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #79bf4b,
        stop:0.46 #4e9f25,
        stop:0.5 #3b8d16,
        stop:1 #2d730d
    );
    border: 1px solid #1f5c08;
    border-radius: 6px;
    padding: 7px 15px;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #8fd461,
        stop:1 #3b8d16
    );
    border: 2px solid #ffb13b;
    padding: 6px 14px;
}
QPushButton:pressed {
    background-color: #2d730d;
    border: 2px solid #174a04;
    padding: 8px 14px 6px 16px;
}
QPushButton:disabled {
    color: #d8e4d1;
    background-color: #719466;
    border-color: #60755a;
}
"""

EXTENSION_SHORTCUT_STYLE = """
QPushButton {
    color: #003399;
    background-color: #ffffff;
    border: 1px solid #7f9db9;
    border-left: 7px solid #245edb;
    border-radius: 3px;
    padding: 7px 8px 7px 7px;
    text-align: left;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    font-weight: normal;
}
QPushButton:hover {
    color: #ffffff;
    background-color: #316ac5;
    border-color: #003c74;
    border-left-color: #ff8c00;
}
QPushButton:pressed {
    color: #ffffff;
    background-color: #245edb;
    border-color: #003c74;
    padding: 8px 7px 6px 8px;
}
QPushButton:disabled {
    color: #808080;
    background-color: #ece9d8;
    border-color: #aca899;
}
"""

IMPORTANT_EXTENSION_STYLE = """
QPushButton {
    color: #003399;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #fff3d8,
        stop:0.16 #ffffff,
        stop:1 #ffffff
    );
    border: 1px solid #7f9db9;
    border-left: 7px solid #ff8c00;
    border-radius: 3px;
    padding: 7px 8px 7px 7px;
    text-align: left;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
    font-weight: bold;
}
QPushButton:hover {
    color: #ffffff;
    background-color: #316ac5;
    border-color: #003c74;
    border-left-color: #ffd27a;
}
QPushButton:pressed {
    color: #ffffff;
    background-color: #245edb;
    border-color: #003c74;
    padding: 8px 7px 6px 8px;
}
QPushButton:disabled {
    color: #808080;
    background-color: #ece9d8;
    border-color: #aca899;
}
"""

IMPORTANT_EXTENSION_KEYWORDS = (
    "tag analytics",
    "dataset updater",
    "interactive tag mapper",
    "compare tags globally",
)

STYLESHEET = """
QWidget {
    background-color: transparent;
    color: #000000;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QMainWindow > QWidget {
    background-color: #3a6ea5;
}
QDialog, QDialog#themeChooserDialog {
    background-color: #ece9d8;
}
QGroupBox {
    background-color: #ece9d8;
    color: #000000;
    border-top: 23px solid #245edb;
    border-left: 1px solid #003c74;
    border-right: 1px solid #003c74;
    border-bottom: 1px solid #003c74;
    border-radius: 5px;
    margin-top: 0px;
    padding: 9px 7px 7px 7px;
}
QGroupBox::title {
    subcontrol-origin: border;
    subcontrol-position: top left;
    left: 6px;
    top: 2px;
    padding: 1px 4px;
    color: #ffffff;
    background-color: #245edb;
    border: none;
    font-weight: bold;
}
QGroupBox[xpStartMenu="true"] {
    background-color: #ffffff;
    border-top: 30px solid #245edb;
    border-left: 2px solid #245edb;
    border-right: 2px solid #245edb;
    border-bottom: 4px solid #ff8c00;
    border-radius: 7px;
    padding: 10px 8px 8px 8px;
}
QGroupBox[xpStartMenu="true"]::title {
    left: 10px;
    top: 4px;
    color: #ffffff;
    background-color: #245edb;
    font-size: 14px;
    font-weight: bold;
}
QTextEdit[xpStartSearchInput="true"] {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid #7f9db9;
    border-radius: 3px;
    padding: 6px;
    selection-background-color: #316ac5;
    selection-color: #ffffff;
}
QTextEdit, QLineEdit, QTextBrowser, QComboBox, QDateEdit, QSpinBox,
QDoubleSpinBox {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #7f9db9;
    border-radius: 3px;
    padding: 3px 5px;
    selection-background-color: #316ac5;
    selection-color: #ffffff;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
    min-height: 24px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #003c74;
    selection-background-color: #316ac5;
    selection-color: #ffffff;
}
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f7f6ef;
    color: #000000;
    border: 1px solid #003c74;
    border-radius: 2px;
    gridline-color: #aca899;
}
QTableWidget::item:selected {
    background-color: #316ac5;
    color: #ffffff;
}
QHeaderView::section {
    color: #000000;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:1 #d6d2c2
    );
    border-top: 1px solid #ffffff;
    border-left: 1px solid #ffffff;
    border-bottom: 1px solid #7f9db9;
    border-right: 1px solid #7f9db9;
    padding: 6px;
    font-weight: bold;
}
QTabBar::tab {
    background-color: #ece9d8;
    color: #000000;
    border: 1px solid #7f9db9;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 7px 12px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #003c74;
    font-weight: bold;
}
QCheckBox, QRadioButton, QLabel {
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    background-color: #ffffff;
    border: 1px solid #003c74;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #245edb;
    border: 2px solid #003c74;
}
QProgressBar {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #003c74;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #3c8d0d;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #ece9d8;
    border: 1px solid #7f9db9;
}
QScrollBar::handle {
    background-color: #d6d2c2;
    border: 1px solid #7f9db9;
    border-radius: 2px;
    min-height: 22px;
    min-width: 22px;
}
QScrollBar::handle:hover { background-color: #c4ddff; }
QMenu, QToolTip {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #003c74;
}
QMenu::item:selected {
    background-color: #316ac5;
    color: #ffffff;
}
"""


class XPClassicController:
    """Own behavior that is specific to the XP Luna classic theme."""

    def __init__(self, switcher):
        self.switcher = switcher
        self.active = False
        self._selection_table = None
        self._selected_tag_rows = set()
        self._autocomplete_styles = {}
        self.install_wrap_tag_override()
        self.install_table_hooks()

    @staticmethod
    def _repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _search_group(self):
        widget = getattr(self.switcher.app, "search_input", None)
        while widget is not None:
            if isinstance(widget, QGroupBox):
                return widget
            widget = widget.parentWidget()
        return None

    def _extension_buttons(self):
        layout = getattr(self.switcher.app, "ext_button_layout", None)
        if layout is None:
            return []
        buttons = []
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                buttons.append(widget)
        return buttons

    def refresh_widget_roles(self, enabled, root=None):
        """Style the search and program shortcuts as an XP Start menu."""
        app = self.switcher.app
        search_input = getattr(app, "search_input", None)
        search_group = self._search_group()
        search_button = getattr(app, "btn_search", None)
        extension_buttons = self._extension_buttons()

        property_widgets = (
            (search_group, "xpStartMenu"),
            (search_input, "xpStartSearchInput"),
        )
        for widget, property_name in property_widgets:
            if widget is None:
                continue
            state = bool(widget.property(property_name))
            if state != bool(enabled):
                widget.setProperty(property_name, bool(enabled))
                self._repolish(widget)

        if not enabled:
            for button in extension_buttons:
                button.setProperty("xpExtensionShortcut", False)
                button.setProperty("xpImportantExtension", False)
                button.setProperty("_xpClassicRoleSignature", None)
            if search_button is not None:
                search_button.setProperty("xpStartSearchButton", False)
                search_button.setProperty("_xpClassicRoleSignature", None)
            return

        epoch = self.switcher._style_epoch
        if search_button is not None:
            signature = f"{epoch}:search"
            if search_button.property("_xpClassicRoleSignature") != signature:
                search_button.setProperty("xpStartSearchButton", True)
                search_button.setStyleSheet(START_SEARCH_BUTTON_STYLE)
                search_button.setProperty(
                    "_xpClassicRoleSignature",
                    signature,
                )

        for button in extension_buttons:
            text = button.text().lower()
            important = any(
                keyword in text
                for keyword in IMPORTANT_EXTENSION_KEYWORDS
            )
            role = "important" if important else "shortcut"
            signature = f"{epoch}:{role}"
            if button.property("_xpClassicRoleSignature") == signature:
                continue
            button.setProperty("xpExtensionShortcut", True)
            button.setProperty("xpImportantExtension", important)
            button.setStyleSheet(
                IMPORTANT_EXTENSION_STYLE
                if important
                else EXTENSION_SHORTCUT_STYLE
            )
            button.setProperty("_xpClassicRoleSignature", signature)

    def install_wrap_tag_override(self):
        app = self.switcher.app
        original = getattr(app, "wrap_tag", None)
        if original is None:
            return

        def themed_wrap_tag(tags_str, color):
            if not self.active:
                return original(tags_str, color)
            if not tags_str:
                return ""
            mapped = TAG_COLORS.get(str(color).lower(), "#164a9c")
            return " ".join(
                f'<a href="{tag}" style="color:{mapped}; '
                f'text-decoration:none;">{tag}</a>'
                for tag in str(tags_str).split()
            )

        app.wrap_tag = themed_wrap_tag

    def install_table_hooks(self):
        table = getattr(self.switcher.app, "table", None)
        if table is not None and table is not self._selection_table:
            table.itemSelectionChanged.connect(self.refresh_table_selection)
            self._selection_table = table
        signal = getattr(self.switcher.app, "data_updated", None)
        if signal is not None and not getattr(
            self.switcher.app,
            "_xpClassicDataHook",
            False,
        ):
            signal.connect(self.refresh_results)
            self.switcher.app._xpClassicDataHook = True

    @staticmethod
    def recolor_html(html, palette):
        return COLOR_PATTERN.sub(
            lambda match: (
                "color:"
                + palette.get(
                    match.group(1).lower(),
                    match.group(1),
                )
            ),
            html,
        )

    def apply_theme(self, name):
        was_active = self.active
        self.active = name == THEME_NAME
        self.install_table_hooks()
        if self.active:
            self.refresh_widget_roles(True)
            self.recolor_table(TAG_COLORS)
            self._selected_tag_rows.clear()
            self.refresh_table_selection()
            self.refresh_autocomplete()
        elif was_active:
            self.recolor_table(ORIGINAL_TAG_COLORS)
            self._selected_tag_rows.clear()
            self.refresh_autocomplete()

    def prepare_theme_change(self, name):
        """Restore shared widgets before another classic runtime styles them."""
        if not self.active or name == THEME_NAME:
            return
        self.active = False
        self.refresh_widget_roles(False)
        self.recolor_table(ORIGINAL_TAG_COLORS)
        self._selected_tag_rows.clear()
        self.refresh_autocomplete()

    def refresh_results(self, *_args):
        if not self.active:
            return
        self.recolor_table(TAG_COLORS)
        self._selected_tag_rows.clear()
        self.refresh_table_selection()

    def recolor_table(self, palette):
        table = self._selection_table
        if table is None:
            return
        for row in range(table.rowCount()):
            browser = table.cellWidget(row, 5)
            if (
                browser is None
                or browser.__class__.__name__ != "TagBrowser"
            ):
                continue
            html = browser.toHtml()
            recolored = self.recolor_html(html, palette)
            if recolored != html:
                browser.setHtml(recolored)

    def refresh_table_selection(self):
        if not self.active or self._selection_table is None:
            return
        table = self._selection_table
        selected_rows = {
            index.row()
            for index in table.selectionModel().selectedRows()
        }
        for row in selected_rows.symmetric_difference(
            self._selected_tag_rows
        ):
            browser = table.cellWidget(row, 5)
            if (
                browser is None
                or browser.__class__.__name__ != "TagBrowser"
            ):
                continue
            html = browser.toHtml()
            palette = (
                SELECTED_TAG_COLORS
                if row in selected_rows
                else UNSELECTED_TAG_COLORS
            )
            recolored = self.recolor_html(html, palette)
            if recolored != html:
                browser.setHtml(recolored)
        self._selected_tag_rows = selected_rows

    def handle_widget_show(self, watched):
        class_name = watched.__class__.__name__
        if class_name in AUTOCOMPLETE_POPUP_NAMES:
            if (
                self.active
                or watched.property("_xpClassicAutocompleteEnabled")
            ):
                self.style_autocomplete(watched, style_labels=False)
            return
        if not self.active or not isinstance(watched, QLabel):
            return
        top_level = watched.window()
        if (
            top_level is not None
            and top_level.__class__.__name__ in AUTOCOMPLETE_POPUP_NAMES
        ):
            self.style_autocomplete_label(watched)

    def style_autocomplete_label(self, label):
        text = label.text()
        signature = f"{self.switcher._style_epoch}:{text}"
        if label.property("_xpClassicAutocompleteLabel") == signature:
            return
        if "color:" in text:
            themed = self.recolor_html(text, TAG_COLORS)
            if themed != text:
                label.setText(themed)
                signature = f"{self.switcher._style_epoch}:{themed}"
        elif label.styleSheet() != AUTOCOMPLETE_LABEL_STYLE:
            label.setStyleSheet(AUTOCOMPLETE_LABEL_STYLE)
        label.setProperty("_xpClassicAutocompleteLabel", signature)

    def refresh_autocomplete(self):
        for popup in QApplication.topLevelWidgets():
            if popup.__class__.__name__ in AUTOCOMPLETE_POPUP_NAMES:
                self.style_autocomplete(popup)
        if not self.active:
            self._autocomplete_styles.clear()

    def style_autocomplete(self, popup, style_labels=True):
        key = id(popup)
        if key not in self._autocomplete_styles:
            self._autocomplete_styles[key] = (
                popup,
                popup.styleSheet(),
            )
        state = popup.property("_xpClassicAutocompleteEnabled")
        if not self.active:
            if state:
                popup.setStyleSheet(self._autocomplete_styles[key][1])
                popup.setProperty("_xpClassicAutocompleteEnabled", False)
            return
        if not state:
            popup.setStyleSheet(AUTOCOMPLETE_STYLE)
            popup.setProperty("_xpClassicAutocompleteEnabled", True)
        if style_labels:
            for label in popup.findChildren(QLabel):
                self.style_autocomplete_label(label)


def stylesheet_suffix(enabled):
    return STYLESHEET if enabled else ""
