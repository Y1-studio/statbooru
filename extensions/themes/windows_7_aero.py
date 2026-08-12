"""Windows 7 Aero runtime: native blur, alpha surfaces, and live toggling."""

import ctypes
import ctypes.util
import os
import sys

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QPushButton,
    QWidget,
)


OPAQUE_FALLBACK_STYLE = """
QMainWindow, QMainWindow > QWidget, QDialog,
QDialog#themeChooserDialog {
    background: #dceef8;
}
"""

BACKING_STYLE = """
QWidget#_aeroGlassBacking {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(244, 252, 255, 205),
        stop:0.5 rgba(210, 235, 249, 195),
        stop:1 rgba(157, 207, 238, 185)
    );
    border: none;
}
"""

BUTTON_STYLE = """
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
    padding: 8px 11px;
    font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:0.45 #e5f6ff,
        stop:0.5 #a9ddf8,
        stop:1 #72bee9
    );
    border-color: #1d6f9f;
}
QPushButton:disabled {
    color: #778b97;
    background-color: rgba(218, 228, 234, 205);
    border-color: #a8bac5;
}
"""

STATS_STYLE = (
    "color: #174f78; font-size: 15px; font-weight: 700; "
    "background-color: rgba(255, 255, 255, 150); "
    "border: 1px solid rgba(91, 142, 174, 170); "
    "border-radius: 5px; padding: 4px 8px;"
)


def set_native_glass(window, enabled):
    """Enable live DWM blur behind a Windows Qt top-level window."""
    if sys.platform != "win32":
        return False
    try:
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(window.winId()))
        dwmapi = ctypes.WinDLL("dwmapi")

        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_int),
                ("right", ctypes.c_int),
                ("top", ctypes.c_int),
                ("bottom", ctypes.c_int),
            ]

        class DWM_BLURBEHIND(ctypes.Structure):
            _fields_ = [
                ("flags", wintypes.DWORD),
                ("enable", wintypes.BOOL),
                ("blur_region", wintypes.HANDLE),
                ("transition_on_maximized", wintypes.BOOL),
            ]

        blur = DWM_BLURBEHIND()
        blur.flags = 0x00000001
        blur.enable = bool(enabled)
        dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(blur))

        margin = -1 if enabled else 0
        margins = MARGINS(margin, margin, margin, margin)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

        try:
            backdrop_type = ctypes.c_int(3 if enabled else 1)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                38,
                ctypes.byref(backdrop_type),
                ctypes.sizeof(backdrop_type),
            )
        except AttributeError:
            pass

        try:
            class ACCENT_POLICY(ctypes.Structure):
                _fields_ = [
                    ("state", ctypes.c_int),
                    ("flags", ctypes.c_int),
                    ("gradient_color", ctypes.c_uint),
                    ("animation_id", ctypes.c_int),
                ]

            class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
                _fields_ = [
                    ("attribute", ctypes.c_int),
                    ("data", ctypes.c_void_p),
                    ("size", ctypes.c_size_t),
                ]

            policy = ACCENT_POLICY()
            policy.state = 3 if enabled else 0
            policy.gradient_color = 0x55F5DCB4 if enabled else 0
            composition_data = WINDOWCOMPOSITIONATTRIBDATA(
                19,
                ctypes.cast(ctypes.byref(policy), ctypes.c_void_p),
                ctypes.sizeof(policy),
            )
            ctypes.windll.user32.SetWindowCompositionAttribute(
                hwnd,
                ctypes.byref(composition_data),
            )
        except (AttributeError, OSError):
            pass
        return True
    except (AttributeError, OSError, RuntimeError, ValueError):
        return False


