"""
Icono de bandeja del sistema (System Tray) para Lime Radial Windows.
Permite gestionar la app silenciosa en segundo plano, cambiar la tecla disparadora,
probar el menú radial y abrir la ventana Acerca de / About.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


def create_lime_icon() -> QIcon:
    """Genera un icono vectorial de Lime (Lima / Citrus verde) en alta resolución."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)

    # Cuerpo de la Lima (Verde Lima brillante)
    painter.setBrush(QBrush(QColor(132, 204, 22)))  # Lime #84CC16
    painter.setPen(QPen(QColor(101, 163, 13), 2))
    painter.drawEllipse(6, 12, 52, 48)

    # Brillo interno / reflejo
    shine_path = QPainterPath()
    shine_path.arcMoveTo(12, 16, 40, 36, 110)
    shine_path.arcTo(12, 16, 40, 36, 110, 60)
    painter.setPen(QPen(QColor(217, 249, 157, 180), 2.5, Qt.SolidLine, Qt.RoundCap))
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(shine_path)

    # Tallo y hojita verde
    leaf_path = QPainterPath()
    leaf_path.moveTo(32, 14)
    leaf_path.quadTo(38, 4, 48, 6)
    leaf_path.quadTo(42, 16, 32, 14)

    painter.setBrush(QBrush(QColor(34, 197, 94)))
    painter.setPen(QPen(QColor(22, 163, 74), 1))
    painter.drawPath(leaf_path)

    painter.end()
    return QIcon(pix)


class LimeTray(QSystemTrayIcon):
    def __init__(
        self,
        on_toggle_enabled: Callable[[bool], None],
        on_change_key: Callable[[str], None],
        on_test_menu: Callable[[], None],
        on_about: Callable[[], None],
        on_quit: Callable[[], None],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(create_lime_icon(), parent)
        self.setToolTip("Lime Radial — Arrastra con Shift para convertir")

        self.on_toggle_enabled = on_toggle_enabled
        self.on_change_key = on_change_key
        self.on_test_menu = on_test_menu
        self.on_about = on_about
        self.on_quit = on_quit

        self._build_menu()
        self.activated.connect(self._on_tray_activated)

    def _build_menu(self):
        menu = QMenu()

        # Título / Estado
        title_action = menu.addAction("🍋 Lime Radial")
        title_action.setEnabled(False)
        menu.addSeparator()

        # Probar menú radial manualmente
        test_action = menu.addAction("✨ Probar menú radial en cursor")
        test_action.triggered.connect(self.on_test_menu)
        menu.addSeparator()

        # Submenú de tecla modificadora
        key_menu = menu.addMenu("⌨️ Tecla disparadora")
        group = QActionGroup(self)

        for key_name in ["Shift", "Ctrl", "Alt"]:
            act = QAction(f"Mantener {key_name} al arrastrar", self, checkable=True)
            if key_name == "Shift":
                act.setChecked(True)
            act.triggered.connect(lambda checked, k=key_name: self.on_change_key(k))
            group.addAction(act)
            key_menu.addAction(act)

        menu.addSeparator()

        # Habilitar / Deshabilitar
        self.toggle_action = menu.addAction("Activado (Shift + Drag)")
        self.toggle_action.setCheckable(True)
        self.toggle_action.setChecked(True)
        self.toggle_action.triggered.connect(self._on_toggle)

        menu.addSeparator()

        # Acerca de / About
        about_action = menu.addAction("ℹ️ Acerca de / About...")
        about_action.triggered.connect(self.on_about)

        menu.addSeparator()

        # Salir
        quit_action = menu.addAction("❌ Salir de Lime Radial")
        quit_action.triggered.connect(self.on_quit)

        self.setContextMenu(menu)

    def _on_toggle(self, checked: bool):
        self.toggle_action.setText("Activado (Shift + Drag)" if checked else "Pausado")
        self.on_toggle_enabled(checked)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.on_test_menu()
