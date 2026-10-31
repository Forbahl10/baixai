#!/bin/sh
# Remove o Baixaí (comando, aplicativo, FFmpeg/Deno baixados e a linha de PATH que o instalador acrescentou).
# Use --purge-data para apagar também a fila, o histórico e os logs. Seus arquivos baixados nunca são tocados.
set -eu
case "$(uname -s)" in
  Darwin) APP_ROOT="$HOME/Library/Application Support/Baixai" ;;
  *) APP_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/baixai" ;;
esac
HELPER="$APP_ROOT/app/baixai-helper/baixai-helper"
PURGE=""; [ "${1:-}" = "--purge-data" ] && PURGE="--purge-data"
if [ -x "$HELPER" ]; then "$HELPER" uninstall-host $PURGE >/dev/null 2>&1 || true; fi
rm -f "$HOME/.local/bin/baixai"
rm -rf "$APP_ROOT/app" "$APP_ROOT/bin" "$APP_ROOT/downloads-tmp"
for RC in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
  if [ -f "$RC" ] && grep -q '# baixai$' "$RC"; then
    grep -v -e '# baixai$' -e '^# Baixaí (adicionado pelo instalador)$' "$RC" > "$RC.baixai-tmp" && cat "$RC.baixai-tmp" > "$RC"; rm -f "$RC.baixai-tmp"
  fi
done
if [ -n "$PURGE" ]; then rm -rf "$APP_ROOT"; else rm -f "$APP_ROOT/desinstalar.sh"; fi
echo "Baixaí removido. Seus downloads não foram tocados."
