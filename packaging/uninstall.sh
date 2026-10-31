#!/bin/sh
# Remove o host Native Messaging e o aplicativo auxiliar. Use --purge-data para apagar também fila, histórico e logs.
set -eu
case "$(uname -s)" in
  Darwin) APP_ROOT="$HOME/Library/Application Support/Baixai" ;;
  *) APP_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/baixai" ;;
esac
HELPER="$APP_ROOT/app/baixai-helper/baixai-helper"
PURGE=""; [ "${1:-}" = "--purge-data" ] && PURGE="--purge-data"
if [ -x "$HELPER" ]; then "$HELPER" uninstall-host $PURGE; fi
rm -rf "$APP_ROOT/app"
[ -n "$PURGE" ] && rm -rf "$APP_ROOT"
echo "Aplicativo auxiliar removido. Seus downloads não foram tocados. Remova a extensão em chrome://extensions."
