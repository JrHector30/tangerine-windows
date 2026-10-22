' Ejecuta Lime Radial Windows en segundo plano sin ventana de consola
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python run.py", 0, False
