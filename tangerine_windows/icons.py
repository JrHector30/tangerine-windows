"""
Sistema de iconos vectoriales minimalistas y fuentes para Tangerine Windows.
Dibuja iconos vectoriales con QPainterPath en alta resolución.
"""
from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QPainterPath, QPen, QColor

FONT_FAMILY = "Segoe UI"


def load_custom_fonts():
    """Carga Plus Jakarta Sans si está disponible en la carpeta fonts."""
    global FONT_FAMILY
    font_path = Path(__file__).parent / "fonts" / "PlusJakartaSans.ttf"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                FONT_FAMILY = families[0]
                return FONT_FAMILY
    return "Segoe UI"


def draw_minimal_icon(painter: QPainter, icon_name: str, center: QPointF, size: float = 18.0, color: QColor = QColor(255, 255, 255)):
    """Dibuja un icono vectorial minimalista con trazos nítidos."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    
    pen = QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    
    cx, cy = center.x(), center.y()
    hs = size / 2.0
    
    name = icon_name.upper().strip()
    
    if name == "COMPRESS":
        # Flechas convergiendo hacia el centro
        d = hs * 0.75
        # Flecha superior izquierda hacia centro
        p = QPainterPath()
        p.moveTo(cx - d, cy - d)
        p.lineTo(cx - 2, cy - 2)
        p.moveTo(cx - d + 3, cy - 2)
        p.lineTo(cx - 2, cy - 2)
        p.lineTo(cx - 2, cy - d + 3)
        # Flecha inferior derecha hacia centro
        p.moveTo(cx + d, cy + d)
        p.lineTo(cx + 2, cy + 2)
        p.moveTo(cx + d - 3, cy + 2)
        p.lineTo(cx + 2, cy + 2)
        p.lineTo(cx + 2, cy + d - 3)
        painter.drawPath(p)

    elif name == "CROP":
        # Marcadores de recorte entrelazados
        d = hs * 0.75
        p = QPainterPath()
        p.moveTo(cx - d, cy - d + 4)
        p.lineTo(cx + d - 4, cy - d + 4)
        p.lineTo(cx + d - 4, cy + d)
        
        p.moveTo(cx + d, cy + d - 4)
        p.lineTo(cx - d + 4, cy + d - 4)
        p.lineTo(cx - d + 4, cy - d)
        painter.drawPath(p)

    elif name in ("CREATE PDF", "PDF"):
        # Documento con esquina doblada o signo más
        w, h = hs * 0.7, hs * 0.9
        p = QPainterPath()
        p.addRoundedRect(QRectF(cx - w, cy - h, w * 2, h * 2), 2, 2)
        # Signo más en el centro
        p.moveTo(cx - 3, cy)
        p.lineTo(cx + 3, cy)
        p.moveTo(cx, cy - 3)
        p.lineTo(cx, cy + 3)
        painter.drawPath(p)

    elif name == "COLLAGE":
        # Cuadrícula 2x2 o split
        d = hs * 0.8
        p = QPainterPath()
        p.addRoundedRect(QRectF(cx - d, cy - d, d * 0.9, d * 1.9), 1.5, 1.5)
        p.addRoundedRect(QRectF(cx + 1, cy - d, d * 0.9, d * 0.9), 1.5, 1.5)
        p.addRoundedRect(QRectF(cx + 1, cy + 1, d * 0.9, d * 0.9), 1.5, 1.5)
        painter.drawPath(p)

    elif name == "METADATA":
        # Etiqueta / Tag con orificio
        d = hs * 0.8
        p = QPainterPath()
        p.moveTo(cx - d + 3, cy - d)
        p.lineTo(cx + d - 4, cy - d)
        p.lineTo(cx + d, cy)
        p.lineTo(cx, cy + d)
        p.lineTo(cx - d, cy + 2)
        p.closeSubpath()
        painter.drawPath(p)
        painter.drawEllipse(QPointF(cx - d + 4, cy - d + 4), 1.2, 1.2)

    elif name == "EDIT":
        # Sliders de ajuste horizontales
        d = hs * 0.75
        p = QPainterPath()
        # Línea 1
        p.moveTo(cx - d, cy - 4)
        p.lineTo(cx + d, cy - 4)
        # Línea 2
        p.moveTo(cx - d, cy + 4)
        p.lineTo(cx + d, cy + 4)
        painter.drawPath(p)
        # Perillas
        painter.drawEllipse(QPointF(cx - 2, cy - 4), 2, 2)
        painter.drawEllipse(QPointF(cx + 3, cy + 4), 2, 2)

    elif name == "ANNOTATE":
        # Círculo con lápiz o pluma
        p = QPainterPath()
        p.addEllipse(QPointF(cx, cy), hs * 0.7, hs * 0.7)
        p.moveTo(cx - 3, cy + 3)
        p.lineTo(cx + 4, cy - 4)
        painter.drawPath(p)

    elif name == "ADD BG":
        # Cuadro de imagen paisaje
        d = hs * 0.8
        p = QPainterPath()
        p.addRoundedRect(QRectF(cx - d, cy - d + 2, d * 2, d * 1.6), 2, 2)
        # Montañas
        p.moveTo(cx - d + 2, cy + d - 2)
        p.lineTo(cx - 2, cy - 1)
        p.lineTo(cx + 2, cy + 2)
        p.lineTo(cx + d - 2, cy - 2)
        painter.drawPath(p)

    elif name == "REDACT":
        # Ojo con barra diagonal
        d = hs * 0.8
        p = QPainterPath()
        p.moveTo(cx - d, cy)
        p.quadTo(cx, cy - d * 0.7, cx + d, cy)
        p.quadTo(cx, cy + d * 0.7, cx - d, cy)
        # Barra diagonal
        p.moveTo(cx - d + 2, cy + d - 2)
        p.lineTo(cx + d - 2, cy - d + 2)
        painter.drawPath(p)

    painter.restore()
