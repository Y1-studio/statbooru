"""Windows 3.1 runtime: VGA tag colors and readability overrides."""

import re

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QWidget,
)


TAG_COLORS = {
    "#f38ba8": "#800000",
    "#cba6f7": "#800080",
    "#a6e3a1": "#008000",
    "#89b4fa": "#000080",
    "#fab387": "#808000",
    "#800000": "#800000",
    "#800080": "#800080",
    "#008000": "#008000",
    "#000080": "#000080",
    "#808000": "#808000",
}

SELECTED_TAG_COLORS = {
    "#f38ba8": "#ff8080",
    "#cba6f7": "#ff80ff",
    "#a6e3a1": "#80ff80",
    "#89b4fa": "#80ffff",
    "#fab387": "#ffff80",
    "#800000": "#ff8080",
    "#800080": "#ff80ff",
    "#008000": "#80ff80",
    "#000080": "#80ffff",
    "#808000": "#ffff80",
}

UNSELECTED_TAG_COLORS = {
    "#ff8080": "#800000",
    "#ff80ff": "#800080",
    "#80ff80": "#008000",
    "#80ffff": "#000080",
    "#ffff80": "#808000",
}

ORIGINAL_TAG_COLORS = {
    "#800000": "#f38ba8",
    "#800080": "#cba6f7",
    "#008000": "#a6e3a1",
    "#000080": "#89b4fa",
    "#808000": "#fab387",
    "#ff8080": "#f38ba8",
    "#ff80ff": "#cba6f7",
    "#80ff80": "#a6e3a1",
    "#80ffff": "#89b4fa",
    "#ffff80": "#fab387",
}

AUTOCOMPLETE_POPUP_NAMES = {
    "AutocompletePopup",
    "ExtAutocompletePopup",
}

AUTOCOMPLETE_STYLE = """
    QListWidget {
        border: 2px solid #000000;
        background-color: #ffffff;
        color: #000000;
        border-radius: 0px;
    }
    QListWidget::item { padding: 2px; border-radius: 0px; }
    QListWidget::item:selected { background-color: #c0c0c0; }
    QLabel {
        color: #000000;
        background-color: transparent;
        font-family: 'Microsoft Sans Serif', 'Tahoma', 'Segoe UI';
    }
"""

AUTOCOMPLETE_LABEL_STYLE = (
    "color: #000000; background: transparent; font-size: 12px;"
)

COLOR_PATTERN = re.compile(r"color\s*:\s*(#[0-9a-fA-F]{6})")

BUTTON_STYLE = """
QPushButton {
    background-color: #c0c0c0;
    color: #000000;
    border-top: 2px solid #ffffff;
    border-left: 2px solid #ffffff;
    border-bottom: 2px solid #000000;
    border-right: 2px solid #000000;
    border-radius: 0px;
    padding: 7px 10px;
    font-family: 'Microsoft Sans Serif', 'Tahoma',
                 'Segoe UI', 'Arial', sans-serif;
    font-size: 12px;
    font-weight: normal;
}
QPushButton:hover { background-color: #d4d4d4; }
QPushButton:pressed {
    background-color: #a0a0a0;
    border-top: 2px solid #000000;
    border-left: 2px solid #000000;
    border-bottom: 2px solid #ffffff;
    border-right: 2px solid #ffffff;
}
QPushButton:disabled {
    color: #808080;
    background-color: #c0c0c0;
}
"""

STATS_STYLE = (
    "color: #ffffff; background-color: #000080; "
    "font-family: 'Microsoft Sans Serif', 'Tahoma', 'Segoe UI'; "
    "font-size: 13px; font-weight: bold; "
    "border: 2px solid #000000; padding: 4px 8px;"
)


