# Remove o Baixaí (comando, aplicativo, FFmpeg/Deno baixados e a entrada de PATH). -PurgeData apaga também fila, histórico e logs.
param([switch]$PurgeData)
$ErrorActionPreference = 'Continue'
$AppRoot = Join-Path $env:APPDATA 'Baixai'
$CmdDir = Join-Path $AppRoot 'cmd'
$Helper = Join-Path $AppRoot 'app\baixai-helper\baixai-helper.exe'
if (Test-Path $Helper) {
  $a = @('uninstall-host'); if ($PurgeData) { $a += '--purge-data' }
  & $Helper @a 2>&1 | Out-Null
}
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath) {
  $kept = ($userPath -split ';') | Where-Object { $_ -and $_ -ne $CmdDir }
  [Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'User')
}
foreach ($d in 'app', 'bin', 'cmd', 'downloads-tmp') { Remove-Item -Recurse -Force (Join-Path $AppRoot $d) -ErrorAction SilentlyContinue }
if ($PurgeData) { Remove-Item -Recurse -Force $AppRoot -ErrorAction SilentlyContinue } else { Remove-Item -Force (Join-Path $AppRoot 'desinstalar.ps1') -ErrorAction SilentlyContinue }
Write-Host 'Baixaí removido. Seus downloads não foram tocados.'
