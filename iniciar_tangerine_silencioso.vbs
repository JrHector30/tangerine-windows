' Ejecuta Tangerine Windows en segundo plano sin ventana de consola negra
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python run.py", 0, False
