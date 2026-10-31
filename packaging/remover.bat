@echo off
rem Remove o Baixai (use remover.bat -PurgeData para apagar tambem fila, historico e logs).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
echo.
pause