def set_linux_blur(window, enabled):
    """Request real KWin blur behind an X11/XWayland window."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        if "xcb" not in QApplication.platformName().lower():
            return False
        display_name = os.environ.get("DISPLAY")
        library_name = ctypes.util.find_library("X11")
        if not display_name or not library_name:
            return False

        x11 = ctypes.CDLL(library_name)
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XInternAtom.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XChangeProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        x11.XDeleteProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        x11.XFlush.argtypes = [ctypes.c_void_p]

        display = x11.XOpenDisplay(display_name.encode())
        if not display:
            return False
        try:
            blur_atom = x11.XInternAtom(
                display,
                b"_KDE_NET_WM_BLUR_BEHIND_REGION",
                0,
            )
            if not blur_atom:
                return False
            window_id = ctypes.c_ulong(int(window.winId()))
            if enabled:
                cardinal_atom = x11.XInternAtom(display, b"CARDINAL", 0)
                x11.XChangeProperty(
                    display,
                    window_id,
                    blur_atom,
                    cardinal_atom,
                    32,
                    0,
                    None,
                    0,
                )
            else:
                x11.XDeleteProperty(display, window_id, blur_atom)
            x11.XFlush(display)
            return True
        finally:
            x11.XCloseDisplay(display)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return False


def set_platform_glass(window, enabled):
    if sys.platform == "win32":
        return set_native_glass(window, enabled)
    if sys.platform.startswith("linux"):
        return set_linux_blur(window, enabled)
    return False


class AeroController(QObject):
    """Own all state and platform behavior specific to Windows 7 Aero."""

    def __init__(self, switcher, themes):
        super().__init__(switcher.app)
        self.switcher = switcher
        self.themes = themes
        self.enabled = switcher.settings.value(
            "aero_transparency_enabled",
            True,
            type=bool,
        )
        self._surface_generation = 0
        QApplication.instance().installEventFilter(self)

    def enabled_for(self, name):
        return bool(self.themes.get(name, {}).get("aero") and self.enabled)

    def add_dialog_controls(self, dialog, layout):
        """Add the controls that exist only for the Aero theme."""
        dialog.aero_transparency = QCheckBox(
            "Enable real Aero transparency"
        )
        dialog.aero_transparency.setToolTip(
            "Applies to the Windows 7 Aero theme. Open windows are refreshed "
            "immediately; no program restart is required."
        )
        layout.addWidget(dialog.aero_transparency)

        dialog.apply_aero_button = QPushButton(
            "Apply Aero Transparency"
        )
        dialog.apply_aero_button.clicked.connect(
            lambda: self.apply_dialog_setting(dialog)
        )
        layout.addWidget(dialog.apply_aero_button)

    def sync_dialog_controls(self, dialog, name):
        """Show and populate Aero controls only when Aero is selected."""
        visible = bool(self.themes.get(name, {}).get("aero"))
        dialog.aero_transparency.setVisible(visible)
        dialog.apply_aero_button.setVisible(visible)
        if visible:
            dialog.aero_transparency.setChecked(self.enabled)

    def apply_dialog_setting(self, dialog):
        """Apply the checkbox immediately and provide button feedback."""
        self.set_enabled(dialog.aero_transparency.isChecked())
        dialog.apply_aero_button.setText("Applying\u2026")
        QTimer.singleShot(
            500,
            lambda: dialog.apply_aero_button.setText("Applied"),
        )
        QTimer.singleShot(
            1400,
            lambda: dialog.apply_aero_button.setText(
                "Apply Aero Transparency"
            ),
        )

    def stylesheet_suffix(self, name):
        if self.themes.get(name, {}).get("aero") and not self.enabled:
            return OPAQUE_FALLBACK_STYLE
        return ""

    def eventFilter(self, watched, event):
        current = getattr(self.switcher.app, "current_theme_name", "")
        active = self.enabled_for(current)
        if event.type() == QEvent.Type.Polish and isinstance(watched, QDialog):
            watched.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground,
                active,
            )
            watched.setAttribute(
                Qt.WidgetAttribute.WA_StyledBackground,
                True,
            )
            self.ensure_dialog_backing(watched, active)
        if (
            event.type() == QEvent.Type.Resize
            and isinstance(watched, QDialog)
            and active
        ):
            self.ensure_dialog_backing(watched, True)
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QDialog)
            and active
        ):
            QTimer.singleShot(
                0,
                lambda window=watched: self.set_window_glass(
                    window,
                    self.enabled_for(
                        getattr(
                            self.switcher.app,
                            "current_theme_name",
                            "",
                        )
                    ),
                ),
            )
        return False

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.switcher.settings.setValue(
            "aero_transparency_enabled",
            self.enabled,
        )
        name = getattr(self.switcher.app, "current_theme_name", "")
        if not self.themes.get(name, {}).get("aero"):
            return
        self.switcher._style_epoch += 1
        self.switcher._forced_window_signatures.clear()
        self.switcher.app.setStyleSheet(
            self.switcher._stylesheet_for_name(name)
        )
        self.switcher._refresh_widget_overrides()
        if self.switcher.force_theme:
            self.switcher._apply_force_theme()
        self.refresh_surfaces(self.enabled)

    def apply_theme(self, name):
        active = self.enabled_for(name)
        self.switcher.app.setWindowOpacity(1.0)
        self.refresh_surfaces(active)

    def refresh_surfaces(self, enabled):
        self._surface_generation += 1
        generation = self._surface_generation
        targets = [
            window
            for window in QApplication.topLevelWidgets()
            if window is self.switcher.app or isinstance(window, QDialog)
        ]
        if self.switcher.app not in targets:
            targets.insert(0, self.switcher.app)

        for window in targets:
            try:
                rebuild_opaque_surface = (
                    not enabled
                    and window.isVisible()
                    and window.testAttribute(
                        Qt.WidgetAttribute.WA_TranslucentBackground
                    )
                )
                if rebuild_opaque_surface:
                    window.hide()
                window.setAttribute(
                    Qt.WidgetAttribute.WA_TranslucentBackground,
                    enabled,
                )
                if isinstance(window, QDialog):
                    window.setAttribute(
                        Qt.WidgetAttribute.WA_StyledBackground,
                        True,
                    )
                    self.ensure_dialog_backing(window, enabled)
                set_platform_glass(window, enabled)
                if rebuild_opaque_surface:
                    window.show()
                    window.raise_()
                window.update()
            except RuntimeError:
                pass

        QTimer.singleShot(
            0,
            lambda: self.set_all_native_glass(enabled, generation),
        )
        QTimer.singleShot(
            100,
            lambda: self.set_all_native_glass(enabled, generation),
        )

    def set_all_native_glass(self, enabled, generation=None):
        if (
            generation is not None
            and generation != self._surface_generation
        ):
            return
        available = False
        for window in QApplication.topLevelWidgets():
            if (
                window is self.switcher.dialog
                or window is self.switcher.app
                or isinstance(window, QDialog)
            ):
                available = self.set_window_glass(window, enabled) or available
        self.switcher.app.aero_glass_available = available

    def set_window_glass(self, window, enabled):
        try:
            window.setWindowOpacity(1.0)
            if window is not self.switcher.app:
                window.setAttribute(
                    Qt.WidgetAttribute.WA_TranslucentBackground,
                    enabled,
                )
                window.setAttribute(
                    Qt.WidgetAttribute.WA_StyledBackground,
                    True,
                )
                if isinstance(window, QDialog):
                    self.ensure_dialog_backing(window, enabled)
            return set_platform_glass(window, enabled)
        except RuntimeError:
            return False

    def ensure_dialog_backing(self, dialog, enabled):
        backing = getattr(dialog, "_aero_glass_backing", None)
        if not enabled:
            if not getattr(dialog, "_aero_surface_used", False):
                if backing is not None:
                    backing.hide()
                return
            if backing is None:
                backing = QWidget(dialog)
                backing.setObjectName("_aeroGlassBacking")
                backing.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                    True,
                )
                backing.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                dialog._aero_glass_backing = backing
            current = getattr(
                self.switcher.app,
                "current_theme_name",
                "",
            )
            background = self.themes.get(current, {}).get(
                "bg",
                "#f0f0f0",
            )
            backing.setStyleSheet(
                "QWidget#_aeroGlassBacking { "
                f"background-color: {background}; border: none; }}"
            )
            backing.setGeometry(dialog.rect())
            backing.show()
            backing.lower()
            return
        if backing is None:
            backing = QWidget(dialog)
            backing.setObjectName("_aeroGlassBacking")
            backing.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
            backing.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            dialog._aero_glass_backing = backing
        dialog._aero_surface_used = True
        backing.setStyleSheet(BACKING_STYLE)
        backing.setGeometry(dialog.rect())
        backing.show()
        backing.lower()
