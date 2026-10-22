"""
Herramientas avanzadas interactivas con Glassmorphism auténtico para Lime Radial Windows.
- CropImageDialog: Con W y H calculados en PX en tiempo real, recuadro libre, selector de aspect ratio y botón de cierre circular.
- EditImageDialog: Ajustes de brillo, contraste, saturación, rotación y volteo.
- AddBgDialog: Fondos elegantes con degradados.
- RedactImageDialog: Censura interactiva de datos.
- AnnotateImageDialog: Dibujo y notas sobre la imagen.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QIntValidator,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .icons import FONT_FAMILY

GLASS_DIALOG_STYLESHEET = f"""
    QWidget#glassCard {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(22, 26, 34, 0.90),
            stop:1 rgba(14, 17, 24, 0.94));
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 24px;
    }}
    QLabel {{
        color: #F8FAFC;
        font-family: "{FONT_FAMILY}";
    }}
    QPushButton {{
        font-family: "{FONT_FAMILY}";
        font-weight: 600;
        border-radius: 9px;
        padding: 6px 14px;
        background-color: rgba(255, 255, 255, 0.08);
        color: #E2E8F0;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }}
    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.18);
        color: #FFFFFF;
    }}
    QPushButton:checked {{
        background-color: #FF5500;
        color: #FFFFFF;
        border: 1px solid #FFA040;
    }}
    QLineEdit {{
        background-color: rgba(10, 14, 20, 0.75);
        color: #FFFFFF;
        font-family: "{FONT_FAMILY}";
        font-weight: bold;
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 8px;
        padding: 4px 8px;
        font-size: 11pt;
    }}
    QLineEdit:focus {{
        border: 1px solid #FF7700;
        background-color: rgba(10, 14, 20, 0.92);
    }}
    QSlider::groove:horizontal {{
        height: 6px;
        background: rgba(255, 255, 255, 0.14);
        border-radius: 3px;
    }}
    QSlider::sub-page:horizontal {{
        background: #FF5500;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: #FFFFFF;
        border: 2px solid #FF5500;
        width: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    QSlider::handle:horizontal:hover {{
        background: #FFF0E6;
        border: 2px solid #FF7722;
    }}
"""

CLOSE_BUTTON_STYLESHEET = """
    QPushButton {
        background-color: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 15px;
        font-size: 13px;
        font-weight: bold;
        color: #FFFFFF;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 0.28);
        color: #FFFFFF;
    }
"""

PRIMARY_BUTTON_STYLESHEET = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #FF6A00, stop:1 #FF4200);
        color: #FFFFFF;
        font-weight: bold;
        border: 1px solid rgba(255, 255, 255, 0.30);
        border-radius: 10px;
        padding: 8px 20px;
        font-size: 11pt;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #FF7B1A, stop:1 #FF5500);
    }
"""


# -------------------------------------------------------------
# 1. CROP VIEW & DIALOG (W y H en PX y Recorte Libre)
# -------------------------------------------------------------
class CropView(QWidget):
    crop_size_changed = Signal(int, int)

    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.pil_img = Image.open(image_path)
        self.pil_img = ImageOps.exif_transpose(self.pil_img)
        self.orig_w, self.orig_h = self.pil_img.size

        self.qimg = QImage(str(image_path))
        self.aspect_ratio: Optional[float] = None
        self.crop_norm = QRectF(0.08, 0.08, 0.84, 0.84)

        self._active_handle: Optional[str] = None
        self._drag_start_pos = QPointF()
        self._drag_start_norm = QRectF()

        self.setMouseTracking(True)
        self.setMinimumSize(420, 340)

    def set_aspect_ratio(self, ratio: Optional[float]):
        self.aspect_ratio = ratio
        if ratio is not None:
            cx, cy = self.crop_norm.center().x(), self.crop_norm.center().y()
            img_aspect = self.orig_w / self.orig_h
            norm_aspect = ratio / img_aspect

            if norm_aspect > 1.0:
                nw = min(0.85, self.crop_norm.width())
                nh = nw / norm_aspect
            else:
                nh = min(0.85, self.crop_norm.height())
                nw = nh * norm_aspect

            self.crop_norm = QRectF(cx - nw / 2, cy - nh / 2, nw, nh)
            self._clamp_norm()
        self._notify_size()
        self.update()

    def set_pixel_size(self, w_px: int, h_px: int):
        """Permite fijar dimensiones exactas en píxeles desde las cajas de texto W y H."""
        w_px = max(20, min(w_px, self.orig_w))
        h_px = max(20, min(h_px, self.orig_h))
        nw = w_px / self.orig_w
        nh = h_px / self.orig_h
        cx, cy = self.crop_norm.center().x(), self.crop_norm.center().y()
        self.crop_norm = QRectF(cx - nw / 2, cy - nh / 2, nw, nh)
        self._clamp_norm()
        self._notify_size()
        self.update()

    def reset_crop(self):
        self.aspect_ratio = None
        self.crop_norm = QRectF(0.05, 0.05, 0.90, 0.90)
        self._notify_size()
        self.update()

    def _get_display_geometry(self) -> Tuple[QRectF, QRectF]:
        w, h = self.width(), self.height()
        scale = min(w / self.orig_w, h / self.orig_h) * 0.92
        disp_w = self.orig_w * scale
        disp_h = self.orig_h * scale
        disp_x = (w - disp_w) / 2
        disp_y = (h - disp_h) / 2
        img_rect = QRectF(disp_x, disp_y, disp_w, disp_h)

        crop_rect = QRectF(
            disp_x + self.crop_norm.left() * disp_w,
            disp_y + self.crop_norm.top() * disp_h,
            self.crop_norm.width() * disp_w,
            self.crop_norm.height() * disp_h,
        )
        return img_rect, crop_rect

    def _notify_size(self):
        w_px = int(round(self.crop_norm.width() * self.orig_w))
        h_px = int(round(self.crop_norm.height() * self.orig_h))
        self.crop_size_changed.emit(w_px, h_px)

    def _hit_test_handles(self, pos: QPointF, crop_rect: QRectF) -> Optional[str]:
        threshold = 14.0
        x, y = pos.x(), pos.y()
        cl, ct, cr, cb = crop_rect.left(), crop_rect.top(), crop_rect.right(), crop_rect.bottom()

        if math.hypot(x - cl, y - ct) <= threshold:
            return "TL"
        if math.hypot(x - cr, y - ct) <= threshold:
            return "TR"
        if math.hypot(x - cl, y - cb) <= threshold:
            return "BL"
        if math.hypot(x - cr, y - cb) <= threshold:
            return "BR"

        if abs(y - ct) <= threshold and cl <= x <= cr:
            return "T"
        if abs(y - cb) <= threshold and cl <= x <= cr:
            return "B"
        if abs(x - cl) <= threshold and ct <= y <= cb:
            return "L"
        if abs(x - cr) <= threshold and ct <= y <= cb:
            return "R"

        if crop_rect.contains(pos):
            return "MOVE"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            img_rect, crop_rect = self._get_display_geometry()
            pos = event.position()
            handle = self._hit_test_handles(pos, crop_rect)
            if handle:
                self._active_handle = handle
                self._drag_start_pos = pos
                self._drag_start_norm = QRectF(self.crop_norm)

    def mouseMoveEvent(self, event):
        img_rect, crop_rect = self._get_display_geometry()
        pos = event.position()

        if self._active_handle and event.buttons() & Qt.LeftButton:
            dx = (pos.x() - self._drag_start_pos.x()) / img_rect.width()
            dy = (pos.y() - self._drag_start_pos.y()) / img_rect.height()

            orig = self._drag_start_norm
            nl, nt, nr, nb = orig.left(), orig.top(), orig.right(), orig.bottom()

            h = self._active_handle
            if h == "MOVE":
                nl += dx
                nr += dx
                nt += dy
                nb += dy
            else:
                if "L" in h:
                    nl = min(nl + dx, nr - 0.05)
                if "R" in h:
                    nr = max(nr + dx, nl + 0.05)
                if "T" in h:
                    nt = min(nt + dy, nb - 0.05)
                if "B" in h:
                    nb = max(nb + dy, nt + 0.05)

                if self.aspect_ratio is not None:
                    img_aspect = self.orig_w / self.orig_h
                    desired_norm_aspect = self.aspect_ratio / img_aspect
                    curr_w = nr - nl
                    curr_h = nb - nt
                    if "T" in h or "B" in h:
                        nr = nl + curr_h * desired_norm_aspect
                    else:
                        nb = nt + curr_w / desired_norm_aspect

            self.crop_norm = QRectF(nl, nt, nr - nl, nb - nt)
            self._clamp_norm()
            self._notify_size()
            self.update()
        else:
            handle = self._hit_test_handles(pos, crop_rect)
            if handle in ("TL", "BR"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ("TR", "BL"):
                self.setCursor(Qt.SizeBDiagCursor)
            elif handle in ("T", "B"):
                self.setCursor(Qt.SizeVerCursor)
            elif handle in ("L", "R"):
                self.setCursor(Qt.SizeHorCursor)
            elif handle == "MOVE":
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._active_handle = None

    def _clamp_norm(self):
        nl = max(0.0, min(self.crop_norm.left(), 0.90))
        nt = max(0.0, min(self.crop_norm.top(), 0.90))
        nw = max(0.05, min(self.crop_norm.width(), 1.0 - nl))
        nh = max(0.05, min(self.crop_norm.height(), 1.0 - nt))
        self.crop_norm = QRectF(nl, nt, nw, nh)

    def get_cropped_image(self) -> Image.Image:
        left = int(max(0, self.crop_norm.left() * self.orig_w))
        top = int(max(0, self.crop_norm.top() * self.orig_h))
        right = int(min(self.orig_w, self.crop_norm.right() * self.orig_w))
        bottom = int(min(self.orig_h, self.crop_norm.bottom() * self.orig_h))
        if right <= left:
            right = left + 10
        if bottom <= top:
            bottom = top + 10
        return self.pil_img.crop((left, top, right, bottom))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        img_rect, crop_rect = self._get_display_geometry()

        # Imagen base
        painter.drawImage(img_rect, self.qimg)

        # Máscara de oscurecimiento exterior
        outer_p = QPainterPath()
        outer_p.addRect(img_rect)
        inner_p = QPainterPath()
        inner_p.addRect(crop_rect)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.setPen(Qt.NoPen)
        painter.drawPath(outer_p.subtracted(inner_p))

        # Marco del recorte en Naranja Ámbar
        painter.setPen(QPen(QColor(255, 102, 0), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(crop_rect)

        # Esquinas gruesas de guía en naranja vibrante
        corner_w = 16
        pen_c = QPen(QColor(255, 95, 15), 4, Qt.SolidLine, Qt.SquareCap)
        painter.setPen(pen_c)

        cl, ct, cr, cb = crop_rect.left(), crop_rect.top(), crop_rect.right(), crop_rect.bottom()
        # TL
        painter.drawLine(cl, ct, cl + corner_w, ct)
        painter.drawLine(cl, ct, cl, ct + corner_w)
        # TR
        painter.drawLine(cr, ct, cr - corner_w, ct)
        painter.drawLine(cr, ct, cr, ct + corner_w)
        # BL
        painter.drawLine(cl, cb, cl + corner_w, cb)
        painter.drawLine(cl, cb, cl, cb - corner_w)
        # BR
        painter.drawLine(cr, cb, cr - corner_w, cb)
        painter.drawLine(cr, cb, cr, cb - corner_w)

        # Píldoras centrales en bordes
        mid_x, mid_y = crop_rect.center().x(), crop_rect.center().y()
        painter.setBrush(QColor(255, 95, 15))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(mid_x - 8, ct - 2.5, 16, 5), 2.5, 2.5)
        painter.drawRoundedRect(QRectF(mid_x - 8, cb - 2.5, 16, 5), 2.5, 2.5)
        painter.drawRoundedRect(QRectF(cl - 2.5, mid_y - 8, 5, 16), 2.5, 2.5)
        painter.drawRoundedRect(QRectF(cr - 2.5, mid_y - 8, 5, 16), 2.5, 2.5)


class CropImageDialog(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.setWindowTitle("Crop Image")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(540, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        # Tarjeta Glassmorphic cálida idéntica al video/captura
        card = QWidget(self)
        card.setObjectName("glassCard")
        card.setStyleSheet(GLASS_DIALOG_STYLESHEET)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 16, 22, 20)
        card_layout.setSpacing(12)

        # Barra superior con botón circular de cierre '✕'
        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(CLOSE_BUTTON_STYLESHEET)
        close_btn.clicked.connect(self.reject)

        title = QLabel("Crop Image")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)

        top_bar.addWidget(close_btn)
        top_bar.addWidget(title, 1)
        top_bar.addSpacing(30)
        card_layout.addLayout(top_bar)

        # Vista de corte interactiva
        self.crop_view = CropView(self.image_path, self)
        card_layout.addWidget(self.crop_view, 1)

        # Fila 1: Aspect Ratio
        ratio_bar = QHBoxLayout()
        lbl_ratio = QLabel("Aspect ratio")
        lbl_ratio.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        ratio_bar.addWidget(lbl_ratio)
        ratio_bar.addSpacing(8)

        self.btn_group = QButtonGroup(self)
        for name, val in [
            ("Free", None),
            ("1:1", 1.0),
            ("16:9", 16.0 / 9.0),
            ("9:16", 9.0 / 16.0),
            ("4:3", 4.0 / 3.0),
            ("3:4", 3.0 / 4.0),
        ]:
            b = QPushButton(name)
            b.setCheckable(True)
            if name == "Free":
                b.setChecked(True)
            b.clicked.connect(lambda checked, v=val: self.crop_view.set_aspect_ratio(v))
            self.btn_group.addButton(b)
            ratio_bar.addWidget(b)
        ratio_bar.addStretch()
        card_layout.addLayout(ratio_bar)

        # Fila 2: W y H calculados en PX en tiempo real
        dim_bar = QHBoxLayout()
        w_lbl = QLabel("W")
        w_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.w_input = QLineEdit()
        self.w_input.setFixedWidth(80)
        self.w_input.setValidator(QIntValidator(10, 20000, self))

        h_lbl = QLabel("H")
        h_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.h_input = QLineEdit()
        self.h_input.setFixedWidth(80)
        self.h_input.setValidator(QIntValidator(10, 20000, self))

        px_lbl = QLabel("px")
        px_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))

        dim_bar.addWidget(w_lbl)
        dim_bar.addWidget(self.w_input)
        dim_bar.addSpacing(12)
        dim_bar.addWidget(h_lbl)
        dim_bar.addWidget(self.h_input)
        dim_bar.addWidget(px_lbl)
        dim_bar.addStretch()
        card_layout.addLayout(dim_bar)

        # Conectar tamaño en tiempo real
        self.crop_view.crop_size_changed.connect(self._on_crop_size_changed)
        self.w_input.returnPressed.connect(self._on_manual_dimension_entered)
        self.h_input.returnPressed.connect(self._on_manual_dimension_entered)

        # Fila 3: Botones inferiores (Reset y Apply)
        bot_bar = QHBoxLayout()
        reset_btn = QPushButton("Reset")
        reset_btn.setFixedWidth(95)
        reset_btn.clicked.connect(self.crop_view.reset_crop)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(115)
        apply_btn.setStyleSheet(PRIMARY_BUTTON_STYLESHEET)
        apply_btn.clicked.connect(self._on_apply)

        bot_bar.addWidget(reset_btn)
        bot_bar.addStretch()
        bot_bar.addWidget(apply_btn)
        card_layout.addLayout(bot_bar)

        root.addWidget(card)
        self.crop_view._notify_size()

    def _on_crop_size_changed(self, w: int, h: int):
        self.w_input.setText(str(w))
        self.h_input.setText(str(h))

    def _on_manual_dimension_entered(self):
        try:
            w = int(self.w_input.text())
            h = int(self.h_input.text())
            self.crop_view.set_pixel_size(w, h)
        except Exception:
            pass

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


# -------------------------------------------------------------
# 2. EDIT IMAGE DIALOG
# -------------------------------------------------------------
class EditImageDialog(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.pil_base = Image.open(self.image_path)
        self.pil_base = ImageOps.exif_transpose(self.pil_base)
        self.rotation_deg = 0

        self.setWindowTitle("Edit Image")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(540, 660)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        card = QWidget(self)
        card.setObjectName("glassCard")
        card.setStyleSheet(GLASS_DIALOG_STYLESHEET)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 16, 22, 20)
        card_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(CLOSE_BUTTON_STYLESHEET)
        close_btn.clicked.connect(self.reject)

        title = QLabel("Edit Image")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(close_btn)
        top_bar.addWidget(title, 1)
        top_bar.addSpacing(30)
        card_layout.addLayout(top_bar)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(280)
        card_layout.addWidget(self.preview_label, 1)

        self.slider_bright = self._make_slider_row("Brightness", card_layout)
        self.slider_contrast = self._make_slider_row("Contrast", card_layout)
        self.slider_saturation = self._make_slider_row("Saturation", card_layout)

        rot_bar = QHBoxLayout()
        btn_rot = QPushButton("Rotar 90° ⟳")
        btn_rot.clicked.connect(self._on_rotate)
        btn_flip_h = QPushButton("Volteo ⇄")
        btn_flip_h.clicked.connect(self._on_flip)
        rot_bar.addWidget(btn_rot)
        rot_bar.addWidget(btn_flip_h)
        rot_bar.addStretch()
        card_layout.addLayout(rot_bar)

        bot_bar = QHBoxLayout()
        reset_btn = QPushButton("Reset")
        reset_btn.setFixedWidth(95)
        reset_btn.clicked.connect(self._on_reset)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(115)
        apply_btn.setStyleSheet(PRIMARY_BUTTON_STYLESHEET)
        apply_btn.clicked.connect(self._on_apply)

        bot_bar.addWidget(reset_btn)
        bot_bar.addStretch()
        bot_bar.addWidget(apply_btn)
        card_layout.addLayout(bot_bar)

        root.addWidget(card)
        self._update_preview()

    def _make_slider_row(self, name: str, parent_layout) -> QSlider:
        row = QHBoxLayout()
        lbl = QLabel(name)
        lbl.setFixedWidth(90)
        lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-50, 50)
        slider.setValue(0)
        slider.valueChanged.connect(self._update_preview)
        row.addWidget(lbl)
        row.addWidget(slider)
        parent_layout.addLayout(row)
        return slider

    def _on_rotate(self):
        self.rotation_deg = (self.rotation_deg - 90) % 360
        self._update_preview()

    def _on_flip(self):
        self.pil_base = self.pil_base.transpose(Image.FLIP_LEFT_RIGHT)
        self._update_preview()

    def _on_reset(self):
        self.slider_bright.setValue(0)
        self.slider_contrast.setValue(0)
        self.slider_saturation.setValue(0)
        self.rotation_deg = 0
        self._update_preview()

    def _get_processed_image(self) -> Image.Image:
        im = self.pil_base
        if self.rotation_deg != 0:
            im = im.rotate(self.rotation_deg, expand=True)

        b_val = 1.0 + (self.slider_bright.value() / 50.0)
        im = ImageEnhance.Brightness(im).enhance(b_val)

        c_val = 1.0 + (self.slider_contrast.value() / 50.0)
        im = ImageEnhance.Contrast(im).enhance(c_val)

        s_val = 1.0 + (self.slider_saturation.value() / 50.0)
        im = ImageEnhance.Color(im).enhance(s_val)
        return im

    def _update_preview(self):
        im = self._get_processed_image()
        thumb = im.copy()
        thumb.thumbnail((440, 280))
        if thumb.mode != "RGBA":
            thumb = thumb.convert("RGBA")
        data = thumb.tobytes("raw", "RGBA")
        qim = QImage(data, thumb.width, thumb.height, QImage.Format_RGBA8888)
        self.preview_label.setPixmap(QPixmap.fromImage(qim))

    def _on_apply(self):
        im = self._get_processed_image()
        parent = self.image_path.parent
        stem = self.image_path.stem
        ext = self.image_path.suffix.lower()

        out_path = parent / f"{stem} Edited{ext}"
        counter = 1
        while out_path.exists():
            out_path = parent / f"{stem} Edited ({counter}){ext}"
            counter += 1
        im.save(out_path)
        self.accept()


# -------------------------------------------------------------
# 3. ADD BG DIALOG
# -------------------------------------------------------------
class AddBgDialog(QDialog):
    GRADIENTS = [
        ("Golden Sunset", (255, 102, 0), (255, 179, 71)),
        ("Midnight Purple", (43, 24, 78), (111, 44, 145)),
        ("Ocean Blue", (15, 32, 67), (40, 116, 166)),
        ("Clean Slate", (30, 32, 36), (60, 64, 72)),
    ]

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.pil_img = Image.open(self.image_path)
        self.pil_img = ImageOps.exif_transpose(self.pil_img)
        self.selected_grad_idx = 0

        self.setWindowTitle("Add Background")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(520, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        card = QWidget(self)
        card.setObjectName("glassCard")
        card.setStyleSheet(GLASS_DIALOG_STYLESHEET)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 16, 22, 20)
        card_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(CLOSE_BUTTON_STYLESHEET)
        close_btn.clicked.connect(self.reject)

        title = QLabel("Add Background (Marco Profesional)")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(close_btn)
        top_bar.addWidget(title, 1)
        top_bar.addSpacing(30)
        card_layout.addLayout(top_bar)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(280)
        card_layout.addWidget(self.preview_label, 1)

        grad_bar = QHBoxLayout()
        for idx, (name, _, _) in enumerate(self.GRADIENTS):
            btn = QPushButton(name.split()[0])
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda ch, i=idx: self._select_grad(i))
            grad_bar.addWidget(btn)
        card_layout.addLayout(grad_bar)

        bot_bar = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(115)
        apply_btn.setStyleSheet(PRIMARY_BUTTON_STYLESHEET)
        apply_btn.clicked.connect(self._on_apply)
        bot_bar.addStretch()
        bot_bar.addWidget(apply_btn)
        card_layout.addLayout(bot_bar)

        root.addWidget(card)
        self._update_preview()

    def _select_grad(self, idx):
        self.selected_grad_idx = idx
        self._update_preview()

    def _render_composed_image(self) -> Image.Image:
        _, c1, _ = self.GRADIENTS[self.selected_grad_idx]
        pad = 80
        w = self.pil_img.width + pad * 2
        h = self.pil_img.height + pad * 2
        bg = Image.new("RGBA", (w, h), c1)
        inner = self.pil_img.convert("RGBA")
        bg.paste(inner, (pad, pad), inner)
        return bg

    def _update_preview(self):
        composed = self._render_composed_image()
        composed.thumbnail((440, 280))
        data = composed.tobytes("raw", "RGBA")
        qim = QImage(data, composed.width, composed.height, QImage.Format_RGBA8888)
        self.preview_label.setPixmap(QPixmap.fromImage(qim))

    def _on_apply(self):
        composed = self._render_composed_image()
        parent = self.image_path.parent
        stem = self.image_path.stem
        out_path = parent / f"{stem} With_BG.png"
        counter = 1
        while out_path.exists():
            out_path = parent / f"{stem} With_BG ({counter}).png"
            counter += 1
        composed.save(out_path)
        self.accept()


