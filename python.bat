@echo off
rem GmaGIS python console - ASCII only.
rem Opens a shell using the bundled interpreter.
rem   python.bat           -> interactive REPL
rem   python.bat script.py -> run a script

setlocal
set "GGIS_HOME=%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
"%GGIS_HOME%python\python.exe" %*
endlocal
