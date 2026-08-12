"""Retro-theme textures, palettes, and image dithering."""

from functools import lru_cache

try:
    import numpy as np
except ImportError:
    np = None

from PyQt6.QtCore import QDir, QStandardPaths, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap


BUTTON_STYLE = """
    QPushButton {
        background-color: #f2f0dc;
        color: #102a43;
        border: 3px solid #102a43;
        border-radius: 0px;
        padding: 9px;
        font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
        font-size: 15px;
        font-weight: 700;
    }
    QPushButton:hover {
        background-color: #4b8f20;
        color: #f2f0dc;
    }
    QPushButton:disabled {
        background-color: #2f66b3;
        color: #f2f0dc;
    }
"""

STATS_STYLE = (
    "color: #f2f0dc; font-size: 16px; font-weight: 700; "
    "background-color: #2f66b3; padding: 3px;"
)

_BAYER = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def checkerboard_path():
    """Create the tiny tiled XP-blue checker texture."""
    base_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    if not base_dir:
        return ""
    theme_dir = QDir(base_dir).filePath("themes")
    QDir().mkpath(theme_dir)
    path = QDir(theme_dir).filePath("xp_8bit_checker.png")

    image = QImage(16, 16, QImage.Format.Format_RGB32)
    blue = QColor("#245edb")
    light_blue = QColor("#4f86d9")
    for y in range(16):
        for x in range(16):
            alternate = ((x // 8) + (y // 8)) % 2
            image.setPixelColor(x, y, light_blue if alternate else blue)
    image.save(path, "PNG")
    return path.replace("\\", "/")


def dither_path():
    """Create a visible two-color ordered-dither tile."""
    base_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    if not base_dir:
        return ""
    theme_dir = QDir(base_dir).filePath("themes")
    QDir().mkpath(theme_dir)
    path = QDir(theme_dir).filePath("xp_readable_dither.png")

    image = QImage(8, 8, QImage.Format.Format_RGB32)
    paper = QColor("#f2f0dc")
    blue = QColor("#2f66b3")
    for y in range(8):
        for x in range(8):
            is_paper = (x % 2 == 0) and (y % 2 == 0)
            image.setPixelColor(x, y, paper if is_paper else blue)
    image.save(path, "PNG")
    return path.replace("\\", "/")


@lru_cache(maxsize=512)
def dither_palette(color_count, palette_kind="xp"):
    """Generate a theme-specific palette containing exactly 2-256 colors."""
    color_count = max(2, min(256, int(color_count)))
    if color_count == 256:
        return [
            QColor(
                round(red * 255 / 7),
                round(green * 255 / 7),
                round(blue * 255 / 3),
            )
            for red in range(8)
            for green in range(8)
            for blue in range(4)
        ]
    if palette_kind == "win31":
        selected = [
            QColor("#000000"), QColor("#ffffff"), QColor("#c0c0c0"),
            QColor("#000080"), QColor("#008080"), QColor("#008000"),
            QColor("#800000"), QColor("#800080"), QColor("#808000"),
            QColor("#808080"), QColor("#0000ff"), QColor("#00ffff"),
            QColor("#00ff00"), QColor("#ff0000"), QColor("#ff00ff"),
            QColor("#ffff00"),
        ]
    else:
        selected = [
            QColor("#102a43"),
            QColor("#f2f0dc"),
            QColor("#2f66b3"),
            QColor("#4b8f20"),
        ]
    if color_count <= len(selected):
        return selected[:color_count]

    candidates = []
    for ordinal in range(256):
        reversed_index = int(f"{ordinal:08b}"[::-1], 2)
        candidates.append(
            QColor(
                round(((reversed_index >> 5) & 0b111) * 255 / 7),
                round(((reversed_index >> 2) & 0b111) * 255 / 7),
                round((reversed_index & 0b11) * 255 / 3),
            )
        )
    selected_rgb = {(c.red(), c.green(), c.blue()) for c in selected}
    selected.extend(
        color for color in candidates
        if (color.red(), color.green(), color.blue()) not in selected_rgb
    )
    return selected[:color_count]


def rgb332_dither_color(color, threshold):
    """Constant-time ordered quantization for the complete color map."""
    def quantize(channel, levels):
        step = 255 / (levels - 1)
        adjusted = max(0, min(255, channel + (threshold - 0.5) * step))
        return round(round(adjusted / step) * step)

    return QColor(
        quantize(color.red(), 8),
        quantize(color.green(), 8),
        quantize(color.blue(), 4),
        color.alpha(),
    )


@lru_cache(maxsize=262144)
def nearest_palette_pair(
    color_count, palette_kind, red_5bit, green_5bit, blue_5bit
):
    """Return two nearby palette indexes using a shared 15-bit lookup."""
    palette = dither_palette(color_count, palette_kind)
    red, green, blue = red_5bit * 8 + 4, green_5bit * 8 + 4, blue_5bit * 8 + 4
    nearest_index, second_index = 0, 1
    nearest_distance = second_distance = float("inf")
    for index, color in enumerate(palette):
        distance = (
            (red - color.red()) ** 2
            + (green - color.green()) ** 2
            + (blue - color.blue()) ** 2
        )
        if distance < nearest_distance:
            second_index, second_distance = nearest_index, nearest_distance
            nearest_index, nearest_distance = index, distance
        elif distance < second_distance:
            second_index, second_distance = index, distance
    mix = nearest_distance / max(1, nearest_distance + second_distance)
    return nearest_index, second_index, mix


@lru_cache(maxsize=8)
def numpy_palette_lut(color_count, palette_kind):
    """Build a compact 15-bit nearest-pair lookup for full-size pictures."""
    if np is None:
        return None
    palette = np.array(
        [(c.red(), c.green(), c.blue())
         for c in dither_palette(color_count, palette_kind)],
        dtype=np.int32,
    )
    indexes = np.arange(32768, dtype=np.int32)
    samples = np.column_stack(
        (
            ((indexes >> 10) & 31) * 8 + 4,
            ((indexes >> 5) & 31) * 8 + 4,
            (indexes & 31) * 8 + 4,
        )
    )
    nearest = np.empty(32768, dtype=np.uint8)
    second = np.empty(32768, dtype=np.uint8)
    mix = np.empty(32768, dtype=np.float32)
    for start in range(0, 32768, 2048):
        stop = min(start + 2048, 32768)
        delta = samples[start:stop, None, :] - palette[None, :, :]
        distances = np.sum(delta * delta, axis=2)
        pair = np.argpartition(distances, 1, axis=1)[:, :2]
        pair_distances = np.take_along_axis(distances, pair, axis=1)
        order = np.argsort(pair_distances, axis=1)
        first = np.take_along_axis(pair, order[:, :1], axis=1)[:, 0]
        runner_up = np.take_along_axis(pair, order[:, 1:2], axis=1)[:, 0]
        first_distance = distances[np.arange(stop - start), first]
        second_distance = distances[np.arange(stop - start), runner_up]
        nearest[start:stop] = first
        second[start:stop] = runner_up
        mix[start:stop] = first_distance / np.maximum(
            1, first_distance + second_distance
        )
    return nearest, second, mix


def dithered_emoji_icon(symbol, color_count=4, palette_kind="xp", size=20):
    """Render an emoji, then quantize it to the selected Bayer palette."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    font = QFont("Segoe UI Emoji")
    font.setPixelSize(size - 3)
    painter.setFont(font)
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    painter.end()

    palette = dither_palette(color_count, palette_kind)
    for y in range(size):
        for x in range(size):
            source = image.pixelColor(x, y)
            threshold = (_BAYER[y % 4][x % 4] + 0.5) / 16.0
            if source.alphaF() < threshold:
                image.setPixelColor(x, y, QColor(0, 0, 0, 0))
                continue
            if len(palette) == 256:
                chosen = rgb332_dither_color(source, threshold)
            else:
                nearest, second, mix = nearest_palette_pair(
                    len(palette), palette_kind,
                    source.red() >> 3, source.green() >> 3, source.blue() >> 3,
                )
                chosen = palette[second] if threshold < mix else palette[nearest]
            image.setPixelColor(x, y, chosen)
    return QIcon(QPixmap.fromImage(image))


def dithered_thumbnail(
    pixmap, color_count=4, palette_kind="xp", working_size=36
):
    """Reduce a thumbnail to pixel art and ordered-dither its color map."""
    if pixmap.isNull():
        return pixmap
    source = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    small = source.scaled(
        working_size,
        working_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    palette = dither_palette(color_count, palette_kind)
    for y in range(small.height()):
        for x in range(small.width()):
            color = small.pixelColor(x, y)
            threshold = (_BAYER[y % 4][x % 4] + 0.5) / 16.0
            if len(palette) == 256:
                chosen = rgb332_dither_color(color, threshold)
            else:
                nearest, second, mix = nearest_palette_pair(
                    len(palette), palette_kind,
                    color.red() >> 3, color.green() >> 3, color.blue() >> 3,
                )
                chosen = QColor(palette[second] if threshold < mix else palette[nearest])
                chosen.setAlpha(color.alpha())
            small.setPixelColor(x, y, chosen)
    return QPixmap.fromImage(small).scaled(
        pixmap.size(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


def dithered_picture(pixmap, color_count=4, palette_kind="xp"):
    """Dither a viewer image without changing its pixel dimensions."""
    if pixmap.isNull():
        return pixmap
    if np is None:
        return dithered_thumbnail(
            pixmap, color_count, palette_kind,
            working_size=max(pixmap.width(), pixmap.height()),
        )

    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = image.width(), image.height()
    pointer = image.bits()
    pointer.setsize(image.sizeInBytes())
    rows = np.frombuffer(pointer, dtype=np.uint8).reshape(
        height, image.bytesPerLine()
    )
    rgba = rows[:, : width * 4].reshape(height, width, 4).copy()
    bayer = np.array(_BAYER, dtype=np.float32)
    thresholds = (
        np.tile(bayer, ((height + 3) // 4, (width + 3) // 4))[:height, :width]
        + 0.5
    ) / 16.0

    color_count = max(2, min(256, int(color_count)))
    if color_count == 256:
        rgb = rgba[:, :, :3].astype(np.float32)
        steps = np.array((255.0 / 7.0, 255.0 / 7.0, 255.0 / 3.0))
        adjusted = np.clip(
            rgb + (thresholds[:, :, None] - 0.5) * steps, 0, 255
        )
        quantized = np.rint(np.rint(adjusted / steps) * steps)
        rgba[:, :, :3] = np.clip(quantized, 0, 255).astype(np.uint8)
    else:
        palette = np.array(
            [(c.red(), c.green(), c.blue())
             for c in dither_palette(color_count, palette_kind)],
            dtype=np.uint8,
        )
        lookup_index = (
            ((rgba[:, :, 0].astype(np.uint16) >> 3) << 10)
            | ((rgba[:, :, 1].astype(np.uint16) >> 3) << 5)
            | (rgba[:, :, 2].astype(np.uint16) >> 3)
        )
        nearest_lut, second_lut, mix_lut = numpy_palette_lut(
            color_count, palette_kind
        )
        nearest = nearest_lut[lookup_index]
        second = second_lut[lookup_index]
        selected = np.where(
            thresholds < mix_lut[lookup_index], second, nearest
        )
        rgba[:, :, :3] = palette[selected]

    result = QImage(
        rgba.data,
        width,
        height,
        int(rgba.strides[0]),
        QImage.Format.Format_RGBA8888,
    ).copy()
    return QPixmap.fromImage(result)
