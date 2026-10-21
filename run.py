"""
Punto de entrada de Tangerine Windows.
Ejecuta: python run.py
"""
import sys
from PySide6.QtWidgets import QApplication
from tangerine_windows.app import TangerineApp

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tangerine")
    app.setOrganizationName("TangerineWindows")
    
    tangerine = TangerineApp(app)
    print("🍊 Tangerine Windows iniciado exitosamente en segundo plano.")
    print("💡 Mantén pulsado Shift mientras arrastras cualquier archivo en Windows para ver la rueda.")
    print("👉 También puedes hacer doble clic o clic derecho en el icono de la mandarina en la bandeja del sistema.")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
