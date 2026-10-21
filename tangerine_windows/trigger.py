"""
Detector global de gesto Shift + Drag para Windows.
Usa GetAsyncKeyState de user32.dll:
- Cero impacto en CPU (muestreo a ~15ms).
- No requiere privilegios de Administrador.
- No instala hooks que puedan ralentizar o bloquear el sistema.
"""
from __future__ import annotations

import ctypes
import sys
from typing import Callable, Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor

VK_LBUTTON = 0x01
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_ALT = 0x12
VK_ESCAPE = 0x1B

DRAG_THRESHOLD = 12       # Píxeles mínimos de desplazamiento arrastrando
IDLE_TIMEOUT_TICKS = 45   # ~700 ms sin recibir drop/drag antes de ocultar


class DragShiftWatcher(QObject):
    show_menu = Signal(QPoint)
    hide_menu = Signal()

    def __init__(
        self,
        is_menu_visible: Callable[[], bool],
        has_menu_drag: Callable[[], bool],
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.is_menu_visible = is_menu_visible
        self.has_menu_drag = has_menu_drag
        self.enabled = True
        self.trigger_vk = VK_SHIFT
        self.key_name = "Shift"

        self._down_at: Optional[QPoint] = None
        self._fired = False
        self._idle_ticks = 0
        self._shown_at = QPoint()

        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._tick)

    def set_trigger_key(self, name: str):
        """Permite configurar la tecla modificadora (Shift, Ctrl, Alt)."""
        mapping = {
            "Shift": VK_SHIFT,
            "Ctrl": VK_CONTROL,
            "Alt": VK_ALT,
        }
        self.key_name = name
        self.trigger_vk = mapping.get(name, VK_SHIFT)

    def start(self):
        if self._user32:
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def _is_down(self, vk: int) -> bool:
        if not self._user32:
            return False
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _tick(self):
        if not self.enabled:
            return

        lbtn = self._is_down(VK_LBUTTON)
        trigger = self._is_down(self.trigger_vk)
        esc = self._is_down(VK_ESCAPE)
        pos = QCursor.pos()

        if self.is_menu_visible():
            if not lbtn or esc:
                # El usuario soltó el clic o presionó Esc: dar margen para que dropEvent aterrice
                QTimer.singleShot(100, self.hide_menu.emit)
            elif not self.has_menu_drag():
                # Si el menú apareció pero no llegó un drag de archivos (p.ej. selección de texto),
                # no molestar y cerrar tras un breve tiempo
                dist = (pos - self._shown_at).manhattanLength()
                if dist > 8:
                    self._idle_ticks += 1
                    if self._idle_ticks > IDLE_TIMEOUT_TICKS:
                        self.hide_menu.emit()
        else:
            if lbtn:
                if self._down_at is None:
                    self._down_at = pos
                    self._fired = False

                moved = (pos - self._down_at).manhattanLength() >= DRAG_THRESHOLD
                if moved and trigger and not self._fired:
                    self._fired = True
                    self._idle_ticks = 0
                    self._shown_at = pos
                    self.show_menu.emit(pos)
            else:
                self._down_at = None
                self._fired = False
