"""
Menú radial flotante de ultra alta fidelidad para Lime Radial Windows.
Implementa:
- Gajos / pétalos orgánicos con esquinas redondeadas (fillets Bezier G2) que eliminan puntas afiladas.
- Auténtico Glassmorphism con bordes especulares y sombreado suave de profundidad (idéntico a Image 3).
- Tipografía moderna Plus Jakarta Sans.
- Iconos vectoriales minimalistas en cada herramienta.
- Cápsula central flotante que cambia dinámicamente al formato o acción seleccionada (p.ej. 'Convert to BMP', 'Redact Photo', '1.2 MB').
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


def make_rounded_petal(
    cx: float,
    cy: float,
    r_in: float,
    r_out: float,
    clock_mid: float,
    clock_span: float,
    corner_r: float,
) -> QPainterPath:
    """
    Construye un pétalo anular suave con todas sus esquinas redondeadas
    utilizando curvas Bezier continuas para un aspecto orgánico moderno.
    """
    half_span = clock_span / 2.0
    th1 = clock_mid - half_span
    th2 = clock_mid + half_span
    
    dr = r_out - r_in
    r_c = min(corner_r, dr / 2.4)
    
    r_out_c = max(1.0, r_out - r_c)
    d_th_out = math.degrees(math.asin(min(0.99, r_c / r_out_c)))
    
    r_in_c = r_in + r_c
    d_th_in = math.degrees(math.asin(min(0.99, r_c / r_in_c)))
    
    max_d_th = half_span * 0.88
    if d_th_out > max_d_th:
        d_th_out = max_d_th
    if d_th_in > max_d_th:
        d_th_in = max_d_th
        
    def pt(r: float, deg: float) -> QPointF:
        rad = math.radians(deg)
        return QPointF(cx + r * math.sin(rad), cy - r * math.cos(rad))
        
    path = QPainterPath()
    
    # Ángulos para arcTo en Qt: 0 deg está a las 3 en punto, antihorario.
    # clock_deg: 0 deg a las 12 en punto, horario.
    # qt_deg = 90.0 - clock_deg
    qt_out_start = 90.0 - (th1 + d_th_out)
    qt_out_sweep = -(clock_span - 2 * d_th_out)
    
    outer_rect = QRectF(cx - r_out, cy - r_out, 2 * r_out, 2 * r_out)
    inner_rect = QRectF(cx - r_in, cy - r_in, 2 * r_in, 2 * r_in)
    
    p_out_start = pt(r_out, th1 + d_th_out)
    path.moveTo(p_out_start)
    
    # 1. Arco exterior
    path.arcTo(outer_rect, qt_out_start, qt_out_sweep)
    
    # 2. Esquina superior derecha (th2)
    p_v_tr = pt(r_out, th2)
    p_tr_rad = pt(r_out - r_c, th2)
    k = 0.552
    c1 = pt(r_out, th2 - d_th_out) + (p_v_tr - pt(r_out, th2 - d_th_out)) * k
    c2 = p_tr_rad + (p_v_tr - p_tr_rad) * k
    path.cubicTo(c1, c2, p_tr_rad)
    
    # 3. Línea radial hacia el interior
    p_br_rad = pt(r_in + r_c, th2)
    path.lineTo(p_br_rad)
    
    # 4. Esquina inferior derecha (th2)
    p_v_br = pt(r_in, th2)
    p_in_end = pt(r_in, th2 - d_th_in)
    c1 = p_br_rad + (p_v_br - p_br_rad) * k
    c2 = p_in_end + (p_v_br - p_in_end) * k
    path.cubicTo(c1, c2, p_in_end)
    
    # 5. Arco interior hacia el inicio
    qt_in_start = 90.0 - (th2 - d_th_in)
    qt_in_sweep = clock_span - 2 * d_th_in
    path.arcTo(inner_rect, qt_in_start, qt_in_sweep)
    
    # 6. Esquina inferior izquierda (th1)
    p_v_bl = pt(r_in, th1)
    p_bl_rad = pt(r_in + r_c, th1)
    c1 = pt(r_in, th1 + d_th_in) + (p_v_bl - pt(r_in, th1 + d_th_in)) * k
    c2 = p_bl_rad + (p_v_bl - p_bl_rad) * k
    path.cubicTo(c1, c2, p_bl_rad)
    
    # 7. Línea radial hacia el exterior
    p_tl_rad = pt(r_out - r_c, th1)
    path.lineTo(p_tl_rad)
    
    # 8. Esquina superior izquierda (th1)
    p_v_tl = pt(r_out, th1)
    c1 = p_tl_rad + (p_v_tl - p_tl_rad) * k
    c2 = p_out_start + (p_v_tl - p_out_start) * k
    path.cubicTo(c1, c2, p_out_start)
    
    path.closeSubpath()
    return path


class RadialMenu(QWidget):
    file_dropped = Signal(list, str)
    tool_triggered = Signal(str, list)
    menu_closed = Signal()

    def __init__(self, size: int = 390, parent: Optional[QWidget] = None):
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
        self.current_ring_name: str = "main"
        self.formats: List[str] = ["JPG", "PNG", "WebP", "HEIC", "TIFF", "AVIF", "BMP", "PDF"]
        self.hover_index: int = -1
        self.has_drag: bool = False
        self.scale_factor: float = 1.0

        # Temporizador para transición a sub-menú (Dwell time)
        self._dwell_timer = QTimer(self)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.setInterval(380)  # 380 ms de reposo abre el sub-menú
        self._dwell_timer.timeout.connect(self._on_dwell_timeout)
        self._dwell_target_index: int = -1

        # Animación de resorte al abrir
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setStartValue(0.72)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_scale_anim)

        self._update_radii()

    def _update_radii(self):
        n = len(self.formats)
        self.outer_ring_outer_r = self.radius - 8
        self.outer_ring_inner_r = self.outer_ring_outer_r - 4.0
        self.wedge_outer_r = self.outer_ring_inner_r - 6.0
        
        if n >= 10:
            self.wedge_inner_r = 72.0
            self.center_hub_r = 60.0
        elif n <= 5:
            self.wedge_inner_r = 60.0
            self.center_hub_r = 52.0
        else:
            self.wedge_inner_r = 66.0
            self.center_hub_r = 56.0

    def _on_scale_anim(self, value):
        self.scale_factor = float(value)
        self.update()

    def popup_at(self, pos: QPoint, paths: Optional[List[str]] = None):
        self.file_paths = paths or []
        self.current_ring_name = "main"

        if self.file_paths:
            self.formats = get_available_formats(self.file_paths)
            if len(self.file_paths) > 1 and "PDF" not in self.formats:
                self.formats.append("PDF")
        else:
            self.formats = ["JPG", "PNG", "WebP", "HEIC", "TIFF", "AVIF", "BMP", "PDF"]

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
        """Disparado cuando el cursor reposa en un formato con submenú."""
        if self.current_ring_name == "main" and 0 <= self._dwell_target_index < len(self.formats):
            item = self.formats[self._dwell_target_index].upper()
            if item == "PDF":
                self.switch_to_ring("pdf_tools")
            elif item in ("TIFF", "JPG", "PNG"):
                self.switch_to_ring("image_tools")

    def _hit_test(self, pos: QPointF) -> int:
        cx, cy = self.width() / 2, self.height() / 2
        dx = pos.x() - cx
        dy = pos.y() - cy
        dist = math.hypot(dx, dy)

        # Zona de la cápsula central
        if dist <= self.center_hub_r + 2:
            return -2

        # Zona de pétalos
        if self.wedge_inner_r - 8 <= dist <= self.wedge_outer_r + 14 and self.formats:
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

            # Temporizador de submenú para PDF y TIFF
            if self.current_ring_name == "main" and new_hover >= 0:
                item = self.formats[new_hover].upper()
                if item in ("PDF", "TIFF"):
                    self._dwell_target_index = new_hover
                    self._dwell_timer.start()

            # Volver al menú principal al mover el cursor al centro
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

    # ------------------ Renderizado Glassmorphic y Pétalos Redondeados ------------------
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

        # 1. Sombra suave circular exterior
        shadow_rect = QRectF(cx - self.radius + 8, cy - self.radius + 8, (self.radius - 8) * 2, (self.radius - 8) * 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 85))
        painter.drawEllipse(shadow_rect)

        # 2. Anillo exterior fino translúcido (Specular Rim Light)
        rim_path = QPainterPath()
        rim_path.addEllipse(QPointF(cx, cy), self.outer_ring_outer_r, self.outer_ring_outer_r)
        rim_inner = QPainterPath()
        rim_inner.addEllipse(QPointF(cx, cy), self.outer_ring_inner_r, self.outer_ring_inner_r)
        rim_shape = rim_path.subtracted(rim_inner)

        rim_grad = QLinearGradient(cx - self.radius, cy - self.radius, cx + self.radius, cy + self.radius)
        rim_grad.setColorAt(0.0, QColor(255, 255, 255, 140))
        rim_grad.setColorAt(0.5, QColor(255, 140, 40, 50))
        rim_grad.setColorAt(1.0, QColor(20, 25, 30, 40))
        painter.setBrush(QBrush(rim_grad))
        painter.drawPath(rim_shape)

        # 3. Pétalos redondeados (Rounded Petals con Glassmorphism)
        n = len(self.formats)
        slice_deg = 360.0 / n if n > 0 else 360.0
        gap_deg = 4.2 if n <= 6 else (3.6 if n <= 8 else 2.8)
        corner_r = 15.0 if n <= 6 else (13.5 if n <= 8 else 10.5)

        # Tipografía Plus Jakarta Sans
        font_size = 9.0 if n >= 10 else (10.0 if n >= 6 else 11.0)
        label_font = QFont(FONT_FAMILY, int(font_size), QFont.Bold)
        label_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.3)
        painter.setFont(label_font)

        # Paleta de color Glassmorphic moderna idéntica a Image 3
        COLOR_PETAL_BG = QColor(244, 246, 249, 238)          # Vidrio esmerilado claro de alta fidelidad
        COLOR_PETAL_BORDER = QColor(255, 255, 255, 220)       # Reflejo especular blanco
        COLOR_PETAL_TEXT = QColor(28, 33, 41)                 # Texto grafito nítido
        COLOR_ACTIVE_GRAD_TOP = QColor(255, 106, 0)           # Tangerine Orange vibrante
        COLOR_ACTIVE_GRAD_BOT = QColor(255, 62, 0)
        COLOR_ACTIVE_BORDER = QColor(255, 185, 110, 240)      # Borde iluminado
        COLOR_ACTIVE_TEXT = QColor(255, 255, 255)

        for i, raw_label in enumerate(self.formats):
            is_active = (self.hover_index == i)

            clock_mid_deg = i * slice_deg
            clock_span_deg = slice_deg - gap_deg

            # Expansión sutil táctil al pasar el cursor (+3px)
            r_out = self.wedge_outer_r + (3.0 if is_active else 0.0)
            r_in = self.wedge_inner_r

            petal_path = make_rounded_petal(
                cx, cy,
                r_in, r_out,
                clock_mid_deg,
                clock_span_deg,
                corner_r,
            )

            if is_active:
                active_grad = QLinearGradient(cx, cy - r_out, cx, cy + r_out)
                active_grad.setColorAt(0.0, COLOR_ACTIVE_GRAD_TOP)
                active_grad.setColorAt(1.0, COLOR_ACTIVE_GRAD_BOT)
                painter.setBrush(QBrush(active_grad))
                painter.setPen(QPen(COLOR_ACTIVE_BORDER, 1.8))
            else:
                painter.setBrush(QBrush(COLOR_PETAL_BG))
                painter.setPen(QPen(COLOR_PETAL_BORDER, 1.2))

            painter.drawPath(petal_path)

            # Posición del texto/icono en el pétalo
            label_radius = (r_in + r_out) / 2
            label_pos = clock_to_cartesian(cx, cy, label_radius, clock_mid_deg)

            has_icon = raw_label.upper() in (
                "COMPRESS", "CROP", "CREATE PDF", "COLLAGE", "METADATA", "EDIT", "ANNOTATE", "ADD BG", "REDACT"
            )

            if has_icon:
                icon_center = QPointF(label_pos.x(), label_pos.y() - 7)
                draw_minimal_icon(
                    painter,
                    raw_label,
                    icon_center,
                    size=16.0,
                    color=COLOR_ACTIVE_TEXT if is_active else COLOR_PETAL_TEXT,
                )
                text_rect = QRectF(label_pos.x() - 42, label_pos.y() + 3, 84, 16)
                painter.setPen(COLOR_ACTIVE_TEXT if is_active else COLOR_PETAL_TEXT)
                sub_font = QFont(FONT_FAMILY, 8, QFont.Bold)
                painter.setFont(sub_font)
                painter.drawText(text_rect, Qt.AlignCenter, raw_label)
                painter.setFont(label_font)
            else:
                display_text = raw_label
                box_w = 74 if n >= 10 else 82
                box_h = 28
                text_rect = QRectF(label_pos.x() - box_w / 2, label_pos.y() - box_h / 2, box_w, box_h)
                painter.setPen(COLOR_ACTIVE_TEXT if is_active else COLOR_PETAL_TEXT)
                painter.drawText(text_rect, Qt.AlignCenter, display_text)

        # 4. Cápsula Central Flotante (Floating Glass Pill)
        # Muestra dinámicamente la acción ('Convert to BMP', 'Redact Photo') o el peso/archivos
        pill_w, pill_h = 130.0, 36.0
        pill_rect = QRectF(cx - pill_w / 2, cy - pill_h / 2, pill_w, pill_h)

        # Sombra sutil de la cápsula
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 35))
        painter.drawRoundedRect(pill_rect.translated(0, 2), 18, 18)

        # Fondo cápsula con cristal esmerilado puro
        capsule_grad = QLinearGradient(pill_rect.topLeft(), pill_rect.bottomRight())
        capsule_grad.setColorAt(0.0, QColor(255, 255, 255, 245))
        capsule_grad.setColorAt(1.0, QColor(242, 245, 248, 245))

        painter.setBrush(QBrush(capsule_grad))
        painter.setPen(QPen(QColor(220, 226, 234, 220), 1.2))
        painter.drawRoundedRect(pill_rect, 18, 18)

        # Texto dentro de la cápsula central
        if 0 <= self.hover_index < len(self.formats):
            raw_active = self.formats[self.hover_index]
            active_clean = raw_active.replace("To ", "").strip()
            
            # Nombre de acción completo como en Tangerine Mac (Image 3)
            action_name_map = {
                "BMP": "Convert to BMP",
                "JPG": "Convert to JPG",
                "JPEG": "Convert to JPEG",
                "PNG": "Convert to PNG",
                "WEBP": "Convert to WebP",
                "HEIC": "Convert to HEIC",
                "TIFF": "Convert to TIFF",
                "AVIF": "Convert to AVIF",
                "PDF": "PDF Tools" if self.current_ring_name == "main" else "Convert to PDF",
                "REDACT": "Redact Photo",
                "CROP": "Crop Image",
                "EDIT": "Edit Image",
                "ANNOTATE": "Annotate",
                "ADD BG": "Add Background",
                "METADATA": "Metadata",
                "COMPRESS": "Compress File",
                "CREATE PDF": "Create PDF",
                "COLLAGE": "Photo Collage",
            }
            display_action = action_name_map.get(active_clean.upper(), f"To {active_clean}")

            capsule_font = QFont(FONT_FAMILY, 9, QFont.Bold)
            painter.setFont(capsule_font)
            painter.setPen(QColor(26, 32, 40))
            painter.drawText(pill_rect, Qt.AlignCenter, display_action)
        else:
            # Mostrar tamaño o cantidad de archivos
            size_str = self._calculate_file_size()
            capsule_font = QFont(FONT_FAMILY, 10, QFont.Bold)
            painter.setFont(capsule_font)
            painter.setPen(QColor(26, 32, 40))
            painter.drawText(pill_rect, Qt.AlignCenter, size_str)

        painter.restore()

    def _calculate_file_size(self) -> str:
        if not self.file_paths:
            return "1 file"
            
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
