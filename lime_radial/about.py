"""
Diálogo "About / Acerca de" para Lime Radial Windows.
Incluye información de versión, licencia, créditos a herramientas de terceros
y descargo de responsabilidad (Disclaimer) formal.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .icons import FONT_FAMILY


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Lime Radial")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(520, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)

        card = QWidget(self)
        card.setObjectName("aboutCard")
        card.setStyleSheet(f"""
            QWidget#aboutCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(36, 32, 28, 0.96),
                    stop:1 rgba(22, 20, 18, 0.98));
                border: 1.5px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
            }}
            QLabel {{
                color: #FFFFFF;
                font-family: "{FONT_FAMILY}";
            }}
            QTextBrowser {{
                background: transparent;
                border: none;
                color: #CCCCCC;
                font-family: "{FONT_FAMILY}";
                font-size: 10pt;
                line-height: 1.5;
            }}
            QScrollBar:vertical {{
                width: 0px;
            }}
            QPushButton {{
                font-family: "{FONT_FAMILY}";
                font-weight: bold;
                border-radius: 9px;
                padding: 7px 18px;
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.25);
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)

        # Barra superior con botón circular de cierre
        top_bar = QHBoxLayout()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 15px;
                font-size: 13px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.22);
            }
        """)
        close_btn.clicked.connect(self.accept)

        title = QLabel("Acerca de / About")
        title.setFont(QFont(FONT_FAMILY, 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)

        top_bar.addWidget(close_btn)
        top_bar.addWidget(title, 1)
        top_bar.addSpacing(30)
        card_layout.addLayout(top_bar)

        # Encabezado con Icono y Nombre
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignCenter)
        header_layout.setSpacing(4)

        logo_label = QLabel("🍋")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("font-size: 42px; margin-bottom: 4px;")
        header_layout.addWidget(logo_label)

        app_name = QLabel("Lime Radial")
        app_name.setAlignment(Qt.AlignCenter)
        app_name.setFont(QFont(FONT_FAMILY, 17, QFont.Bold))
        app_name.setStyleSheet("color: #FFFFFF;")
        header_layout.addWidget(app_name)

        version_label = QLabel("lime-radial-windows • v1.0.0 (Open Source)")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setFont(QFont(FONT_FAMILY, 9))
        version_label.setStyleSheet("color: #84CC16; font-weight: bold;")
        header_layout.addWidget(version_label)

        card_layout.addLayout(header_layout)

        # Texto informativo con créditos y descargo de responsabilidad
        info_browser = QTextBrowser()
        info_browser.setOpenExternalLinks(True)
        html_content = f"""
        <div style="font-family: '{FONT_FAMILY}', sans-serif; color: #D1D5DB; font-size: 12px; line-height: 1.5;">
            <p><b>Lime Radial</b> es una utilidad de productividad de código abierto para Windows diseñada para la manipulación y conversión rápida de archivos mediante un menú radial con interacción Shift + Arrastre.</p>
            
            <p style="margin-top: 10px;"><b>Licencia:</b> Distribuido bajo la Licencia MIT.</p>
            
            <p style="margin-top: 10px;"><b>Créditos a Proyectos de Terceros:</b></p>
            <ul style="margin-top: 4px; padding-left: 18px; color: #9CA3AF;">
                <li><b>PySide6 (Qt)</b> — Interfaz gráfica y motor vectorial QPainter.</li>
                <li><b>FFmpeg</b> (vía imageio-ffmpeg) — Procesamiento de audio y video.</li>
                <li><b>Pillow & Pillow-HEIF</b> — Conversión de imágenes y soporte HEIC.</li>
                <li><b>PyMuPDF</b> — Renderizado y extracción de documentos PDF.</li>
                <li><b>python-docx, python-pptx & openpyxl</b> — Soporte de documentos Office.</li>
                <li><b>Plus Jakarta Sans</b> — Tipografía (Licencia SIL Open Font).</li>
            </ul>

            <div style="margin-top: 14px; padding: 10px 12px; background-color: rgba(255, 255, 255, 0.06); border-left: 3px solid #84CC16; border-radius: 4px; color: #E5E7EB; font-size: 11px;">
                <b>Disclaimer:</b> This project is an independent open-source utility for Windows and is not affiliated, associated, authorized, endorsed by, or in any way officially connected with Leap Studio or the original Tangerine app for macOS.
            </div>
        </div>
        """
        info_browser.setHtml(html_content)
        card_layout.addWidget(info_browser, 1)

        # Botón inferior Aceptar
        bot_bar = QHBoxLayout()
        ok_btn = QPushButton("Cerrar")
        ok_btn.setFixedWidth(100)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #84CC16;
                color: #111827;
                font-weight: bold;
                border: 1px solid #A3E635;
                padding: 8px 16px;
                border-radius: 9px;
            }
            QPushButton:hover {
                background-color: #A3E635;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        bot_bar.addStretch()
        bot_bar.addWidget(ok_btn)
        bot_bar.addStretch()
        card_layout.addLayout(bot_bar)

        root.addWidget(card)
