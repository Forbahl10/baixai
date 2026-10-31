#!/bin/sh
# Instalação rápida do Baixaí pelo terminal (macOS e Linux). Cole:
#   curl -fsSL https://raw.githubusercontent.com/Forbahl10/baixai/main/get.sh | sh
# Baixa o pacote da última Release do GitHub, confere o SHA-256 e instala para o seu usuário (sem sudo).
# Depois é só usar:  baixai "LINK"      Opções do instalador: curl ... | sh -s -- --deps --no-path
set -eu

REPO="Forbahl10/baixai"
BASE="${BAIXAI_BASE_URL:-https://github.com/$REPO/releases}"
say() { printf '%s\n' "$*"; }
die() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "preciso do comando '$1', que não foi encontrado."; }
need curl; need tar

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

for f in "$PKG" SHA256SUMS.txt; do
  say "    baixando $f"
  curl -fL --proto-redir '=https' --progress-bar -o "$TMP/$f" "$URL/$f" || die "falha ao baixar $URL/$f"
done

say "==> Conferindo a integridade (SHA-256)"
if command -v sha256sum >/dev/null 2>&1; then SUM="sha256sum"; else SUM="shasum -a 256"; fi
WANT=$(grep " $PKG\$" "$TMP/SHA256SUMS.txt" | cut -d' ' -f1)
GOT=$($SUM "$TMP/$PKG" | cut -d' ' -f1)
[ -n "$WANT" ] && [ "$WANT" = "$GOT" ] || die "o SHA-256 de $PKG não confere; nada foi instalado."
say "    ok"

tar -xzf "$TMP/$PKG" -C "$TMP"
cd "$TMP/baixai-helper-$VERSION-$TARGET"
# Com 'curl | sh' a entrada padrão é o pipe: as perguntas do instalador precisam vir do teclado (/dev/tty).
if ( : </dev/tty ) 2>/dev/null; then ./install.sh "$@" </dev/tty; else ./install.sh "$@"; fi
