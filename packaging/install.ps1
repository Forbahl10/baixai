# Instala o Baixaí para o usuário atual (Windows 10/11). Sem administrador. Deixa o comando `baixai` pronto para uso no terminal.
# Uso:  .\install.ps1                       (pergunta antes de baixar FFmpeg/Deno e de mexer no PATH)
#       .\install.ps1 -Deps -NoPath         (sem perguntas)
param(
  [switch]$Deps, [switch]$NoDeps, [switch]$NoPath,
  [switch]$WithExtension, [string[]]$ExtensionId,
  [ValidateSet('chrome', 'chromium', 'edge', 'brave')][string[]]$Browser = @('chrome')
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppRoot = Join-Path $env:APPDATA 'Baixai'
$AppDir = Join-Path $AppRoot 'app'
$CmdDir = Join-Path $AppRoot 'cmd'
if (-not (Test-Path (Join-Path $Here 'baixai-helper'))) { throw 'Pasta baixai-helper\ não encontrada ao lado do instalador.' }

function Run($exe, $argList) {   # chama um programa nativo sem que o stderr dele vire erro do PowerShell
  $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  & $exe @argList 2>&1 | ForEach-Object { "$_" } | Out-Host
  $code = $LASTEXITCODE; $ErrorActionPreference = $old; return $code
}
function Ask($q) {   # Enter = sim. Sem terminal interativo: não.
  if ([Console]::IsInputRedirected) { return $false }
  $a = Read-Host "$q [S/n]"
  return -not ($a -match '^(n|N)')
}

Write-Host "==> Instalando o aplicativo em: $AppDir"
New-Item -ItemType Directory -Force -Path $AppDir, $CmdDir | Out-Null
$Dest = Join-Path $AppDir 'baixai-helper'
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
Copy-Item -Recurse (Join-Path $Here 'baixai-helper') $Dest
$Helper = Join-Path $Dest 'baixai-helper.exe'
Get-ChildItem -Recurse $Dest | Unblock-File   # remove a marca de "baixado da internet"
Copy-Item (Join-Path $Here 'uninstall.ps1') (Join-Path $AppRoot 'desinstalar.ps1') -Force

Write-Host "==> Criando o comando: $CmdDir\baixai.cmd"
Set-Content -Path (Join-Path $CmdDir 'baixai.cmd') -Encoding Oem -Value "@echo off`r`n`"$Helper`" %*"

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$onPath = (($userPath -split ';') -contains $CmdDir) -or (($env:Path -split ';') -contains $CmdDir)
$pathState = if ($onPath) { 'yes' } else { 'no' }
if (-not $onPath -and -not $NoPath -and (Ask "==> Para usar só digitando 'baixai', posso acrescentar $CmdDir ao PATH do seu usuário. Pode?")) {
  $new = if ([string]::IsNullOrEmpty($userPath)) { $CmdDir } else { "$userPath;$CmdDir" }
  [Environment]::SetEnvironmentVariable('Path', $new, 'User')
  $pathState = 'configured'
  Write-Host '    ok: PATH do usuário atualizado'
}

# FFmpeg (MP3 e vídeo em alta qualidade) e Deno (YouTube): opcionais, verificados por SHA-256, guardados só na pasta do Baixaí.
$needDeps = $false
if ($Deps) { $needDeps = $true }
elseif (-not $NoDeps) {
  if ((Run $Helper @('tools', 'install-deps', '--if-missing', '--dry-run')) -ne 0) {
    $needDeps = Ask '==> Falta o FFmpeg e/ou o Deno (MP3, vídeo em alta qualidade e YouTube dependem deles). Baixar agora (~150 MB, SHA-256 conferido, ficam só na pasta do Baixaí)?'
  }
}
if ($needDeps) {
  if ((Run $Helper @('tools', 'install-deps', '--if-missing')) -ne 0) { Write-Host '    Não foi possível instalar tudo; rode depois:  baixai tools install-deps' }
}

if ($WithExtension -or $ExtensionId) {
  if (-not $ExtensionId) { $ExtensionId = @(Get-Content (Join-Path $Here 'DEFAULT_EXTENSION_IDS') | Where-Object { $_.Trim() }) }
  Write-Host '==> Registrando o host da extensão do Chrome (opcional)'
  $hostArgs = @('install-host'); foreach ($i in $ExtensionId) { $hostArgs += @('--extension-id', $i) }
  foreach ($b in $Browser) { $hostArgs += @('--browser', $b) }
  $hostArgs += @('--exec', $Helper)
  if ((Run $Helper $hostArgs) -ne 0) { throw 'Falha ao registrar o host da extensão.' }
}

Write-Host '==> Diagnóstico'
Run $Helper @('doctor') | Out-Null
Write-Host ''
Write-Host 'Pronto! Para baixar, coloque o link entre aspas:'
if ($pathState -eq 'configured') { Write-Host '    Abra um NOVO terminal (PowerShell ou Prompt) e digite:   baixai "LINK"' }
elseif ($pathState -eq 'yes') { Write-Host '    baixai "LINK"' }
else { Write-Host "    & `"$CmdDir\baixai.cmd`" `"LINK`"     (para digitar só 'baixai', adicione $CmdDir ao PATH)" }
Write-Host "    Mais exemplos:  baixai --help      Para remover:  powershell -ExecutionPolicy Bypass -File `"$AppRoot\desinstalar.ps1`""
