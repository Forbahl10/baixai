# Instalacao rapida do Baixai pelo terminal (Windows 10/11). No PowerShell, cole:
#   irm https://raw.githubusercontent.com/Forbahl10/baixai/main/get.ps1 | iex
# Baixa o pacote da ultima Release do GitHub, confere o SHA-256 e instala para o seu usuario (sem administrador).
# Depois e so usar:  baixai "LINK"
# Opcoes do instalador (opcional), antes do comando acima:  $env:BAIXAI_INSTALL_OPTIONS = 'Deps,NoPath'
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
function Get-Sha256($path) {   # .NET direto: nao depende de modulos do PowerShell
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $fs = [System.IO.File]::OpenRead($path)
  try { return ([BitConverter]::ToString($sha.ComputeHash($fs)) -replace '-', '').ToLower() } finally { $fs.Dispose(); $sha.Dispose() }
}
$Repo = 'Forbahl10/baixai'
$Base = if ($env:BAIXAI_BASE_URL) { $env:BAIXAI_BASE_URL } else { "https://github.com/$Repo/releases" }

$Version = $env:BAIXAI_VERSION
if (-not $Version) {
  $Version = (Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest").tag_name.TrimStart('v')
}
Write-Host "==> Baixai $Version para Windows"
$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("baixai-get-" + [Guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $Tmp | Out-Null
try {
  $Url = "$Base/download/v$Version"
  $Pkg = "baixai-helper-$Version-windows-x86_64.zip"
  foreach ($f in @($Pkg, 'SHA256SUMS.txt')) {
    Write-Host "    baixando $f"
    Invoke-WebRequest -UseBasicParsing -Uri "$Url/$f" -OutFile (Join-Path $Tmp $f)
  }
  Write-Host '==> Conferindo a integridade (SHA-256)'
  $line = Get-Content (Join-Path $Tmp 'SHA256SUMS.txt') | Where-Object { $_ -match ("\s\*?" + [regex]::Escape($Pkg) + "$") } | Select-Object -First 1
  $want = if ($line) { ($line -split '\s+')[0].ToLower() } else { '' }
  $got = Get-Sha256 (Join-Path $Tmp $Pkg)
  if (-not $want -or $want -ne $got) { throw "O SHA-256 de $Pkg nao confere; nada foi instalado." }
  Write-Host '    ok'

  Write-Host '==> Extraindo'
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $Tmp $Pkg), (Join-Path $Tmp 'pkg'))
  $opts = @{}
  foreach ($k in ($env:BAIXAI_INSTALL_OPTIONS -split '[ ,]+' | Where-Object { $_ })) { $opts[$k] = $true }
  & (Join-Path $Tmp "pkg\baixai-helper-$Version-windows-x86_64\install.ps1") @opts
} finally {
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
