#!/bin/sh
# Instala o Baixaí para o usuário atual (macOS e Linux). Sem sudo. Deixa o comando `baixai` pronto para uso no terminal.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
case "$(uname -s)" in
  Darwin) APP_ROOT="$HOME/Library/Application Support/Baixai" ;;
  *) APP_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/baixai" ;;
esac
APP_DIR="$APP_ROOT/app"
BIN_DIR="$HOME/.local/bin"
IDS=""; BROWSERS=""; DEPS="ask"; PATHMODE="ask"; WITH_EXT="no"

usage() {
  cat <<EOF
Uso: ./install.sh [--deps|--no-deps] [--no-path] [--with-extension | --extension-id ID ...]

  --deps / --no-deps   Baixa (ou não) o FFmpeg e o Deno sem perguntar. Sem a opção, pergunta.
  --no-path            Não mexe no PATH do seu shell (só mostra o que fazer).
  --with-extension     Também registra o host da extensão do Chrome (ID de DEFAULT_EXTENSION_IDS).
  --extension-id ID    Registra o host para este ID de extensão (pode repetir). --browser chrome|chromium|edge|brave.
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --deps) DEPS="yes"; shift ;;
    --no-deps|--no-ffmpeg) DEPS="no"; shift ;;
    --with-ffmpeg) DEPS="yes"; shift ;;
    --no-path) PATHMODE="no"; shift ;;
    --with-extension) WITH_EXT="yes"; shift ;;
    --extension-id) IDS="$IDS --extension-id $2"; shift 2 ;;
    --browser) BROWSERS="$BROWSERS --browser $2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[ -d "$HERE/baixai-helper" ] || { echo "Pasta baixai-helper/ não encontrada ao lado do instalador." >&2; exit 1; }

ask() { # ask "pergunta" -> 0 se sim (Enter = sim). Sem terminal: não.
  if ! ( : </dev/tty ) 2>/dev/null; then return 1; fi
  printf '%s [S/n] ' "$1" >/dev/tty; read -r ANS </dev/tty || ANS="n"
  case "$ANS" in n|N|nao|não|NAO|NÃO) return 1 ;; *) return 0 ;; esac
}

echo "==> Instalando o aplicativo em: $APP_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR"
rm -rf "$APP_DIR/baixai-helper"
cp -R "$HERE/baixai-helper" "$APP_DIR/baixai-helper"
HELPER="$APP_DIR/baixai-helper/baixai-helper"
chmod +x "$HELPER"
# Arquivos baixados pelo navegador vêm com quarentena do macOS; este instalador foi executado por você.
[ "$(uname -s)" = "Darwin" ] && xattr -dr com.apple.quarantine "$APP_DIR/baixai-helper" 2>/dev/null || true
cp "$HERE/uninstall.sh" "$APP_ROOT/desinstalar.sh" && chmod +x "$APP_ROOT/desinstalar.sh"

echo "==> Criando o comando: $BIN_DIR/baixai"
printf '#!/bin/sh\nexec "%s" "$@"\n' "$HELPER" > "$BIN_DIR/baixai"
chmod +x "$BIN_DIR/baixai"

ON_PATH="yes"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) ON_PATH="no" ;; esac
if [ "$ON_PATH" = "no" ]; then
  case "$(basename "${SHELL:-sh}")" in
    zsh) RC="$HOME/.zshrc" ;;
    bash) if [ "$(uname -s)" = "Darwin" ]; then RC="$HOME/.bash_profile"; else RC="$HOME/.bashrc"; fi ;;
    *) RC="" ;;
  esac
  if [ -n "$RC" ] && grep -q '# baixai$' "$RC" 2>/dev/null; then
    ON_PATH="configured"
  elif [ -n "$RC" ] && [ "$PATHMODE" != "no" ] && ask "==> Para usar só digitando 'baixai', posso acrescentar uma linha ao seu $RC (adiciona $BIN_DIR ao PATH). Pode?"; then
    printf '\n# Baixaí (adicionado pelo instalador)\nexport PATH="$HOME/.local/bin:$PATH" # baixai\n' >> "$RC"
    ON_PATH="configured"
    echo "    ok: linha adicionada em $RC"
  fi
fi

# FFmpeg (MP3 e vídeo em alta qualidade) e Deno (YouTube): opcionais, verificados por SHA-256, guardados só na pasta do Baixaí.
NEED_DEPS="no"
case "$DEPS" in
  yes) NEED_DEPS="yes" ;;
  ask) if "$HELPER" tools install-deps --if-missing --dry-run >/dev/null 2>&1; then :; else
         if ask "==> Falta o FFmpeg e/ou o Deno (MP3, vídeo em alta qualidade e YouTube dependem deles). Baixar agora (~100 MB, SHA-256 conferido, ficam só na pasta do Baixaí)?"; then NEED_DEPS="yes"; fi
       fi ;;
esac
if [ "$NEED_DEPS" = "yes" ]; then "$HELPER" tools install-deps --if-missing || echo "    Não foi possível instalar tudo; rode depois:  baixai tools install-deps"; fi

if [ "$WITH_EXT" = "yes" ] || [ -n "$IDS" ]; then
  if [ -z "$IDS" ]; then for i in $(cat "$HERE/DEFAULT_EXTENSION_IDS" 2>/dev/null); do IDS="$IDS --extension-id $i"; done; fi
  echo "==> Registrando o host da extensão do Chrome (opcional)"
  # shellcheck disable=SC2086
  "$HELPER" install-host $IDS ${BROWSERS:---browser chrome} --exec "$HELPER" >/dev/null
fi

echo "==> Diagnóstico"
"$HELPER" doctor || true
echo
echo "Pronto! Para baixar, coloque o link entre aspas:"
if [ "$ON_PATH" = "configured" ]; then
  echo "    Abra um NOVO terminal e digite:   baixai \"LINK\""
elif [ "$ON_PATH" = "yes" ]; then
  echo "    baixai \"LINK\""
else
  echo "    $BIN_DIR/baixai \"LINK\""
  echo "    (para digitar só 'baixai', acrescente ao seu shell:  export PATH=\"\$HOME/.local/bin:\$PATH\")"
fi
echo "    Mais exemplos:  baixai --help      Para remover:  \"$APP_ROOT/desinstalar.sh\""
