import os
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QDoubleSpinBox, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt

# The theme template for scaling
BASE_THEME_TEMPLATE = """
QWidget {{ 
    background-color: #1e1e2e; 
    color: #cdd6f4; 
    font-family: 'Segoe UI', Arial, sans-serif; 
    font-size: {fs}px; 
}}
QTextEdit, QComboBox, QDateEdit, QSpinBox, QTabWidget::pane {{ 
    background-color: #313244; 
    border: 1px solid #45475a; 
    border-radius: {br}px; 
    padding: {p}px; 
    color: #cdd6f4; 
}}
QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{ 
    border: 1px solid #89b4fa; 
}}
QPushButton {{ 
    background-color: #89b4fa; 
    color: #11111b; 
    border: none; 
    border-radius: {br}px; 
    padding: {p_btn}px; 
    font-weight: bold; 
}}
QPushButton:hover {{ background-color: #b4befe; }}
QPushButton:disabled {{ background-color: #45475a; color: #a6adc8; }}
QGroupBox {{ 
    border: 1px solid #45475a; 
    border-radius: {br_lg}px; 
    margin-top: {m_top}px; 
    padding-top: {p_top}px; 
    font-weight: bold; 
}}
QGroupBox::title {{ 
    subcontrol-origin: margin; 
    subcontrol-position: top left; 
    padding: 0 {p}px; 
    left: {p_lg}px; 
    color: #89b4fa; 
}}
QTableWidget {{ 
    background-color: #1e1e2e; 
    alternate-background-color: #2a2b3d; 
    gridline-color: #45475a; 
    border: 1px solid #45475a; 
    border-radius: {br}px; 
}}
QTableWidget::item:selected {{ background-color: #45475a; }}
QHeaderView::section {{ 
    background-color: #313244; 
    color: #cdd6f4; 
    padding: {p}px; 
    border: 1px solid #45475a; 
    font-weight: bold; 
}}
QTabBar::tab {{ 
    background: #313244; 
    color: #cdd6f4; 
    padding: {p}px {p_lg}px; 
    border: 1px solid #45475a; 
    border-bottom: none; 
    border-top-left-radius: {br}px; 
    border-top-right-radius: {br}px; 
    margin-right: 2px; 
}}
QTabBar::tab:selected {{ 
    background: #89b4fa; 
    color: #11111b; 
    font-weight: bold; 
}}
QProgressBar {{ 
    border: 1px solid #45475a; 
    border-radius: 4px; 
    text-align: center; 
    background-color: #313244; 
    color: #cdd6f4; 
}}
QProgressBar::chunk {{ background-color: #a6e3a1; border-radius: 3px; }}
QScrollBar:vertical, QScrollBar:horizontal {{ 
    background: #1e1e2e; 
    border-radius: 5px; 
}}
QScrollBar::handle {{ background: #45475a; border-radius: 5px; }}
QScrollBar::handle:hover {{ background: #585b70; }}
QCheckBox::indicator, QRadioButton::indicator {{ 
    width: {sz_ind}px; 
    height: {sz_ind}px; 
    border: 1px solid #45475a; 
    background: #313244; 
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ 
    background: #89b4fa; 
    border: 1px solid #89b4fa; 
}}
QMenu {{ background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; }}
QMenu::item {{ padding: {p}px 24px; }}
QMenu::item:selected {{ background-color: #89b4fa; color: #11111b; }}
"""

def apply_theme_scale(app, scale):
    """Helper function to apply the scaled CSS to the app."""
    scaled_style = BASE_THEME_TEMPLATE.format(
        fs=int(13 * scale),
        br=int(6 * scale),
        p=int(6 * scale),
        p_btn=int(10 * scale),
        br_lg=int(8 * scale),
        m_top=int(14 * scale),
        p_top=int(14 * scale),
        p_lg=int(10 * scale),
        sz_ind=int(16 * scale)
    )
    app.setStyleSheet(scaled_style)

class UIScaleDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("UI Scaling Settings")
        self.setFixedSize(300, 150)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        layout = QVBoxLayout(self)

        group = QGroupBox("Interface Scale")
        group_layout = QHBoxLayout(group)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 3.0)
        self.scale_spin.setSingleStep(0.1)
        # Load the current scale from the app if it exists
        current_scale = getattr(app, "current_ui_scale", 1.0)
        self.scale_spin.setValue(current_scale)

        self.apply_btn = QPushButton("Apply Scale")
        self.apply_btn.clicked.connect(self.apply_scaling)

        group_layout.addWidget(QLabel("Scale:"))
        group_layout.addWidget(self.scale_spin)
        group_layout.addWidget(self.apply_btn)

        layout.addWidget(group)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def apply_scaling(self):
        s = self.scale_spin.value()
        self.app.current_ui_scale = s # Update the tracked scale
        apply_theme_scale(self.app, s)

def setup(app):
    """Entry point for the ExtensionManager"""
    
    # 1. DETECT RESOLUTION AND AUTO-SCALE
    screen = QApplication.primaryScreen()
    if screen:
        width = screen.size().width()
        height = screen.size().height()
        
        # If smaller than 1080p (1920x1080)
        if width < 1920 or height < 1080:
            # Calculate a scale factor based on the most limiting dimension
            # Example: 1366 / 1920 = 0.71
            auto_scale = min(width / 1920, height / 1080)
            # Clamp it so it doesn't get absurdly small (min 0.6)
            auto_scale = max(0.6, auto_scale)
            
            app.current_ui_scale = auto_scale
            apply_theme_scale(app, auto_scale)
            print(f"Auto-scaled UI to {auto_scale:.2f} based on resolution {width}x{height}")
        else:
            app.current_ui_scale = 1.0
            print("Resolution is 1080p or higher. Using default scale.")

    # 2. CREATE THE CONTROL BUTTON
    btn_open_settings = QPushButton("⚙️ UI Scale")
    
    dialog_ref = None 

    def open_window():
        nonlocal dialog_ref
        dialog_ref = UIScaleDialog(app)
        dialog_ref.show()

    btn_open_settings.clicked.connect(open_window)
    app.add_extension_button(btn_open_settings)
    print("UI Scaler with Auto-Detection loaded.")
