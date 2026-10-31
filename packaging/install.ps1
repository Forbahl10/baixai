# Instala o aplicativo auxiliar do Baixaí para o usuário atual (Windows 10/11). Sem administrador.
# Uso:  .\install.ps1                         (usa o ID padrão de DEFAULT_EXTENSION_IDS)
#       .\install.ps1 -ExtensionId ID1,ID2     (IDs informados)
param(
  [string[]]$ExtensionId,
  [ValidateSet('chrome', 'chromium', 'edge', 'brave')][string[]]$Browser = @('chrome'),
  [switch]$WithFfmpeg, [switch]$NoFfmpeg
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppRoot = Join-Path $env:APPDATA 'Baixai'
$AppDir = Join-Path $AppRoot 'app'
if (-not (Test-Path (Join-Path $Here 'baixai-helper'))) { throw 'Pasta baixai-helper\ não encontrada ao lado do instalador.' }

# Aceita também IDs passados separados por espaço (instalar.bat ID1 ID2)
if (-not $ExtensionId -or $ExtensionId.Count -eq 0) {
  $defaults = Join-Path $Here 'DEFAULT_EXTENSION_IDS'
  if (Test-Path $defaults) {
    $ExtensionId = @(Get-Content $defaults | Where-Object { $_.Trim() })
    Write-Host "Usando o ID padrão de DEFAULT_EXTENSION_IDS (extensão carregada a partir do pacote 'manual')."
  } else { throw 'Informe o ID da extensão: .\install.ps1 -ExtensionId <ID>' }
}

Write-Host "==> Instalando o aplicativo em: $AppDir"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
$Dest = Join-Path $AppDir 'baixai-helper'
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
Copy-Item -Recurse (Join-Path $Here 'baixai-helper') $Dest
$Helper = Join-Path $Dest 'baixai-helper.exe'
Get-ChildItem -Recurse $Dest | Unblock-File   # remove a marca de "baixado da internet"

$hostArgs = @('install-host')
foreach ($i in $ExtensionId) { $hostArgs += @('--extension-id', $i) }
foreach ($b in $Browser) { $hostArgs += @('--browser', $b) }
$hostArgs += @('--exec', $Helper)
Write-Host '==> Registrando o host Native Messaging (somente para o seu usuário)'
& $Helper @hostArgs | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Falha ao registrar o host Native Messaging.' }

function Ask($q) { if ($WithFfmpeg) { return $true }; $a = Read-Host "$q [s/N]"; return ($a -match '^(s|y)') }
$haveWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
$haveFfmpeg = [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\ffmpeg.exe'))
if (-not $haveFfmpeg -and -not $NoFfmpeg) {
  Write-Host '==> FFmpeg não encontrado (necessário para MP3 e para combinar vídeo e áudio).'
  if ($haveWinget -and (Ask 'Instalar o FFmpeg com o winget (pacote Gyan.FFmpeg, licença GPL)?')) {
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  } else { Write-Host '    Instale depois com:  winget install --id Gyan.FFmpeg' }
}
$haveJs = [bool](Get-Command deno -ErrorAction SilentlyContinue) -or [bool](Get-Command node -ErrorAction SilentlyContinue)
if (-not $haveJs -and -not $NoFfmpeg) {
  Write-Host '==> Deno/Node.js não encontrado (ajuda o YouTube a funcionar por completo).'
  if ($haveWinget -and (Ask 'Instalar o Deno com o winget (DenoLand.Deno, licença MIT)?')) {
    winget install --id DenoLand.Deno -e --accept-source-agreements --accept-package-agreements
  } else { Write-Host '    Opcional. Depois:  winget install --id DenoLand.Deno' }
}

Write-Host '==> Diagnóstico'
& $Helper doctor
Write-Host "`nPronto. Reinicie o Chrome e abra o Baixaí: deve aparecer 'Aplicativo local conectado'."
