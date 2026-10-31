@echo off
rem Instala o Baixai para o usuario atual. Dispensa mudar a politica de execucao do PowerShell.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
