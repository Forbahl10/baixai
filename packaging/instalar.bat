@echo off
rem Instala o Baixai para o usuario atual. Dispensa mudar a politica de execucao do PowerShell.
rem Uso: instalar.bat            (usa o ID padrao de DEFAULT_EXTENSION_IDS)
rem      instalar.bat ID_DA_EXTENSAO [OUTRO_ID]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
