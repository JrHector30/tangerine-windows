"""
Menú radial flotante de ultra alta fidelidad para Tangerine Windows.
Implementa:
- Auténtico Glassmorphism con bordes especulares y brillo ámbar/vidrio esmerilado.
- Tipografía moderna Plus Jakarta Sans.
- Iconos vectoriales minimalistas en cada herramienta.
- Cápsula central flotante que cambia dinámicamente al formato/herramienta seleccionada (p.ej. 'JPG', '1.2 MB', 'CROP').
- Sub-menús radiales automáticos al mantener el cursor sobre 'PDF', 'TIFF' o herramientas avanzadas.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    QTimer,
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
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from .convert import get_available_formats
from .icons import FONT_FAMILY, draw_minimal_icon, load_custom_fonts

# Sub-anillos de herramientas según contexto
PDF_TOOLS_ITEMS = ["COMPRESS", "CROP", "CREATE PDF", "COLLAGE"]
IMAGE_TOOLS_ITEMS = ["COMPRESS", "METADATA", "EDIT", "ANNOTATE", "ADD BG", "CROP", "REDACT"]


def clock_to_cartesian(cx: float, cy: float, radius: float, clock_deg: float) -> QPointF:
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
    tool_triggered = Signal(str, list)
    menu_closed = Signal()

    def __init__(self, size: int = 380, parent: Optional[QWidget] = None):
        super().__init__(parent)
        load_custom_fonts()

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

        # Estado del Menú
        self.file_paths: List[str] = []
        self.current_ring_name: str = "main"  # 'main', 'pdf_tools', 'image_tools'
        self.formats: List[str] = ["JPEG", "WebP", "HEIC", "TIFF", "BMP", "GIF", "PDF", "PNG"]
        self.hover_index: int = -1
        self.has_drag: bool = False
        self.scale_factor: float = 1.0

        # Temporizador para transición a sub-menú (Dwell time)
        self._dwell_timer = QTimer(self)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.setInterval(420)  # 420 ms quieto abre el sub-menú
        self._dwell_timer.timeout.connect(self._on_dwell_timeout)
        self._dwell_target_index: int = -1

        # Animación de resorte
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setStartValue(0.68)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_scale_anim)

        self._update_radii()

    def _update_radii(self):
        n = len(self.formats)
        self.outer_ring_outer_r = self.radius - 8
        self.outer_ring_inner_r = self.outer_ring_outer_r - 4.5
        self.wedge_outer_r = self.outer_ring_inner_r - 5.5
        
        if n >= 10:
            self.wedge_inner_r = 68.0
            self.center_hub_r = 58.0
        else:
            self.wedge_inner_r = 62.0
            self.center_hub_r = 54.0

    def _on_scale_anim(self, value):
        self.scale_factor = float(value)
        self.update()

    def popup_at(self, pos: QPoint, paths: Optional[List[str]] = None):
        self.file_paths = paths or []
        self.current_ring_name = "main"

        if self.file_paths:
            self.formats = get_available_formats(self.file_paths)
            # Si hay múltiples imágenes, agregar PDF para permitir abrir submenú collage/create pdf
            if len(self.file_paths) > 1 and "PDF" not in self.formats:
                self.formats.append("PDF")
        else:
            self.formats = ["JPEG", "WebP", "HEIC", "TIFF", "BMP", "GIF", "PDF", "PNG"]

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
            self._dwell_timer.stop()
            self.hide()
            self.has_drag = False
            self.hover_index = -1
            self.current_ring_name = "main"
            self.menu_closed.emit()

    def switch_to_ring(self, ring_name: str):
        """Transición fluida a otro anillo radial (p.ej. herramientas de PDF o Imagen)."""
        self.current_ring_name = ring_name
        if ring_name == "pdf_tools":
            self.formats = list(PDF_TOOLS_ITEMS)
        elif ring_name == "image_tools":
            self.formats = list(IMAGE_TOOLS_ITEMS)
        else:
            self.formats = get_available_formats(self.file_paths)

        self._update_radii()
        self.hover_index = -1
        self._anim.start()
        self.update()

    def _on_dwell_timeout(self):
        """Disparado cuando el cursor reposa quieto en un formato con submenú."""
        if self.current_ring_name == "main" and 0 <= self._dwell_target_index < len(self.formats):
            item = self.formats[self._dwell_target_index].upper()
            if item == "PDF":
                self.switch_to_ring("pdf_tools")
            elif item in ("TIFF", "JPEG", "PNG"):
                self.switch_to_ring("image_tools")

    def _hit_test(self, pos: QPointF) -> int:
        cx, cy = self.width() / 2, self.height() / 2
        dx = pos.x() - cx
        dy = pos.y() - cy
        dist = math.hypot(dx, dy)

        # Zona de la cápsula central
        if dist <= self.center_hub_r + 4:
            return -2

        # Zona de gajos
        if self.wedge_inner_r - 6 <= dist <= self.wedge_outer_r + 16 and self.formats:
            angle_deg = math.degrees(math.atan2(dx, -dy)) % 360.0
            total = len(self.formats)
            slice_deg = 360.0 / total
            
            aligned_deg = (angle_deg + slice_deg / 2) % 360.0
            idx = int(aligned_deg // slice_deg)
            return idx % total

        return -1

    def _handle_hover_change(self, new_hover: int):
        if new_hover != self.hover_index:
            self.hover_index = new_hover
            self._dwell_timer.stop()

            # Si se posa sobre PDF o TIFF en el anillo principal, iniciar temporizador de submenú
            if self.current_ring_name == "main" and new_hover >= 0:
                item = self.formats[new_hover].upper()
                if item in ("PDF", "TIFF"):
                    self._dwell_target_index = new_hover
                    self._dwell_timer.start()

            # Si vuelve al centro estando en un submenú, retornar al menú principal
            if new_hover == -2 and self.current_ring_name != "main":
                self.switch_to_ring("main")

            self.update()

    # ------------------ Drag & Drop ------------------
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
        self._handle_hover_change(self._hit_test(pos))
        event.setDropAction(Qt.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._dwell_timer.stop()
        self.hover_index = -1
        self.update()

    def dropEvent(self, event):
        pos = event.position()
        idx = self._hit_test(pos)
        
        if 0 <= idx < len(self.formats) and self.file_paths:
            chosen_item = self.formats[idx]
            paths_to_process = list(self.file_paths)
            
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.close_menu()
            
            item_key = chosen_item.upper().replace("TO ", "").strip()
            KNOWN_TOOLS = {
                "CROP", "COMPRESS", "COLLAGE", "CREATE PDF", "METADATA",
                "ADD BG", "ADDBG", "EDIT", "ANNOTATE", "REDACT"
            }
            if self.current_ring_name in ("pdf_tools", "image_tools") or item_key in KNOWN_TOOLS:
                self.tool_triggered.emit(chosen_item, paths_to_process)
            else:
                self.file_dropped.emit(paths_to_process, chosen_item)
        else:
            event.ignore()
            self.close_menu()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.current_ring_name != "main":
                self.switch_to_ring("main")
            else:
                self.close_menu()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        self._handle_hover_change(self._hit_test(event.position()))

    def mousePressEvent(self, event):
        idx = self._hit_test(event.position())
        if event.button() == Qt.LeftButton and 0 <= idx < len(self.formats):
            chosen_item = self.formats[idx]
            if chosen_item.upper() in ("PDF", "TIFF") and self.current_ring_name == "main":
                self.switch_to_ring("pdf_tools" if chosen_item.upper() == "PDF" else "image_tools")
                return

            if self.file_paths:
                paths = list(self.file_paths)
                self.close_menu()
                item_key = chosen_item.upper().replace("TO ", "").strip()
                KNOWN_TOOLS = {
                    "CROP", "COMPRESS", "COLLAGE", "CREATE PDF", "METADATA",
                    "ADD BG", "ADDBG", "EDIT", "ANNOTATE", "REDACT"
                }
                if self.current_ring_name != "main" or item_key in KNOWN_TOOLS:
                    self.tool_triggered.emit(chosen_item, paths)
                else:
                    self.file_dropped.emit(paths, chosen_item)
            else:
                self.close_menu()
        else:
            self.close_menu()

    # ------------------ Renderizado Glassmorphic y Especular ------------------
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

        # 1. Sombra suave de profundidad
        shadow_rect = QRectF(cx - self.radius + 6, cy - self.radius + 6, (self.radius - 6) * 2, (self.radius - 6) * 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.drawEllipse(shadow_rect)

        # 2. Resplandor especular exterior (Glass Specular Rim Light)
        rim_grad = QLinearGradient(cx - self.radius, cy - self.radius, cx + self.radius, cy + self.radius)
        rim_grad.setColorAt(0.0, QColor(255, 220, 180, 110))   # Brillo ámbar cálido en borde superior
        rim_grad.setColorAt(0.4, QColor(255, 140, 60, 50))
        rim_grad.setColorAt(1.0, QColor(40, 35, 30, 80))

        outer_ring_path = QPainterPath()
        outer_ring_path.addEllipse(QPointF(cx, cy), self.outer_ring_outer_r, self.outer_ring_outer_r)
        outer_ring_inner = QPainterPath()
        outer_ring_inner.addEllipse(QPointF(cx, cy), self.outer_ring_inner_r, self.outer_ring_inner_r)
        outer_ring_shape = outer_ring_path.subtracted(outer_ring_inner)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(rim_grad))
        painter.drawPath(outer_ring_shape)

        # 3. Gajos de Vidrio Esmerilado (Glass Wedges)
        n = len(self.formats)
        slice_deg = 360.0 / n if n > 0 else 360.0
        gap_deg = 2.2 if n >= 10 else 2.6

        # Tipografía Plus Jakarta Sans
        font_size = 8.5 if n >= 10 else (9.5 if n >= 6 else 10.5)
        label_font = QFont(FONT_FAMILY, int(font_size), QFont.Bold)
        label_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)
        painter.setFont(label_font)

        # Colores Glassmorphic
        COLOR_WEDGE_GLASS = QColor(36, 32, 28, 225)           # Vidrio oscuro con tinte ámbar
        COLOR_WEDGE_BORDER = QColor(90, 80, 70, 160)          # Borde suave translúcido
        COLOR_TANGERINE_ORANGE = QColor(255, 96, 14, 255)     # Naranja Tangerine vibrante
        COLOR_TANGERINE_BORDER = QColor(255, 165, 80, 255)    # Borde iluminado
        COLOR_TEXT_NORMAL = QColor(240, 238, 235)
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
                active_grad = QLinearGradient(cx, cy - self.wedge_outer_r, cx, cy + self.wedge_outer_r)
                active_grad.setColorAt(0.0, QColor(255, 115, 25))
                active_grad.setColorAt(1.0, COLOR_TANGERINE_ORANGE)
                painter.setBrush(QBrush(active_grad))
                painter.setPen(QPen(COLOR_TANGERINE_BORDER, 1.6))
            else:
                painter.setBrush(QBrush(COLOR_WEDGE_GLASS))
                painter.setPen(QPen(COLOR_WEDGE_BORDER, 1.0))

            painter.drawPath(wedge_path)

            # Posición del contenido en el gajo
            label_radius = (self.wedge_inner_r + self.wedge_outer_r) / 2
            label_pos = clock_to_cartesian(cx, cy, label_radius, clock_mid_deg)

            has_icon = raw_label.upper() in (
                "COMPRESS", "CROP", "CREATE PDF", "COLLAGE", "METADATA", "EDIT", "ANNOTATE", "ADD BG", "REDACT"
            )

            if has_icon:
                # Dibujar icono minimalista encima y etiqueta debajo
                icon_center = QPointF(label_pos.x(), label_pos.y() - 7)
                draw_minimal_icon(
                    painter,
                    raw_label,
                    icon_center,
                    size=16.0,
                    color=COLOR_TEXT_ACTIVE if is_active else COLOR_TEXT_NORMAL,
                )
                text_rect = QRectF(label_pos.x() - 40, label_pos.y() + 3, 80, 16)
                painter.setPen(COLOR_TEXT_ACTIVE if is_active else COLOR_TEXT_NORMAL)
                sub_font = QFont(FONT_FAMILY, 8, QFont.Bold)
                painter.setFont(sub_font)
                painter.drawText(text_rect, Qt.AlignCenter, raw_label)
                painter.setFont(label_font)
            else:
                # Dibujar texto de formato
                display_text = raw_label
                if "(low quality)" in display_text.lower():
                    display_text = display_text.replace("(low quality)", "\n(LQ)").replace("(Low Quality)", "\n(LQ)")

                box_w = 72 if n >= 10 else 78
                box_h = 32 if "\n" in display_text else 26
                text_rect = QRectF(label_pos.x() - box_w / 2, label_pos.y() - box_h / 2, box_w, box_h)
                painter.setPen(COLOR_TEXT_ACTIVE if is_active else COLOR_TEXT_NORMAL)
                painter.drawText(text_rect, Qt.AlignCenter, display_text)

        # 4. Cápsula Central Flotante (Glass Floating Pill)
        # La cápsula muestra el formato seleccionado si hay hover, o el peso/archivos si está libre
        pill_w, pill_h = 96.0, 36.0
        pill_rect = QRectF(cx - pill_w / 2, cy - pill_h / 2, pill_w, pill_h)

        # Fondo cápsula con gradiente de vidrio esmerilado
        capsule_grad = QLinearGradient(pill_rect.topLeft(), pill_rect.bottomRight())
        capsule_grad.setColorAt(0.0, QColor(48, 42, 36, 240))
        capsule_grad.setColorAt(1.0, QColor(25, 22, 20, 245))

        painter.setBrush(QBrush(capsule_grad))
        painter.setPen(QPen(QColor(110, 95, 80, 200), 1.4))
        painter.drawRoundedRect(pill_rect, 18, 18)

        # Contenido de la cápsula
        if 0 <= self.hover_index < len(self.formats):
            # Mostrar el formato / herramienta seleccionado al pasar el ratón (como en el video!)
            active_name = self.formats[self.hover_index].replace("To ", "")
            if "(low quality)" in active_name.lower():
                active_name = active_name.split()[0] + " (LQ)"

            capsule_font = QFont(FONT_FAMILY, 11, QFont.Bold)
            painter.setFont(capsule_font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pill_rect, Qt.AlignCenter, active_name)
        else:
            # Mostrar tamaño o cantidad de archivos (p.ej. '1.2 MB' o '4 files')
            size_str = self._calculate_file_size()
            capsule_font = QFont(FONT_FAMILY, 10, QFont.Bold)
            painter.setFont(capsule_font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pill_rect, Qt.AlignCenter, size_str)

        painter.restore()

    def _calculate_file_size(self) -> str:
        if not self.file_paths:
            return "4 files"
            
        total_bytes = 0
        valid_count = 0
        for p in self.file_paths:
            try:
                if os.path.exists(p):
                    total_bytes += os.path.getsize(p)
                    valid_count += 1
            except Exception:
                pass

        if total_bytes > 0:
            if total_bytes < 1024 * 1024:
                return f"{total_bytes / 1024:.0f} KB"
            return f"{total_bytes / (1024 * 1024):.1f} MB"
            
        count = len(self.file_paths)
        return f"{count} file" if count == 1 else f"{count} files"
