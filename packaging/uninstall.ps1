param([switch]$PurgeData)
$ErrorActionPreference = 'Stop'
$AppRoot = Join-Path $env:APPDATA 'Baixai'
$Helper = Join-Path $AppRoot 'app\baixai-helper\baixai-helper.exe'
if (Test-Path $Helper) { if ($PurgeData) { & $Helper uninstall-host --purge-data } else { & $Helper uninstall-host } }
Remove-Item -Recurse -Force (Join-Path $AppRoot 'app') -ErrorAction SilentlyContinue
if ($PurgeData) { Remove-Item -Recurse -Force $AppRoot -ErrorAction SilentlyContinue }
Write-Host 'Aplicativo auxiliar removido. Seus downloads não foram tocados. Remova a extensão em chrome://extensions.'
