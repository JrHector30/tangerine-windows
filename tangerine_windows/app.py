"""
Coordinador principal de la aplicación Tangerine Windows.
Completamente silencioso (sin notificaciones emergentes).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QPoint, QRunnable, QThreadPool, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from .convert import convert_files
from .radial import RadialMenu
from .tray import TangerineTray
from .trigger import DragShiftWatcher


class ConversionTask(QRunnable):
    def __init__(self, paths: List[str], target_format: str):
        super().__init__()
        self.paths = paths
        self.target_format = target_format

    def run(self):
        try:
            # Conversión en segundo plano de alta velocidad
            convert_files(self.paths, self.target_format)
        except Exception as e:
            print(f"[Tangerine Error] Falló la conversión: {e}", file=sys.stderr)


class TangerineApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.qapp.setQuitOnLastWindowClosed(False)
        self.thread_pool = QThreadPool.globalInstance()

        # 1. Menú radial flotante
        self.radial_menu = RadialMenu(size=360)
        self.radial_menu.file_dropped.connect(self._on_files_dropped)

        # 2. Detector de Shift + Drag
        self.watcher = DragShiftWatcher(
            is_menu_visible=self.radial_menu.isVisible,
            has_menu_drag=lambda: self.radial_menu.has_drag,
        )
        self.watcher.show_menu.connect(self._on_trigger_show)
        self.watcher.hide_menu.connect(self._on_trigger_hide)

        # 3. Icono en bandeja de sistema
        self.tray = TangerineTray(
            on_toggle_enabled=self._on_toggle_watcher,
            on_change_key=self.watcher.set_trigger_key,
            on_test_menu=self._on_test_menu,
            on_quit=self._on_quit,
        )
        self.tray.show()

        # Iniciar monitoreo global
        self.watcher.start()

    def _on_trigger_show(self, pos: QPoint):
        self.radial_menu.popup_at(pos)

    def _on_trigger_hide(self):
        self.radial_menu.close_menu()

    def _on_test_menu(self):
        pos = QCursor.pos()
        self.radial_menu.popup_at(pos)

    def _on_toggle_watcher(self, enabled: bool):
        self.watcher.enabled = enabled

    def _on_files_dropped(self, paths: List[str], target_format: str):
        """
        Procesa y convierte los archivos soltados en un hilo de fondo.
        Completamente silencioso: no emite notificaciones emergentes de Windows.
        """
        task = ConversionTask(paths, target_format)
        self.thread_pool.start(task)

    def _on_quit(self):
        self.watcher.stop()
        self.radial_menu.close_menu()
        self.tray.hide()
        self.qapp.quit()
