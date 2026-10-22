"""
Punto de entrada de Lime Radial Windows.
Ejecuta: python run.py
"""
import sys
from PySide6.QtWidgets import QApplication
from lime_radial.app import LimeApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Lime Radial")
    app.setOrganizationName("LimeRadial")

    lime = LimeApp(app)
    print("🍋 Lime Radial Windows iniciado exitosamente en segundo plano.")
    print("💡 Mantén pulsado Shift mientras arrastras cualquier archivo en Windows para abrir la rueda.")
    print("👉 Accede a los ajustes o a 'Acerca de' desde el icono en la bandeja del sistema.")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