# -------------------------------------------------------------
# 4. REDACT IMAGE DIALOG
# -------------------------------------------------------------
class RedactView(QWidget):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.pil_img = Image.open(image_path)
        self.pil_img = ImageOps.exif_transpose(self.pil_img)
        self.qimg = QImage(str(image_path))
        self.rects_norm: List[QRectF] = []
        self._drag_start: Optional[QPointF] = None
        self._curr_pos: Optional[QPointF] = None
        self.setMinimumSize(420, 320)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position()
            self._curr_pos = event.position()

    def mouseMoveEvent(self, event):
        if self._drag_start:
            self._curr_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_start and self._curr_pos:
            w, h = self.width(), self.height()
            scale = min(w / self.pil_img.width, h / self.pil_img.height) * 0.92
            disp_w, disp_h = self.pil_img.width * scale, self.pil_img.height * scale
            disp_x, disp_y = (w - disp_w) / 2, (h - disp_h) / 2

            r = QRectF(self._drag_start, self._curr_pos).normalized()
            nl = (r.left() - disp_x) / disp_w
            nt = (r.top() - disp_y) / disp_h
            nw = r.width() / disp_w
            nh = r.height() / disp_h
            if nw > 0.01 and nh > 0.01:
                self.rects_norm.append(QRectF(nl, nt, nw, nh))
            self._drag_start = None
            self._curr_pos = None
            self.update()

    def clear_redactions(self):
        self.rects_norm.clear()
        self.update()

    def get_redacted_image(self) -> Image.Image:
        im = self.pil_img.copy()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(im)
        for r in self.rects_norm:
            x0 = int(r.left() * im.width)
            y0 = int(r.top() * im.height)
            x1 = int(r.right() * im.width)
            y1 = int(r.bottom() * im.height)
            draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))
        return im

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        scale = min(w / self.pil_img.width, h / self.pil_img.height) * 0.92
        disp_w, disp_h = self.pil_img.width * scale, self.pil_img.height * scale
        disp_x, disp_y = (w - disp_w) / 2, (h - disp_h) / 2
        img_rect = QRectF(disp_x, disp_y, disp_w, disp_h)

        painter.drawImage(img_rect, self.qimg)

        painter.setBrush(QColor(0, 0, 0, 240))
        painter.setPen(QPen(QColor(255, 80, 80), 1.5))
        for r in self.rects_norm:
            rx = disp_x + r.left() * disp_w
            ry = disp_y + r.top() * disp_h
            rw = r.width() * disp_w
            rh = r.height() * disp_h
            painter.drawRect(QRectF(rx, ry, rw, rh))

        if self._drag_start and self._curr_pos:
            curr_rect = QRectF(self._drag_start, self._curr_pos).normalized()
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(QPen(QColor(255, 90, 0), 2, Qt.DashLine))
            painter.drawRect(curr_rect)


