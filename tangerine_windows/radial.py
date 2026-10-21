"""
Menú radial flotante de alta fidelidad para Tangerine Windows.
Dibuja los gajos (wedges), el anillo exterior y el centro con la estética exacta
de Tangerine (modo oscuro + resaltado naranja vibrante).
Soporta Imágenes, Audio y Video (hasta 12 opciones simultáneas).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

from .convert import get_available_formats


def clock_to_cartesian(cx: float, cy: float, radius: float, clock_deg: float) -> QPointF:
    """Convierte ángulo horario (0° = 12:00, 90° = 3:00) a coordenadas de pantalla."""
    rad = math.radians(clock_deg)
    return QPointF(cx + radius * math.sin(rad), cy - radius * math.cos(rad))


def make_wedge_path(
    cx: float,
    cy: float,
    r_in: float,
    r_out: float,
    clock_start_deg: float,
    clock_sweep_deg: float,
) -> QPainterPath:
    """Construye el contorno de un gajo anular horario."""
    path = QPainterPath()
    outer_rect = QRectF(cx - r_out, cy - r_out, 2 * r_out, 2 * r_out)
    inner_rect = QRectF(cx - r_in, cy - r_in, 2 * r_in, 2 * r_in)
    
    qt_start = 90.0 - clock_start_deg
    qt_sweep = -clock_sweep_deg
    
    path.arcMoveTo(outer_rect, qt_start)
    path.arcTo(outer_rect, qt_start, qt_sweep)
    path.arcTo(inner_rect, qt_start + qt_sweep, -qt_sweep)
    path.closeSubpath()
    return path


class RadialMenu(QWidget):
    file_dropped = Signal(list, str)
    menu_closed = Signal()

    def __init__(self, size: int = 360, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.menu_size = size
        self.radius = size / 2

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(size, size)

        self.file_paths: List[str] = []
        self.formats: List[str] = ["JPEG", "WebP", "HEIC", "TIFF", "BMP", "GIF"]
        self.hover_index: int = -1
        self.has_drag: bool = False
        self.scale_factor: float = 1.0

        # Animación de resorte
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setStartValue(0.68)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_scale_anim)

        # Radios por defecto
        self._update_radii()

    def _update_radii(self):
        n = len(self.formats)
        self.outer_ring_outer_r = self.radius - 8
        self.outer_ring_inner_r = self.outer_ring_outer_r - 5
        self.wedge_outer_r = self.outer_ring_inner_r - 5
        
        # Para 10+ gajos (p.ej. videos), ajustamos ligeramente el radio interno
        if n >= 10:
            self.wedge_inner_r = 66.0
            self.center_hub_r = 56.0
        else:
            self.wedge_inner_r = 60.0
            self.center_hub_r = 52.0

    def _on_scale_anim(self, value):
        self.scale_factor = float(value)
        self.update()

    def popup_at(self, pos: QPoint, paths: Optional[List[str]] = None):
        self.file_paths = paths or []
        if self.file_paths:
            self.formats = get_available_formats(self.file_paths)
        else:
            self.formats = ["JPEG", "WebP", "HEIC", "TIFF", "BMP", "GIF"]

        self._update_radii()
        self.hover_index = -1
        self.has_drag = bool(paths)

        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        geom = screen.geometry()
        
        top_left_x = int(pos.x() - self.radius)
        top_left_y = int(pos.y() - self.radius)
        
        top_left_x = max(geom.left() + 10, min(top_left_x, geom.right() - self.menu_size - 10))
        top_left_y = max(geom.top() + 10, min(top_left_y, geom.bottom() - self.menu_size - 10))
        
        self.move(top_left_x, top_left_y)
        self.show()
        self.raise_()
        self._anim.start()

    def close_menu(self):
        if self.isVisible():
            self.hide()
            self.has_drag = False
            self.hover_index = -1
            self.menu_closed.emit()

    def _hit_test(self, pos: QPointF) -> int:
        cx, cy = self.width() / 2, self.height() / 2
        dx = pos.x() - cx
        dy = pos.y() - cy
        dist = math.hypot(dx, dy)

        if dist <= self.center_hub_r + 3:
            return -2

        if self.wedge_inner_r - 4 <= dist <= self.wedge_outer_r + 15 and self.formats:
            angle_deg = math.degrees(math.atan2(dx, -dy)) % 360.0
            total = len(self.formats)
            slice_deg = 360.0 / total
            
            aligned_deg = (angle_deg + slice_deg / 2) % 360.0
            idx = int(aligned_deg // slice_deg)
            return idx % total

        return -1

    @staticmethod
    def _extract_paths(mime_data) -> List[str]:
        if not mime_data.hasUrls():
            return []
        return [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile() and url.toLocalFile()]

    def dragEnterEvent(self, event):
        paths = self._extract_paths(event.mimeData())
        if not paths:
            event.ignore()
            return

        self.has_drag = True
        if paths != self.file_paths:
            self.file_paths = paths
            self.formats = get_available_formats(paths)
            self._update_radii()

        event.setDropAction(Qt.CopyAction)
        event.accept()
        self.update()

    def dragMoveEvent(self, event):
        pos = event.position()
        new_hover = self._hit_test(pos)
        if new_hover != self.hover_index:
            self.hover_index = new_hover
            self.update()
        event.setDropAction(Qt.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self.hover_index = -1
        self.update()

    def dropEvent(self, event):
        pos = event.position()
        idx = self._hit_test(pos)
        
        if 0 <= idx < len(self.formats) and self.file_paths:
            chosen_format = self.formats[idx]
            paths_to_convert = list(self.file_paths)
            
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.close_menu()
            self.file_dropped.emit(paths_to_convert, chosen_format)
        else:
            event.ignore()
            self.close_menu()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_menu()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        idx = self._hit_test(event.position())
        if idx != self.hover_index:
            self.hover_index = idx
            self.update()

    def mousePressEvent(self, event):
        idx = self._hit_test(event.position())
        if event.button() == Qt.LeftButton and 0 <= idx < len(self.formats):
            if self.file_paths:
                chosen_format = self.formats[idx]
                paths_to_convert = list(self.file_paths)
                self.close_menu()
                self.file_dropped.emit(paths_to_convert, chosen_format)
            else:
                self.close_menu()
        else:
            self.close_menu()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        cx, cy = self.width() / 2, self.height() / 2

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self.scale_factor, self.scale_factor)
        painter.translate(-cx, -cy)

        # 1. Sombra suave exterior
        shadow_rect = QRectF(cx - self.radius + 6, cy - self.radius + 6, (self.radius - 6) * 2, (self.radius - 6) * 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawEllipse(shadow_rect)

        # 2. Anillo exterior fino
        outer_ring_path = QPainterPath()
        outer_ring_path.addEllipse(QPointF(cx, cy), self.outer_ring_outer_r, self.outer_ring_outer_r)
        outer_ring_inner = QPainterPath()
        outer_ring_inner.addEllipse(QPointF(cx, cy), self.outer_ring_inner_r, self.outer_ring_inner_r)
        outer_ring_shape = outer_ring_path.subtracted(outer_ring_inner)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(60, 60, 65, 230))
        painter.drawPath(outer_ring_shape)

        # 3. Gajos (Wedges)
        n = len(self.formats)
        slice_deg = 360.0 / n if n > 0 else 360.0
        gap_deg = 2.0 if n >= 10 else 2.4

        # Tamaño de tipografía adaptado al número de gajos
        font_size = 8.5 if n >= 10 else (10.0 if n >= 8 else 11.0)
        format_font = QFont("Segoe UI", int(font_size), QFont.Bold)
        format_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)
        painter.setFont(format_font)

        COLOR_WEDGE_NORMAL = QColor(42, 42, 45, 245)
        COLOR_WEDGE_BORDER = QColor(65, 65, 72, 240)
        COLOR_TANGERINE_ORANGE = QColor(255, 92, 14, 255)
        COLOR_TANGERINE_BORDER = QColor(255, 138, 70, 255)
        COLOR_TEXT_NORMAL = QColor(235, 235, 240)
        COLOR_TEXT_ACTIVE = QColor(255, 255, 255)

        for i, raw_label in enumerate(self.formats):
            is_active = (self.hover_index == i)

            clock_mid_deg = i * slice_deg
            clock_start_deg = clock_mid_deg - (slice_deg - gap_deg) / 2
            clock_sweep_deg = slice_deg - gap_deg

            wedge_path = make_wedge_path(
                cx, cy,
                self.wedge_inner_r,
                self.wedge_outer_r + (4.0 if is_active else 0.0),
                clock_start_deg,
                clock_sweep_deg,
            )

            if is_active:
                painter.setBrush(QBrush(COLOR_TANGERINE_ORANGE))
                painter.setPen(QPen(COLOR_TANGERINE_BORDER, 1.5))
            else:
                painter.setBrush(QBrush(COLOR_WEDGE_NORMAL))
                painter.setPen(QPen(COLOR_WEDGE_BORDER, 1.0))

            painter.drawPath(wedge_path)

            # Formateo del texto para gajos compactos
            display_text = raw_label
            if "(low quality)" in display_text.lower():
                display_text = display_text.replace("(low quality)", "\n(LQ)").replace("(Low Quality)", "\n(LQ)")

            label_radius = (self.wedge_inner_r + self.wedge_outer_r) / 2
            label_pos = clock_to_cartesian(cx, cy, label_radius, clock_mid_deg)

            box_w = 70 if n >= 10 else 76
            box_h = 32 if "\n" in display_text else 26
            text_rect = QRectF(
                label_pos.x() - box_w / 2,
                label_pos.y() - box_h / 2,
                box_w,
                box_h,
            )
            painter.setPen(COLOR_TEXT_ACTIVE if is_active else COLOR_TEXT_NORMAL)
            painter.drawText(text_rect, Qt.AlignCenter, display_text)

        # 4. Centro circular (Hub)
        hub_rect = QRectF(
            cx - self.center_hub_r,
            cy - self.center_hub_r,
            self.center_hub_r * 2,
            self.center_hub_r * 2,
        )

        painter.setBrush(QBrush(QColor(22, 22, 25, 250)))
        painter.setPen(QPen(QColor(65, 65, 72, 220), 1.5))
        painter.drawEllipse(hub_rect)

        count = len(self.file_paths) if self.file_paths else 1
        count_str = f"{count} file" if count == 1 else f"{count} files"

        title_font = QFont("Segoe UI", 12, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor(255, 255, 255))
        title_rect = QRectF(cx - self.center_hub_r, cy - 18, self.center_hub_r * 2, 20)
        painter.drawText(title_rect, Qt.AlignCenter, count_str)

        subtitle_font = QFont("Segoe UI", 8, QFont.Bold)
        subtitle_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
        painter.setFont(subtitle_font)
        painter.setPen(QColor(165, 165, 175))
        subtitle_rect = QRectF(cx - self.center_hub_r, cy + 4, self.center_hub_r * 2, 16)
        painter.drawText(subtitle_rect, Qt.AlignCenter, "CONVERT")

        painter.restore()