class Win31Controller:
    def __init__(self, switcher):
        self.switcher = switcher
        self._readability_active = False
        self._autocomplete_active = False
        self._selection_table = None
        self._selected_tag_rows = set()
        self.install_wrap_tag_override()
        self.install_table_selection_override()

    def install_wrap_tag_override(self):
        app = self.switcher.app
        original = getattr(
            app,
            "_theme_switcher_original_wrap_tag",
            getattr(app, "wrap_tag", None),
        )
        if original is None:
            return
        app._theme_switcher_original_wrap_tag = original

        def themed_wrap_tag(tags_str, color):
            if getattr(app, "current_theme_name", "") != "Windows 3.1":
                return original(tags_str, color)
            if not tags_str:
                return ""
            mapped = TAG_COLORS.get(str(color).lower(), "#000080")
            return " ".join(
                f'<a href="{tag}" style="color:{mapped}; '
                f'text-decoration:none;">{tag}</a>'
                for tag in str(tags_str).split()
            )

        app.wrap_tag = themed_wrap_tag

    def install_table_selection_override(self):
        table = getattr(self.switcher.app, "table", None)
        if table is None or table is self._selection_table:
            return
        table.itemSelectionChanged.connect(self.refresh_table_selection)
        self._selection_table = table

    @staticmethod
    def _recolor_html(html, palette):
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

    def refresh_table_selection(self):
        """Use bright VGA tag colors only on newly selected table rows."""
        if not self._readability_active:
            return
        self.install_table_selection_override()
        table = self._selection_table
        if table is None:
            return
        selected_rows = {
            index.row()
            for index in table.selectionModel().selectedRows()
        }
        changed_rows = selected_rows.symmetric_difference(
            self._selected_tag_rows
        )
        for row in changed_rows:
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
            recolored = self._recolor_html(html, palette)
            if recolored != html:
                browser.setHtml(recolored)
        self._selected_tag_rows = selected_rows

    def refresh_readability(self, enabled, root=None):
        switcher = self.switcher
        if not enabled:
            if not self._readability_active:
                return
            if root is not None:
                return
            self._restore_readability()
            self._readability_active = False
            return

        self._readability_active = True
        owner = root or switcher.app
        labels = owner.findChildren(QLabel)
        if isinstance(owner, QLabel):
            labels.insert(0, owner)
        for label in labels:
            if label.property("tutorialManagedStyle"):
                continue
            if label.__class__.__name__ == "ThumbnailWidget":
                continue
            pixmap = label.pixmap()
            if pixmap is not None and not pixmap.isNull():
                continue
            key = id(label)
            if key not in switcher._label_styles:
                switcher._label_styles[key] = (label, label.styleSheet())
            signature = f"{int(enabled)}:{switcher._style_epoch}"
            if label.property("_win31ReadabilitySignature") == signature:
                continue
            original_style = switcher._label_styles[key][1]
            is_heading = (
                "font-size: 18px" in original_style
                or "Dashboard:" in label.text()
            )
            if is_heading:
                label.setStyleSheet(
                    "color: #ffffff; background-color: #000080; "
                    "font-family: 'Microsoft Sans Serif', 'Tahoma', "
                    "'Segoe UI'; font-size: 16px; font-weight: bold; "
                    "padding: 5px 8px;"
                )
            else:
                label.setStyleSheet(
                    "color: #000000; background-color: transparent; "
                    "font-family: 'Microsoft Sans Serif', 'Tahoma', "
                    "'Segoe UI'; font-size: 14px; font-weight: normal;"
                )
            label.setProperty("_win31ReadabilitySignature", signature)

        control_types = (
            QComboBox,
            QDateEdit,
            QSpinBox,
            QDoubleSpinBox,
            QLineEdit,
            QTextEdit,
        )
        controls = []
        seen_controls = set()
        for control_type in control_types:
            for control in owner.findChildren(control_type):
                key = id(control)
                if key not in seen_controls:
                    controls.append(control)
                    seen_controls.add(key)
        if isinstance(owner, control_types):
            controls.insert(0, owner)
        for control in controls:
            if control.property("tutorialManagedStyle"):
                continue
            key = id(control)
            if key not in switcher._control_styles:
                switcher._control_styles[key] = (
                    control,
                    control.styleSheet(),
                    control.displayFormat()
                    if isinstance(control, QDateEdit)
                    else None,
                )
            signature = f"{int(enabled)}:{switcher._style_epoch}"
            if control.property("_win31ReadabilitySignature") == signature:
                continue
            original_style = switcher._control_styles[key][1]
            is_date = isinstance(control, QDateEdit)
            padding = "1px 0px" if is_date else "3px 5px"
            font_size = "11px" if is_date else "14px"
            date_drop_down = (
                " QDateEdit::drop-down { width: 14px; "
                "border-left: 1px solid #808080; }"
                if is_date
                else ""
            )
            if is_date:
                control.setDisplayFormat("dd/MM/yy")
            control.setStyleSheet(
                "background-color: #ffffff; color: #000000; "
                "border-top: 2px solid #000000; "
                "border-left: 2px solid #000000; "
                "border-bottom: 2px solid #ffffff; "
                "border-right: 2px solid #ffffff; "
                f"border-radius: 0px; padding: {padding}; "
                "min-height: 24px; "
                "font-family: 'Microsoft Sans Serif', 'Tahoma', "
                f"'Segoe UI'; font-size: {font_size};"
                + date_drop_down
            )
            control.setProperty("_win31ReadabilitySignature", signature)

        browsers = owner.findChildren(QTextBrowser)
        if isinstance(owner, QTextBrowser):
            browsers.insert(0, owner)
        for browser in browsers:
            if browser.property("tutorialManagedStyle"):
                continue
            key = id(browser)
            if key not in switcher._rich_text_states:
                switcher._rich_text_states[key] = (
                    browser,
                    browser.toHtml(),
                )
                browser.setHtml(
                    COLOR_PATTERN.sub(
                        lambda match: (
                            "color:"
                            + TAG_COLORS.get(
                                match.group(1).lower(),
                                "#000080",
                            )
                        ),
                        switcher._rich_text_states[key][1],
                    )
                )
        if root is None:
            self.install_table_selection_override()
            self._selected_tag_rows.clear()
            self.refresh_table_selection()

    def _restore_readability(self):
        switcher = self.switcher
        for label, original_style in switcher._label_styles.values():
            try:
                label.setStyleSheet(original_style)
                label.setProperty("_win31ReadabilitySignature", None)
            except RuntimeError:
                pass
        switcher._label_styles.clear()

        for control, original_style, date_format in (
            switcher._control_styles.values()
        ):
            try:
                control.setStyleSheet(original_style)
                if isinstance(control, QDateEdit):
                    control.setDisplayFormat(date_format)
                control.setProperty("_win31ReadabilitySignature", None)
            except RuntimeError:
                pass
        switcher._control_styles.clear()

        for browser, original_html in switcher._rich_text_states.values():
            try:
                browser.setHtml(original_html)
            except RuntimeError:
                pass
        switcher._rich_text_states.clear()
        self._restore_table_tag_colors()
        self._selected_tag_rows.clear()

    def _restore_table_tag_colors(self):
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
            restored = self._recolor_html(html, ORIGINAL_TAG_COLORS)
            if restored != html:
                browser.setHtml(restored)

    def handle_widget_show(self, watched):
        """Style one newly shown autocomplete object without rescanning it."""
        class_name = watched.__class__.__name__
        if class_name in AUTOCOMPLETE_POPUP_NAMES:
            self.refresh_autocomplete(watched, style_labels=False)
            return
        if not isinstance(watched, QLabel) or not self._autocomplete_enabled():
            return
        top_level = watched.window()
        if (
            top_level is not None
            and top_level.__class__.__name__ in AUTOCOMPLETE_POPUP_NAMES
        ):
            self._style_autocomplete_label(watched)

    def _autocomplete_enabled(self):
        return (
            getattr(self.switcher.app, "current_theme_name", "")
            == "Windows 3.1"
        )

    def _style_autocomplete_label(self, label):
        text = label.text()
        signature = f"{self.switcher._style_epoch}:{text}"
        if label.property("_win31AutocompleteLabel") == signature:
            return
        if "color:" in text:
            themed_text = COLOR_PATTERN.sub(
                lambda match: (
                    "color:"
                    + TAG_COLORS.get(
                        match.group(1).lower(),
                        "#ff0000",
                    )
                ),
                text,
            )
            if themed_text != text:
                label.setText(themed_text)
                signature = (
                    f"{self.switcher._style_epoch}:{themed_text}"
                )
        elif label.styleSheet() != AUTOCOMPLETE_LABEL_STYLE:
            label.setStyleSheet(AUTOCOMPLETE_LABEL_STYLE)
        label.setProperty("_win31AutocompleteLabel", signature)

    def refresh_autocomplete(self, popup=None, style_labels=True):
        switcher = self.switcher
        enabled = self._autocomplete_enabled()
        if not enabled and not self._autocomplete_active and popup is None:
            return
        candidates = (
            [popup]
            if popup is not None
            else [
                widget
                for widget in QApplication.topLevelWidgets()
                if widget.__class__.__name__ in AUTOCOMPLETE_POPUP_NAMES
            ]
        )
        if enabled:
            self._autocomplete_active = True
        for candidate in candidates:
            if candidate is None:
                continue
            key = id(candidate)
            if key not in switcher._autocomplete_styles:
                switcher._autocomplete_styles[key] = (
                    candidate,
                    candidate.styleSheet(),
                )
            state = candidate.property("_win31AutocompleteEnabled")
            if not enabled:
                if state:
                    try:
                        candidate.setStyleSheet(
                            switcher._autocomplete_styles[key][1]
                        )
                        candidate.setProperty(
                            "_win31AutocompleteEnabled",
                            False,
                        )
                    except RuntimeError:
                        pass
                continue

            if not state:
                candidate.setStyleSheet(AUTOCOMPLETE_STYLE)
                candidate.setProperty("_win31AutocompleteEnabled", True)
            if style_labels:
                for label in candidate.findChildren(QLabel):
                    self._style_autocomplete_label(label)
        if not enabled and popup is None:
            self._autocomplete_active = False
            switcher._autocomplete_styles.clear()