class RedactImageDialog(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.setWindowTitle("Redact Information")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(540, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        card = QWidget(self)
        card.setObjectName("glassCard")
        card.setStyleSheet(GLASS_DIALOG_STYLESHEET)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 16, 22, 20)
        card_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(CLOSE_BUTTON_STYLESHEET)
        close_btn.clicked.connect(self.reject)

        title = QLabel("Redact (Censurar Datos)")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(close_btn)
        top_bar.addWidget(title, 1)
        top_bar.addSpacing(30)
        card_layout.addLayout(top_bar)

        self.view = RedactView(self.image_path, self)
        card_layout.addWidget(self.view, 1)

        bot_bar = QHBoxLayout()
        clear_btn = QPushButton("Limpiar")
        clear_btn.clicked.connect(self.view.clear_redactions)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(PRIMARY_BUTTON_STYLESHEET)
        apply_btn.clicked.connect(self._on_apply)

        bot_bar.addWidget(clear_btn)
        bot_bar.addStretch()
        bot_bar.addWidget(apply_btn)
        card_layout.addLayout(bot_bar)

        root.addWidget(card)

    def _on_apply(self):
        redacted = self.view.get_redacted_image()
        parent = self.image_path.parent
        stem = self.image_path.stem
        out_path = parent / f"{stem} Redacted.png"
        counter = 1
        while out_path.exists():
            out_path = parent / f"{stem} Redacted ({counter}).png"
            counter += 1
        redacted.save(out_path)
        self.accept()


# -------------------------------------------------------------
# 5. ANNOTATE IMAGE DIALOG
# -------------------------------------------------------------
class AnnotateView(QWidget):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.pil_img = Image.open(image_path)
        self.pil_img = ImageOps.exif_transpose(self.pil_img)
        self.qimg = QImage(str(image_path))
        self.lines: List[List[QPointF]] = []
        self._curr_line: List[QPointF] = []
        self.setMinimumSize(420, 320)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._curr_line = [event.position()]

    def mouseMoveEvent(self, event):
        if self._curr_line:
            self._curr_line.append(event.position())
            self.update()

    def mouseReleaseEvent(self, event):
        if self._curr_line:
            self.lines.append(self._curr_line)
            self._curr_line = []
            self.update()

    def clear(self):
        self.lines.clear()
        self.update()

    def get_annotated_image(self) -> Image.Image:
        w, h = self.width(), self.height()
        scale = min(w / self.pil_img.width, h / self.pil_img.height) * 0.92
        disp_w, disp_h = self.pil_img.width * scale, self.pil_img.height * scale
        disp_x, disp_y = (w - disp_w) / 2, (h - disp_h) / 2

        im = self.pil_img.copy()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(im)

        for line in self.lines:
            coords = []
            for pt in line:
                ix = (pt.x() - disp_x) / scale
                iy = (pt.y() - disp_y) / scale
                coords.append((ix, iy))
            if len(coords) >= 2:
                draw.line(coords, fill=(255, 90, 0), width=4)
        return im

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        scale = min(w / self.pil_img.width, h / self.pil_img.height) * 0.92
        disp_w, disp_h = self.pil_img.width * scale, self.pil_img.height * scale
        disp_x, disp_y = (w - disp_w) / 2, (h - disp_h) / 2
        img_rect = QRectF(disp_x, disp_y, disp_w, disp_h)

        painter.drawImage(img_rect, self.qimg)

        pen = QPen(QColor(255, 90, 0), 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        for line in self.lines + ([self._curr_line] if self._curr_line else []):
            for i in range(len(line) - 1):
                painter.drawLine(line[i], line[i + 1])


class AnnotateImageDialog(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.setWindowTitle("Annotate Image")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(540, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        card = QWidget(self)
        card.setObjectName("glassCard")
        card.setStyleSheet(GLASS_DIALOG_STYLESHEET)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 16, 22, 20)
        card_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(CLOSE_BUTTON_STYLESHEET)
        close_btn.clicked.connect(self.reject)

        title = QLabel("Annotate (Dibuja sobre la imagen)")
        title.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        top_bar.addWidget(close_btn)
        top_bar.addWidget(title, 1)
        top_bar.addSpacing(30)
        card_layout.addLayout(top_bar)

        self.view = AnnotateView(self.image_path, self)
        card_layout.addWidget(self.view, 1)

        bot_bar = QHBoxLayout()
        clear_btn = QPushButton("Borrar")
        clear_btn.clicked.connect(self.view.clear)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(PRIMARY_BUTTON_STYLESHEET)
        apply_btn.clicked.connect(self._on_apply)

        bot_bar.addWidget(clear_btn)
        bot_bar.addStretch()
        bot_bar.addWidget(apply_btn)
        card_layout.addLayout(bot_bar)

        root.addWidget(card)

    def _on_apply(self):
        annotated = self.view.get_annotated_image()
        parent = self.image_path.parent
        stem = self.image_path.stem
        out_path = parent / f"{stem} Annotated.png"
        counter = 1
        while out_path.exists():
            out_path = parent / f"{stem} Annotated ({counter}).png"
            counter += 1
        annotated.save(out_path)
        self.accept()


# -------------------------------------------------------------
# 6. HERRAMIENTAS RÁPIDAS
# -------------------------------------------------------------
def execute_compress(paths: List[str]):
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
            print("[LimeRadial Compress Error]:", e)


def execute_create_pdf(paths: List[str]):
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
        counter = 1
        while out_pdf.exists():
            out_pdf = Path(paths[0]).parent / f"Combined_Document ({counter}).pdf"
            counter += 1
        first.save(out_pdf, save_all=True, append_images=images[1:], resolution=150.0)


def execute_collage(paths: List[str]):
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
    counter = 1
    while out_file.exists():
        out_file = Path(paths[0]).parent / f"Collage ({counter}).jpg"
        counter += 1
    collage.save(out_file, "JPEG", quality=90)


def execute_metadata_strip(paths: List[str]):
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
            counter = 1
            while out_file.exists():
                out_file = path.parent / f"{path.stem} NoMeta ({counter}){path.suffix}"
                counter += 1
            clean_im.save(out_file)
        except Exception as e:
            print("[LimeRadial Metadata Error]:", e)
