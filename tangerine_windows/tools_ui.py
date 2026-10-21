"""
Ventanas de ajustes y herramientas con estética Glassmorphic para Tangerine Windows.
Incluye ventana de recorte interactiva (Crop), compresión inteligente y collage.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageOps
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import FONT_FAMILY


class CropView(QWidget):
    """Área interactiva para previsualizar y ajustar el área de recorte."""

    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.pil_img = Image.open(image_path)
        self.pil_img = ImageOps.exif_transpose(self.pil_img)
        self.orig_w, self.orig_h = self.pil_img.size

        # Convertir a QImage
        self.qimg = QImage(str(image_path))
        self.aspect_ratio: Optional[float] = None  # None = Free
        self.crop_rect_norm = QRectF(0.08, 0.08, 0.84, 0.84)  # Coordenadas normalizadas 0..1

        self.setMinimumSize(380, 320)

    def set_aspect_ratio(self, ratio: Optional[float]):
        self.aspect_ratio = ratio
        if ratio is not None:
            # Reajustar crop_rect manteniendo aspecto
            cx, cy = self.crop_rect_norm.center().x(), self.crop_rect_norm.center().y()
            img_aspect = self.orig_w / self.orig_h
            norm_aspect = ratio / img_aspect

            if norm_aspect > 1.0:
                nw = 0.84
                nh = nw / norm_aspect
            else:
                nh = 0.84
                nw = nh * norm_aspect

            self.crop_rect_norm = QRectF(cx - nw / 2, cy - nh / 2, nw, nh)
        self.update()

    def reset_crop(self):
        self.aspect_ratio = None
        self.crop_rect_norm = QRectF(0.05, 0.05, 0.90, 0.90)
        self.update()

    def get_cropped_image(self) -> Image.Image:
        norm = self.crop_rect_norm
        left = int(max(0, norm.left() * self.orig_w))
        top = int(max(0, norm.top() * self.orig_h))
        right = int(min(self.orig_w, norm.right() * self.orig_w))
        bottom = int(min(self.orig_h, norm.bottom() * self.orig_h))
        if right <= left:
            right = left + 10
        if bottom <= top:
            bottom = top + 10
        return self.pil_img.crop((left, top, right, bottom))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()

        # Calcular escala de imagen dentro del widget
        scale = min(w / self.orig_w, h / self.orig_h) * 0.92
        disp_w = self.orig_w * scale
        disp_h = self.orig_h * scale
        disp_x = (w - disp_w) / 2
        disp_y = (h - disp_h) / 2
        img_rect = QRectF(disp_x, disp_y, disp_w, disp_h)

        # Dibujar imagen escalada
        painter.drawImage(img_rect, self.qimg)

        # Coordenadas absolutas del recorte
        crop_x = disp_x + self.crop_rect_norm.left() * disp_w
        crop_y = disp_y + self.crop_rect_norm.top() * disp_h
        crop_w = self.crop_rect_norm.width() * disp_w
        crop_h = self.crop_rect_norm.height() * disp_h
        crop_rect = QRectF(crop_x, crop_y, crop_w, crop_h)

        # Máscara semitransparente oscura fuera del recorte
        outer_path = QPainterPath()
        outer_path.addRect(img_rect)
        inner_path = QPainterPath()
        inner_path.addRect(crop_rect)
        mask = outer_path.subtracted(inner_path)

        painter.setBrush(QColor(0, 0, 0, 140))
        painter.setPen(Qt.NoPen)
        painter.drawPath(mask)

        # Borde del recorte en Naranja Tangerine
        painter.setPen(QPen(QColor(255, 102, 0), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(crop_rect)

        # Esquinas decorativas de recorte (estilo Tangerine)
        corner_len = 14
        pen_corner = QPen(QColor(255, 120, 30), 3.5, Qt.SolidLine, Qt.SquareCap)
        painter.setPen(pen_corner)

        # Sup Izq
        painter.drawLine(crop_x, crop_y, crop_x + corner_len, crop_y)
        painter.drawLine(crop_x, crop_y, crop_x, crop_y + corner_len)
        # Sup Der
        painter.drawLine(crop_x + crop_w, crop_y, crop_x + crop_w - corner_len, crop_y)
        painter.drawLine(crop_x + crop_w, crop_y, crop_x + crop_w, crop_y + corner_len)
        # Inf Izq
        painter.drawLine(crop_x, crop_y + crop_h, crop_x + corner_len, crop_y + crop_h)
        painter.drawLine(crop_x, crop_y + crop_h, crop_x, crop_y + crop_h - corner_len)
        # Inf Der
        painter.drawLine(crop_x + crop_w, crop_y + crop_h, crop_x + crop_w - corner_len, crop_y + crop_h)
        painter.drawLine(crop_x + crop_w, crop_y + crop_h, crop_x + crop_w, crop_y + crop_h - corner_len)


class CropImageDialog(QDialog):
    """Ventana moderna con Glassmorphism para Recortar Imagen."""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)

        self.setWindowTitle("Crop Image")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(520, 600)

        # Layout Principal
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)

        # Tarjeta Glassmorphic
        self.card = QWidget(self)
        self.card.setObjectName("glassCard")
        self.card.setStyleSheet(f"""
            QWidget#glassCard {{
                background-color: rgba(30, 27, 24, 0.95);
                border: 1px solid rgba(255, 170, 100, 0.22);
                border-radius: 20px;
            }}
            QLabel {{
                color: #FFFFFF;
                font-family: "{FONT_FAMILY}";
            }}
            QPushButton {{
                font-family: "{FONT_FAMILY}";
                font-weight: bold;
                border-radius: 8px;
                padding: 6px 14px;
                background-color: rgba(60, 56, 52, 0.8);
                color: #E0E0E0;
                border: 1px solid rgba(100, 95, 90, 0.5);
            }}
            QPushButton:hover {{
                background-color: rgba(80, 75, 70, 0.9);
                color: #FFFFFF;
            }}
            QPushButton:checked {{
                background-color: #FF6600;
                color: #FFFFFF;
                border: 1px solid #FFA040;
            }}
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 16, 20, 18)
        card_layout.setSpacing(12)

        # Barra superior con Título y Cerrar
        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                color: #888888;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        close_btn.clicked.connect(self.reject)
        
        title_label = QLabel("Crop Image")
        title_label.setFont(QFont(FONT_FAMILY, 13, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)

        top_bar.addWidget(close_btn)
        top_bar.addWidget(title_label, 1)
        top_bar.addSpacing(28)  # Balancear el botón cerrar

        card_layout.addLayout(top_bar)

        # Vista de Recorte
        self.crop_view = CropView(self.image_path, self)
        card_layout.addWidget(self.crop_view, 1)

        # Selector de Aspect Ratio
        ratio_bar = QHBoxLayout()
        ratio_label = QLabel("Aspect ratio")
        ratio_label.setFont(QFont(FONT_FAMILY, 9, QFont.Bold))
        ratio_label.setStyleSheet("color: #AAAAAA;")
        ratio_bar.addWidget(ratio_label)
        ratio_bar.addSpacing(8)

        self.btn_group = QButtonGroup(self)
        ratios = [
            ("Free", None),
            ("1:1", 1.0),
            ("16:9", 16.0 / 9.0),
            ("9:16", 9.0 / 16.0),
            ("4:3", 4.0 / 3.0),
            ("3:4", 3.0 / 4.0),
        ]
        for name, val in ratios:
            btn = QPushButton(name)
            btn.setCheckable(True)
            if name == "Free":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, v=val: self.crop_view.set_aspect_ratio(v))
            self.btn_group.addButton(btn)
            ratio_bar.addWidget(btn)

        ratio_bar.addStretch()
        card_layout.addLayout(ratio_bar)

        # Botones inferiores: Reset y Apply
        bottom_bar = QHBoxLayout()
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.crop_view.reset_crop)
        reset_btn.setFixedWidth(90)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(110)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF6600;
                color: #FFFFFF;
                border: 1px solid #FFA040;
                font-size: 11pt;
                padding: 8px;
                border-radius: 9px;
            }
            QPushButton:hover {
                background-color: #FF7711;
            }
        """)
        apply_btn.clicked.connect(self._on_apply)

        bottom_bar.addWidget(reset_btn)
        bottom_bar.addStretch()
        bottom_bar.addWidget(apply_btn)

        card_layout.addLayout(bottom_bar)
        root_layout.addWidget(self.card)

    def _on_apply(self):
        cropped = self.crop_view.get_cropped_image()
        parent = self.image_path.parent
        stem = self.image_path.stem
        ext = self.image_path.suffix.lower()
        
        out_path = parent / f"{stem} Cropped{ext}"
        counter = 1
        while out_path.exists():
            out_path = parent / f"{stem} Cropped ({counter}){ext}"
            counter += 1
            
        cropped.save(out_path)
        self.accept()


# ------------------ Herramientas adicionales ------------------
def execute_compress(paths: List[str]):
    """Comprime imágenes reduciendo tamaño 50-70% manteniendo nitidez."""
    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        try:
            im = Image.open(path)
            im = ImageOps.exif_transpose(im)
            out_path = path.parent / f"{path.stem} Compressed{path.suffix}"
            if im.mode in ("RGBA", "P"):
                im.save(out_path, optimize=True, quality=80)
            else:
                im.save(out_path, "JPEG", optimize=True, progressive=True, quality=78)
        except Exception as e:
            print("Error comprimiendo:", e)


def execute_create_pdf(paths: List[str]):
    """Combina múltiples imágenes en un único archivo PDF."""
    images = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            im = Image.open(path)
            im = ImageOps.exif_transpose(im)
            if im.mode != "RGB":
                im = im.convert("RGB")
            images.append(im)
            
    if images:
        first = images[0]
        out_pdf = Path(paths[0]).parent / "Combined_Document.pdf"
        first.save(out_pdf, save_all=True, append_images=images[1:], resolution=150.0)


def execute_collage(paths: List[str]):
    """Crea un collage 2x2 o fila con las imágenes seleccionadas."""
    images = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            im = Image.open(path)
            im = ImageOps.exif_transpose(im)
            im.thumbnail((800, 800))
            images.append(im)
            
    if not images:
        return
        
    n = len(images)
    cols = 2 if n >= 3 else n
    rows = (n + cols - 1) // cols
    cell_w = max(im.width for im in images)
    cell_h = max(im.height for im in images)
    
    collage = Image.new("RGB", (cols * cell_w, rows * cell_h), (255, 255, 255))
    for idx, im in enumerate(images):
        r = idx // cols
        c = idx % cols
        x = c * cell_w + (cell_w - im.width) // 2
        y = r * cell_h + (cell_h - im.height) // 2
        collage.paste(im, (x, y))
        
    out_file = Path(paths[0]).parent / "Collage.jpg"
    collage.save(out_file, "JPEG", quality=90)


def execute_metadata_strip(paths: List[str]):
    """Elimina metadatos EXIF / GPS privados de las imágenes."""
    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        try:
            im = Image.open(path)
            data = list(im.getdata())
            clean_im = Image.new(im.mode, im.size)
            clean_im.putdata(data)
            out_file = path.parent / f"{path.stem} NoMeta{path.suffix}"
            clean_im.save(out_file)
        except Exception as e:
            print("Error limpiando metadata:", e)
