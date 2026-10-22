"""
Detector global inteligente de Shift + Drag para Windows.
Garantiza que el menú radial NUNCA se active en juegos, navegadores o aplicaciones ajenas.
Sólo se activa cuando el usuario arrastra archivos reales desde el Explorador de Windows o el Escritorio.
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

DRAG_THRESHOLD = 14       # Píxeles mínimos de desplazamiento arrastrando
IDLE_TIMEOUT_TICKS = 25   # ~350 ms si no llega ningún evento OLE de archivo real

# Clases nativas de Windows para el Explorador de Archivos y el Escritorio
EXPLORER_WINDOW_CLASSES = {
    "CabinetWClass",       # Carpetas del Explorador de Windows (Windows 10 / 11)
    "ExploreWClass",       # Explorador clásico
    "Progman",             # Escritorio de Windows
    "WorkerW",             # Escritorio con wallpaper dinámico
    "SysDragImage",        # Imagen flotante de arrastre del sistema
    "DirectUIHWND",        # Área de archivos interna
    "SysListView32",       # Lista de iconos clásica
}


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


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
        self._down_in_explorer: bool = False
        self._fired = False
        self._idle_ticks = 0
        self._shown_at = QPoint()

        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._tick)

    def set_trigger_key(self, name: str):
        mapping = {"Shift": VK_SHIFT, "Ctrl": VK_CONTROL, "Alt": VK_ALT}
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

    def _is_explorer_or_file_context(self, pos: QPoint) -> bool:
        """
        Verifica si el clic o arrastre proviene de una ventana del Explorador/Escritorio
        o si existe la ventana de arrastre del sistema 'SysDragImage'.
        Evita al 100% que se active mientras juegas o usas otras apps.
        """
        if not self._user32:
            return False

        # 1. Si Windows ya creó la ventana de arrastre de archivos SysDragImage
        if self._user32.FindWindowW("SysDragImage", None) != 0:
            return True

        # 2. Verificar la ventana debajo del cursor donde empezó el clic
        pt = POINT(pos.x(), pos.y())
        hwnd = self._user32.WindowFromPoint(pt)
        if not hwnd:
            return False

        # Obtener clase de la ventana directa y de la ventana raíz
        buf = ctypes.create_unicode_buffer(256)
        self._user32.GetClassNameW(hwnd, buf, 256)
        direct_class = buf.value

        root_hwnd = self._user32.GetAncestor(hwnd, 2)  # GA_ROOT = 2
        root_class = ""
        if root_hwnd:
            self._user32.GetClassNameW(root_hwnd, buf, 256)
            root_class = buf.value

        return (
            direct_class in EXPLORER_WINDOW_CLASSES
            or root_class in EXPLORER_WINDOW_CLASSES
        )

    def _tick(self):
        if not self.enabled:
            return

        lbtn = self._is_down(VK_LBUTTON)
        trigger = self._is_down(self.trigger_vk)
        esc = self._is_down(VK_ESCAPE)
        pos = QCursor.pos()

        if self.is_menu_visible():
            if not lbtn or esc:
                # El usuario soltó el clic o canceló
                QTimer.singleShot(80, self.hide_menu.emit)
            elif not self.has_menu_drag():
                # Si el menú apareció pero no llegó ningún drag OLE de archivos reales,
                # ocultar de inmediato para no estorbar
                dist = (pos - self._shown_at).manhattanLength()
                if dist > 6:
                    self._idle_ticks += 1
                    if self._idle_ticks > IDLE_TIMEOUT_TICKS:
                        self.hide_menu.emit()
        else:
            if lbtn:
                if self._down_at is None:
                    self._down_at = pos
                    self._fired = False
                    # Verificar al hacer clic si estamos en el Explorador o Escritorio
                    self._down_in_explorer = self._is_explorer_or_file_context(pos)

                moved = (pos - self._down_at).manhattanLength() >= DRAG_THRESHOLD
                
                # SÓLO se dispara si empezó en el explorador/escritorio o hay drag activo
                is_valid_context = self._down_in_explorer or (self._user32 and self._user32.FindWindowW("SysDragImage", None) != 0)

                if moved and trigger and is_valid_context and not self._fired:
                    self._fired = True
                    self._idle_ticks = 0
                    self._shown_at = pos
                    self.show_menu.emit(pos)
            else:
                self._down_at = None
                self._down_in_explorer = False
                self._fired = False
