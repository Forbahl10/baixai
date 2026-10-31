#!/bin/sh
# Instalação rápida do Baixaí (macOS e Linux). Uso:
#   curl -fsSL https://raw.githubusercontent.com/Forbahl10/baixai/main/get.sh | sh
# Baixa o pacote da última Release do GitHub, confere o SHA-256, instala o aplicativo auxiliar para o seu usuário
# (sem sudo) e deixa a extensão pronta em ~/Baixai/extensao. Não instala nada além disso sem perguntar.
set -eu

REPO="Forbahl10/baixai"
BASE="${BAIXAI_BASE_URL:-https://github.com/$REPO/releases}"
say() { printf '%s\n' "$*"; }
die() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "preciso do comando '$1', que não foi encontrado."; }
need curl; need tar; need unzip

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) TARGET="macos-arm64" ;;
  Darwin-x86_64) TARGET="macos-x86_64" ;;
  Linux-x86_64|Linux-amd64) TARGET="linux-x86_64" ;;
  *) die "sistema não suportado: $(uname -s) $(uname -m). Veja https://github.com/$REPO/releases" ;;
esac

if [ -n "${BAIXAI_VERSION:-}" ]; then
  VERSION="$BAIXAI_VERSION"
else
  VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -1)
  [ -n "$VERSION" ] || die "não consegui descobrir a última versão. Veja https://github.com/$REPO/releases"
fi
say "==> Baixaí $VERSION para $TARGET"

TMP=$(mktemp -d "${TMPDIR:-/tmp}/baixai-get.XXXXXX")
trap 'rm -rf "$TMP"' EXIT INT TERM
URL="$BASE/download/v$VERSION"
PKG="baixai-helper-$VERSION-$TARGET.tar.gz"
EXT="baixai-extension-$VERSION-manual.zip"

for f in "$PKG" "$EXT" SHA256SUMS.txt; do
  say "    baixando $f"
  curl -fL --proto-redir '=https' --progress-bar -o "$TMP/$f" "$URL/$f" || die "falha ao baixar $URL/$f"
done

say "==> Conferindo a integridade (SHA-256)"
if command -v sha256sum >/dev/null 2>&1; then SUM="sha256sum"; else SUM="shasum -a 256"; fi
for f in "$PKG" "$EXT"; do
  WANT=$(grep " $f\$" "$TMP/SHA256SUMS.txt" | cut -d' ' -f1)
  GOT=$($SUM "$TMP/$f" | cut -d' ' -f1)
  [ -n "$WANT" ] && [ "$WANT" = "$GOT" ] || die "o SHA-256 de $f não confere; nada foi instalado."
done
say "    ok"

say "==> Preparando a extensão em ~/Baixai/extensao"
EXT_DIR="$HOME/Baixai/extensao"
rm -rf "$EXT_DIR"; mkdir -p "$EXT_DIR"
unzip -q "$TMP/$EXT" -d "$EXT_DIR"

say "==> Instalando o aplicativo auxiliar"
tar -xzf "$TMP/$PKG" -C "$TMP"
cd "$TMP/baixai-helper-$VERSION-$TARGET"
# Com 'curl | sh' a entrada padrão é o pipe: perguntas (ex.: baixar o FFmpeg) precisam vir do teclado.
if ( : </dev/tty ) 2>/dev/null; then ./install.sh "$@" </dev/tty; else ./install.sh --no-ffmpeg "$@"; fi

IDEXT=$(cat DEFAULT_EXTENSION_IDS 2>/dev/null | head -1 || true)
cat <<EOM

==> Falta só 1 passo, que o Chrome não deixa nenhum programa fazer por você:
    1. Abra  chrome://extensions
    2. Ative o "Modo do desenvolvedor" (canto superior direito)
    3. Clique em "Carregar sem compactação" e escolha a pasta:
         $EXT_DIR
    4. Confira se o ID da extensão é: $IDEXT
    5. Reinicie o Chrome e abra o Baixaí: deve aparecer "Aplicativo local conectado".

    Não apague nem mova a pasta acima: o Chrome lê a extensão dela.
    Para remover tudo depois: rode ~/Baixai/desinstalar.sh
EOM
cp uninstall.sh "$HOME/Baixai/desinstalar.sh" 2>/dev/null && chmod +x "$HOME/Baixai/desinstalar.sh" || true
case "$(uname -s)" in Darwin) open "$EXT_DIR" 2>/dev/null || true ;; esac
