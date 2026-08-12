"""Shared Qt stylesheet renderer for theme definitions."""


def build_stylesheet(colors, retro_runtime):
    """Build one complete host stylesheet from a small color palette."""
    stylesheet = """
QWidget {{
    background-color: {bg};
    color: {text};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}
QTextEdit, QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox,
QTabWidget::pane {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px;
    color: {text};
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {accent};
}}
QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QPushButton {{
    background-color: {accent};
    color: {accent_text};
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-weight: bold;
}}
QPushButton:hover {{ background-color: {accent_hover}; }}
QPushButton:pressed {{ border: 2px solid {border_hover}; }}
QPushButton:disabled {{ background-color: {border}; color: {muted}; }}
QGroupBox {{
    border: 1px solid {border};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
    color: {accent};
}}
QTableWidget {{
    background-color: {bg};
    alternate-background-color: {surface_alt};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: 6px;
}}
QTableWidget::item:selected {{
    background-color: {accent};
    color: {accent_text};
}}
QHeaderView::section {{
    background-color: {surface};
    color: {text};
    padding: 6px;
    border: 1px solid {border};
    font-weight: bold;
}}
QTabBar::tab {{
    background: {surface};
    color: {text};
    padding: 8px 16px;
    border: 1px solid {border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {accent}; color: {accent_text}; font-weight: bold; }}
QProgressBar {{
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
    background-color: {surface};
    color: {text};
}}
QProgressBar::chunk {{ background-color: {success}; border-radius: 3px; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {bg}; border-radius: 5px; }}
QScrollBar::handle {{ background: {border}; border-radius: 5px; min-height: 20px; min-width: 20px; }}
QScrollBar::handle:hover {{ background: {border_hover}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    background: {surface};
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {accent};
    border: 1px solid {accent};
}}
QMenu {{ background-color: {surface}; color: {text}; border: 1px solid {border}; }}
QMenu::item {{ padding: 6px 24px; }}
QMenu::item:selected {{ background-color: {accent}; color: {accent_text}; }}
QToolTip {{ background-color: {surface}; color: {text}; border: 1px solid {accent}; padding: 4px; }}
""".format(**colors)
    if colors.get("retro"):
        checker = (
            retro_runtime.checkerboard_path()
            if colors.get("checkerboard")
            else ""
        )
        stylesheet += """
QWidget {
    font-family: 'Press Start 2P', 'Cascadia Mono', 'Consolas', monospace;
}
QTextEdit, QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox,
QTabWidget::pane, QPushButton, QGroupBox, QTableWidget, QProgressBar,
QCheckBox::indicator, QRadioButton::indicator, QMenu, QToolTip {
    border-radius: 0px;
}
QTextEdit, QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox,
QTabWidget::pane, QTableWidget, QGroupBox {
    border-width: 2px;
}
QPushButton {
    border: 2px solid #1646a2;
    padding: 9px;
}
QPushButton[emojiButton="true"] {
    font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    font-size: 13px;
}
QPushButton:hover {
    color: #ffffff;
    border-color: #ff8c00;
}
QPushButton:pressed {
    background-color: #ff8c00;
    border: 2px solid #c94f00;
}
QGroupBox::title {
    color: #0a246a;
}
QHeaderView::section {
    border: 2px solid #245edb;
    color: #0a246a;
}
QTableWidget::item:selected {
    background-color: #316ac5;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #3c8d0d;
    border-radius: 0px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #3c8d0d;
    border: 2px solid #1f5f08;
}
QScrollBar::handle {
    background: #316ac5;
    border-radius: 0px;
}
"""
        if checker:
            stylesheet += """
QMainWindow, QMainWindow > QWidget, QDialog {
    background-color: #245edb;
    background-image: url("%s");
    background-repeat: repeat;
}
QGroupBox {
    background-color: #ece9d8;
}
QTableWidget {
    background-color: #ffffff;
}
QTableWidget::item:alternate {
    background-color: #d9e4f7;
}
QPushButton {
    background-color: #316ac5;
}
QPushButton[default="true"] {
    background-color: #3c8d0d;
    border-color: #1f5f08;
}
""" % checker
        if colors.get("dithered"):
            dither = retro_runtime.dither_path()
            if dither:
                stylesheet += """
QMainWindow, QMainWindow > QWidget, QDialog {
    background-color: #2f66b3;
    background-image: url("%s");
    background-repeat: repeat;
}
QWidget {
    color: #f2f0dc;
    font-family: 'Segoe UI', 'Segoe UI Emoji', 'Cascadia Mono', 'Consolas', sans-serif;
    font-size: 16px;
    font-weight: 600;
}
QGroupBox {
    background-color: #2f66b3;
    background-image: url("%s");
    background-repeat: repeat;
    border: 3px solid #102a43;
    margin-top: 18px;
    padding-top: 17px;
}
QGroupBox::title {
    color: #f2f0dc;
    background-color: #2f66b3;
    padding: 2px 8px;
    font-size: 16px;
    font-weight: 700;
}
QTextEdit, QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
    background-color: #f2f0dc;
    color: #102a43;
    border: 3px solid #102a43;
    font-size: 16px;
    font-weight: 600;
    min-height: 22px;
}
QTableWidget {
    background-color: #2f66b3;
    background-image: url("%s");
    background-repeat: repeat;
    alternate-background-color: #2f66b3;
    color: #f2f0dc;
    border: 3px solid #102a43;
    font-size: 16px;
}
QHeaderView::section {
    background-color: #f2f0dc;
    color: #102a43;
    border: 2px solid #102a43;
    font-size: 15px;
    font-weight: 700;
    padding: 8px;
}
QPushButton {
    background-color: #f2f0dc;
    color: #102a43;
    border: 3px solid #102a43;
    font-size: 15px;
    font-weight: 700;
    padding: 9px;
}
QPushButton:hover {
    background-color: #4b8f20;
    color: #f2f0dc;
    border-color: #102a43;
}
QPushButton:disabled {
    background-color: #2f66b3;
    color: #f2f0dc;
    border-color: #102a43;
}
QToolTip {
    background-color: #f2f0dc;
    color: #102a43;
    border: 3px solid #102a43;
    font-size: 15px;
}
QCheckBox, QRadioButton, QLabel {
    color: #f2f0dc;
    font-size: 15px;
    font-weight: 600;
}
QCheckBox::indicator, QRadioButton::indicator {
    background-color: #f2f0dc;
    border: 2px solid #102a43;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #4b8f20;
    border: 2px solid #102a43;
}
QProgressBar {
    background-color: #f2f0dc;
    color: #102a43;
    border: 3px solid #102a43;
}
QProgressBar::chunk {
    background-color: #4b8f20;
}
QPushButton[emojiButton="true"] {
    font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    font-size: 15px;
}
""" % (dither, dither, dither)
    if colors.get("aero"):
        stylesheet += """
QMainWindow {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(196, 231, 252, 115),
        stop:0.45 rgba(98, 174, 224, 100),
        stop:1 rgba(42, 111, 164, 115)
    );
}
QMainWindow > QWidget {
    background-color: rgba(220, 239, 250, 105);
}
QWidget {
    background-color: transparent;
    color: #16354a;
    font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    font-size: 14px;
}
QDialog, QDialog#themeChooserDialog {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(244, 252, 255, 205),
        stop:0.5 rgba(210, 235, 249, 195),
        stop:1 rgba(157, 207, 238, 185)
    );
}
QGroupBox {
    background-color: rgba(255, 255, 255, 118);
    border: 1px solid rgba(65, 116, 151, 205);
    border-radius: 9px;
    margin-top: 16px;
    padding-top: 15px;
}
QGroupBox::title {
    color: #174f78;
    background-color: rgba(240, 249, 255, 180);
    border: 1px solid rgba(91, 142, 174, 180);
    border-radius: 5px;
    padding: 2px 8px;
    left: 10px;
}
QTextEdit, QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
    background-color: rgba(255, 255, 255, 225);
    color: #16354a;
    border: 1px solid #7aa6c2;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #3d8ec9;
    selection-color: #ffffff;
}
QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #2f83bd;
    background-color: rgba(255, 255, 255, 245);
}
QPushButton {
    color: #12364f;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #f8fcff,
        stop:0.46 #cfeafb,
        stop:0.5 #8fc8eb,
        stop:1 #5ca8d8
    );
    border: 1px solid #397da9;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 600;
}
QPushButton:hover {
    color: #0f3148;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:0.45 #e5f6ff,
        stop:0.5 #a9ddf8,
        stop:1 #72bee9
    );
    border: 1px solid #1d6f9f;
}
QPushButton:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #4b94c4,
        stop:1 #b8e1f7
    );
}
QPushButton:disabled {
    color: #778b97;
    background-color: rgba(218, 228, 234, 205);
    border-color: #a8bac5;
}
QTableWidget {
    background-color: rgba(255, 255, 255, 178);
    alternate-background-color: rgba(222, 239, 249, 168);
    color: #16354a;
    border: 1px solid #5f91b1;
    border-radius: 6px;
    gridline-color: #a8c4d6;
}
QTableWidget::item:selected {
    background-color: #3d8ec9;
    color: #ffffff;
}
QHeaderView::section {
    color: #173b54;
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:0.5 #d6edf9,
        stop:1 #9ccbe5
    );
    border: 1px solid #6d9db9;
    padding: 7px;
    font-weight: 600;
}
QCheckBox, QRadioButton, QLabel {
    background-color: transparent;
    color: #16354a;
}
QCheckBox::indicator, QRadioButton::indicator {
    background-color: rgba(255, 255, 255, 230);
    border: 1px solid #5f8da8;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #4b9bd3;
    border: 2px solid #226b9c;
}
QProgressBar {
    background-color: rgba(255, 255, 255, 190);
    color: #16354a;
    border: 1px solid #6793ae;
    border-radius: 5px;
}
QProgressBar::chunk {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #b9eb96,
        stop:0.5 #72bd4e,
        stop:1 #4b9631
    );
    border-radius: 4px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: rgba(225, 239, 247, 190);
    border: 1px solid rgba(91, 142, 174, 160);
    border-radius: 7px;
}
QScrollBar::handle {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #d9f0fc,
        stop:0.5 #7fbee2,
        stop:1 #4c99c8
    );
    border: 1px solid #4d88aa;
    border-radius: 6px;
}
QMenu, QToolTip {
    background-color: rgba(244, 251, 255, 238);
    color: #16354a;
    border: 1px solid #5b8eae;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #4b9bd3;
    color: #ffffff;
}
"""
    if colors.get("metro"):
        stylesheet += """
QMainWindow, QMainWindow > QWidget, QDialog {
    background-color: #180052;
}
QWidget {
    background-color: transparent;
    color: #ffffff;
    font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    font-size: 14px;
}
QGroupBox {
    background-color: #0078d7;
    color: #ffffff;
    border: none;
    border-radius: 0px;
    margin-top: 20px;
    padding: 16px 10px 10px 10px;
}
QGroupBox[metroTile="0"] { background-color: #0078d7; }
QGroupBox[metroTile="1"] { background-color: #00a300; }
QGroupBox[metroTile="2"] { background-color: #6a00ff; }
QGroupBox[metroTile="3"] { background-color: #d83b01; }
QGroupBox[metroTile="4"] { background-color: #0099bc; }
QGroupBox[metroTile="5"] { background-color: #b91d47; }
QGroupBox[metroTile="6"] { background-color: #2d7d9a; }
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0px 4px;
    color: #ffffff;
    background-color: transparent;
    font-family: 'Segoe UI Light', 'Segoe UI', sans-serif;
    font-size: 16px;
    font-weight: 400;
}
QTextEdit, QLineEdit, QTextBrowser, QComboBox, QDateEdit, QSpinBox,
QDoubleSpinBox {
    background-color: #ffffff;
    color: #1f1f1f;
    border: 2px solid #ffffff;
    border-radius: 0px;
    padding: 7px;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}
QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #00a4ef;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1f1f1f;
    border: 2px solid #0078d7;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}
QPushButton {
    background-color: #0078d7;
    color: #ffffff;
    border: 2px solid transparent;
    border-radius: 0px;
    padding: 11px 14px;
    font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    font-size: 14px;
    font-weight: 500;
    text-align: left;
}
QPushButton:hover {
    background-color: #1b8fe5;
    border: 2px solid rgba(255, 255, 255, 180);
}
QPushButton:pressed {
    background-color: #005a9e;
    border: 2px solid #ffffff;
}
QPushButton:disabled {
    background-color: #666666;
    color: #c8c8c8;
}
QTableWidget {
    background-color: #f4f4f4;
    alternate-background-color: #e6e6e6;
    color: #1f1f1f;
    border: none;
    border-radius: 0px;
    gridline-color: #c8c8c8;
    selection-background-color: #0078d7;
    selection-color: #ffffff;
}
QTableWidget::item:selected {
    background-color: #0078d7;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #0078d7;
    color: #ffffff;
    border: none;
    border-right: 2px solid #180052;
    padding: 9px;
    font-size: 14px;
    font-weight: 500;
}
QCheckBox, QRadioButton, QLabel {
    background-color: transparent;
    color: #ffffff;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 17px;
    height: 17px;
    background-color: #ffffff;
    border: 2px solid #ffffff;
    border-radius: 0px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #00a4ef;
    border: 2px solid #ffffff;
}
QProgressBar {
    background-color: #ffffff;
    color: #1f1f1f;
    border: none;
    border-radius: 0px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #00a300;
    border-radius: 0px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #180052;
    border: none;
    border-radius: 0px;
}
QScrollBar::handle {
    background-color: #00a4ef;
    border: none;
    border-radius: 0px;
    min-height: 24px;
    min-width: 24px;
}
QScrollBar::handle:hover { background-color: #29b6f6; }
QMenu, QToolTip {
    background-color: #252525;
    color: #ffffff;
    border: 2px solid #00a4ef;
    border-radius: 0px;
}
QMenu::item:selected {
    background-color: #0078d7;
    color: #ffffff;
}
"""
    if colors.get("win31"):
        stylesheet += """
QWidget {
    background-color: transparent;
    color: #000000;
    font-family: 'Microsoft Sans Serif', 'Tahoma', 'Segoe UI', 'Arial', sans-serif;
    font-size: 14px;
}
QMainWindow, QMainWindow > QWidget, QDialog,
QDialog#themeChooserDialog {
    background-color: #008080;
}
QGroupBox {
    background-color: #c0c0c0;
    color: #000000;
    border-top: 22px solid #000080;
    border-left: 2px solid #000000;
    border-right: 2px solid #000000;
    border-bottom: 2px solid #000000;
    border-radius: 0px;
    margin-top: 0px;
    padding: 9px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: border;
    subcontrol-position: top left;
    left: 5px;
    top: 2px;
    padding: 1px 4px;
    color: #ffffff;
    background-color: #000080;
    border: none;
    border-radius: 0px;
    font-weight: bold;
}
QTextEdit, QLineEdit, QTextBrowser, QComboBox, QDateEdit, QSpinBox,
QDoubleSpinBox {
    background-color: #ffffff;
    color: #000000;
    border-top: 2px solid #000000;
    border-left: 2px solid #000000;
    border-bottom: 2px solid #ffffff;
    border-right: 2px solid #ffffff;
    border-radius: 0px;
    padding: 3px 5px;
    selection-background-color: #000080;
    selection-color: #ffffff;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
    min-height: 24px;
}
QDateEdit {
    padding: 1px 0px;
    font-size: 11px;
}
QDateEdit::drop-down {
    width: 14px;
    border-left: 1px solid #808080;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid #000000;
    selection-background-color: #000080;
    selection-color: #ffffff;
}
QPushButton {
    background-color: #c0c0c0;
    color: #000000;
    border-top: 2px solid #ffffff;
    border-left: 2px solid #ffffff;
    border-bottom: 2px solid #000000;
    border-right: 2px solid #000000;
    border-radius: 0px;
    padding: 7px 12px;
    font-family: 'Microsoft Sans Serif', 'Tahoma', 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
    font-weight: normal;
}
QPushButton:hover {
    background-color: #d4d4d4;
}
QPushButton:pressed {
    background-color: #a0a0a0;
    border-top: 2px solid #000000;
    border-left: 2px solid #000000;
    border-bottom: 2px solid #ffffff;
    border-right: 2px solid #ffffff;
    padding: 8px 11px 6px 13px;
}
QPushButton:disabled {
    color: #808080;
    background-color: #c0c0c0;
}
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #e8e8e8;
    color: #000000;
    border-top: 2px solid #000000;
    border-left: 2px solid #000000;
    border-bottom: 2px solid #ffffff;
    border-right: 2px solid #ffffff;
    border-radius: 0px;
    gridline-color: #808080;
    font-size: 14px;
}
QTableWidget::item:selected {
    background-color: #000080;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #c0c0c0;
    color: #000000;
    border-top: 2px solid #ffffff;
    border-left: 2px solid #ffffff;
    border-bottom: 2px solid #000000;
    border-right: 2px solid #000000;
    padding: 6px;
    font-size: 14px;
    font-weight: bold;
}
QTabBar::tab {
    background-color: #c0c0c0;
    color: #000000;
    border-top: 2px solid #ffffff;
    border-left: 2px solid #ffffff;
    border-bottom: 2px solid #000000;
    border-right: 2px solid #000000;
    border-radius: 0px;
    padding: 7px 12px;
    font-size: 14px;
}
QTabBar::tab:selected {
    background-color: #000080;
    color: #ffffff;
}
QCheckBox, QRadioButton, QLabel {
    background-color: transparent;
    color: #000000;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 13px;
    height: 13px;
    background-color: #ffffff;
    border: 1px solid #000000;
    border-radius: 0px;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #000080;
    border: 2px solid #000000;
}
QProgressBar {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid #000000;
    border-radius: 0px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #000080;
    border-radius: 0px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #c0c0c0;
    border: 1px solid #000000;
    border-radius: 0px;
}
QScrollBar::handle {
    background-color: #c0c0c0;
    border-top: 2px solid #ffffff;
    border-left: 2px solid #ffffff;
    border-bottom: 2px solid #000000;
    border-right: 2px solid #000000;
    border-radius: 0px;
    min-height: 22px;
    min-width: 22px;
}
QMenu, QToolTip {
    background-color: #c0c0c0;
    color: #000000;
    border: 2px solid #000000;
    border-radius: 0px;
}
QMenu::item:selected {
    background-color: #000080;
    color: #ffffff;
}
"""
    return stylesheet
