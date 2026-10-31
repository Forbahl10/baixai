# Instalação rápida do Baixaí pelo terminal (Windows 10/11). No PowerShell, cole:
#   irm https://raw.githubusercontent.com/Forbahl10/baixai/main/get.ps1 | iex
# Baixa o pacote da última Release do GitHub, confere o SHA-256 e instala para o seu usuário (sem administrador).
# Depois é só usar:  baixai "LINK"
# Opções do instalador (opcional), antes do comando acima:  $env:BAIXAI_INSTALL_OPTIONS = 'Deps,NoPath'
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$Repo = 'Forbahl10/baixai'
$Base = if ($env:BAIXAI_BASE_URL) { $env:BAIXAI_BASE_URL } else { "https://github.com/$Repo/releases" }

$Version = $env:BAIXAI_VERSION
if (-not $Version) {
  $Version = (Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest").tag_name.TrimStart('v')
}
Write-Host "==> Baixaí $Version para Windows"
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
  $got = (Get-FileHash -Algorithm SHA256 (Join-Path $Tmp $Pkg)).Hash.ToLower()
  if (-not $want -or $want -ne $got) { throw "O SHA-256 de $Pkg não confere; nada foi instalado." }
  Write-Host '    ok'

  Expand-Archive -Path (Join-Path $Tmp $Pkg) -DestinationPath $Tmp -Force
  $opts = @{}
  foreach ($k in ($env:BAIXAI_INSTALL_OPTIONS -split '[ ,]+' | Where-Object { $_ })) { $opts[$k] = $true }
  & (Join-Path $Tmp "baixai-helper-$Version-windows-x86_64\install.ps1") @opts
} finally {
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
