@echo off
rem GmaGIS launcher - ASCII only.
rem NOTE: cmd.exe parses .bat with the legacy codepage (GBK on zh-CN).
rem       Non-ASCII bytes here would be mangled into bogus commands.
rem NOTE: %%* must not be expanded inside an if (...) block.

setlocal
set "GGIS_HOME=%~dp0"
set "PYEXE=%GGIS_HOME%\python\python.exe"

"%PYEXE%" "%GGIS_HOME%apps\ggis.py" %*

endlocal