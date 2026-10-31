# Instalação rápida do Baixaí (Windows 10/11). No PowerShell:
#   irm https://raw.githubusercontent.com/Forbahl10/baixai/main/get.ps1 | iex
# Baixa o pacote da última Release do GitHub, confere o SHA-256, instala o aplicativo auxiliar para o seu usuário
# (sem administrador) e deixa a extensão pronta em %USERPROFILE%\Baixai\extensao.
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
  $Ext = "baixai-extension-$Version-manual.zip"
  foreach ($f in @($Pkg, $Ext, 'SHA256SUMS.txt')) {
    Write-Host "    baixando $f"
    Invoke-WebRequest -UseBasicParsing -Uri "$Url/$f" -OutFile (Join-Path $Tmp $f)
  }
  Write-Host '==> Conferindo a integridade (SHA-256)'
  $sums = Get-Content (Join-Path $Tmp 'SHA256SUMS.txt')
  foreach ($f in @($Pkg, $Ext)) {
    $line = $sums | Where-Object { $_ -match ("\s\*?" + [regex]::Escape($f) + "$") } | Select-Object -First 1
    $want = if ($line) { ($line -split '\s+')[0].ToLower() } else { '' }
    $got = (Get-FileHash -Algorithm SHA256 (Join-Path $Tmp $f)).Hash.ToLower()
    if (-not $want -or $want -ne $got) { throw "O SHA-256 de $f não confere; nada foi instalado." }
  }
  Write-Host '    ok'

  Write-Host '==> Preparando a extensão em %USERPROFILE%\Baixai\extensao'
  $ExtDir = Join-Path $env:USERPROFILE 'Baixai\extensao'
  if (Test-Path $ExtDir) { Remove-Item -Recurse -Force $ExtDir }
  New-Item -ItemType Directory -Force -Path $ExtDir | Out-Null
  Expand-Archive -Path (Join-Path $Tmp $Ext) -DestinationPath $ExtDir -Force

  Write-Host '==> Instalando o aplicativo auxiliar'
  Expand-Archive -Path (Join-Path $Tmp $Pkg) -DestinationPath $Tmp -Force
  $PkgDir = Join-Path $Tmp "baixai-helper-$Version-windows-x86_64"
  & (Join-Path $PkgDir 'install.ps1')
  $UninstDir = Join-Path $env:USERPROFILE 'Baixai'
  Copy-Item (Join-Path $PkgDir 'uninstall.ps1') (Join-Path $UninstDir 'desinstalar.ps1') -Force
  $IdExt = (Get-Content (Join-Path $PkgDir 'DEFAULT_EXTENSION_IDS') -ErrorAction SilentlyContinue | Select-Object -First 1)

  Write-Host @"

==> Falta só 1 passo, que o Chrome não deixa nenhum programa fazer por você:
    1. Abra  chrome://extensions
    2. Ative o "Modo do desenvolvedor" (canto superior direito)
    3. Clique em "Carregar sem compactação" e escolha a pasta:
         $ExtDir
    4. Confira se o ID da extensão é: $IdExt
    5. Reinicie o Chrome e abra o Baixaí: deve aparecer "Aplicativo local conectado".

    Não apague nem mova a pasta acima: o Chrome lê a extensão dela.
    Para remover tudo depois: powershell -ExecutionPolicy Bypass -File "$UninstDir\desinstalar.ps1"
"@
  Start-Process explorer.exe $ExtDir
} finally {
  Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
