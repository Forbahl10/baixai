#!/bin/sh
# Instala o aplicativo auxiliar do Baixaí para o usuário atual (macOS e Linux). Sem sudo.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
case "$(uname -s)" in
  Darwin) APP_ROOT="$HOME/Library/Application Support/Baixai" ;;
  *) APP_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/baixai" ;;
esac
APP_DIR="$APP_ROOT/app"
IDS=""; BROWSERS=""; FFMPEG_MODE="ask"

usage() {
  cat <<EOF
Uso: ./install.sh --extension-id ID [--extension-id ID2] [--browser chrome|chromium|edge|brave] [--with-ffmpeg|--no-ffmpeg]

  --extension-id   ID da extensão (chrome://extensions, modo desenvolvedor). Repita para desenvolvimento e produção.
  --browser        Navegadores a registrar (padrão: chrome). Pode repetir.
  --with-ffmpeg    Baixa o FFmpeg (macOS arm64) sem perguntar.   --no-ffmpeg  Não oferece o FFmpeg.
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --extension-id) IDS="$IDS --extension-id $2"; shift 2 ;;
    --browser) BROWSERS="$BROWSERS --browser $2"; shift 2 ;;
    --with-ffmpeg) FFMPEG_MODE="yes"; shift ;;
    --no-ffmpeg) FFMPEG_MODE="no"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opção desconhecida: $1" >&2; usage >&2; exit 2 ;;
  esac
done
if [ -z "$IDS" ]; then
  if [ -f "$HERE/DEFAULT_EXTENSION_IDS" ]; then
    for i in $(cat "$HERE/DEFAULT_EXTENSION_IDS"); do IDS="$IDS --extension-id $i"; done
    echo "Usando os IDs padrão de $HERE/DEFAULT_EXTENSION_IDS (extensão carregada descompactada)."
  else
    echo "Informe o ID da extensão com --extension-id." >&2; usage >&2; exit 2
  fi
fi
[ -d "$HERE/baixai-helper" ] || { echo "Pasta baixai-helper/ não encontrada ao lado do instalador." >&2; exit 1; }

echo "==> Instalando o aplicativo em: $APP_DIR"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/baixai-helper"
cp -R "$HERE/baixai-helper" "$APP_DIR/baixai-helper"
HELPER="$APP_DIR/baixai-helper/baixai-helper"
chmod +x "$HELPER"
# Arquivos baixados pelo navegador vêm com quarentena do macOS; este instalador foi executado por você.
[ "$(uname -s)" = "Darwin" ] && xattr -dr com.apple.quarantine "$APP_DIR/baixai-helper" 2>/dev/null || true

echo "==> Registrando o host Native Messaging"
# shellcheck disable=SC2086
"$HELPER" install-host $IDS ${BROWSERS:---browser chrome} --exec "$HELPER"

have_ffmpeg() { command -v ffmpeg >/dev/null 2>&1 || [ -x /opt/homebrew/bin/ffmpeg ] || [ -x /usr/local/bin/ffmpeg ] || [ -x "$APP_ROOT/bin/ffmpeg" ]; }
FF_BASE="https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2"
FF_SHA_FFMPEG="c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924"
FF_SHA_FFPROBE="fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6"
sha256() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }

if ! have_ffmpeg && [ "$FFMPEG_MODE" != "no" ]; then
  echo "==> FFmpeg não encontrado. Ele é necessário para MP3 e para combinar vídeo e áudio."
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    ANS="n"
    if [ "$FFMPEG_MODE" = "yes" ]; then ANS="s"; else
      echo "    Posso baixar o build do FFmpeg 9.0.2 (ffmpeg.martin-riedl.de), licença GPL-3.0-ou-posterior,"
      echo "    verificar o SHA-256 e guardá-lo em $APP_ROOT/bin (nada fora dessa pasta)."
      printf "    Baixar agora? [s/N] "; read -r ANS || ANS="n"
    fi
    case "$ANS" in s|S|y|Y)
      mkdir -p "$APP_ROOT/bin"; TMP=$(mktemp -d)
      for pair in "ffmpeg:$FF_SHA_FFMPEG" "ffprobe:$FF_SHA_FFPROBE"; do
        n=${pair%%:*}; want=${pair##*:}
        curl -fsSL -o "$TMP/$n.zip" "$FF_BASE/$n.zip" || { echo "Falha ao baixar $n."; rm -rf "$TMP"; exit 1; }
        [ "$(sha256 "$TMP/$n.zip")" = "$want" ] || { echo "SHA-256 de $n não confere; abortado."; rm -rf "$TMP"; exit 1; }
        unzip -oq "$TMP/$n.zip" -d "$APP_ROOT/bin"; chmod +x "$APP_ROOT/bin/$n"
        xattr -dr com.apple.quarantine "$APP_ROOT/bin/$n" 2>/dev/null || true
      done
      rm -rf "$TMP"; echo "    FFmpeg instalado em $APP_ROOT/bin" ;;
    *) echo "    Ok, sem FFmpeg por enquanto." ;;
    esac
  else
    echo "    Instale-o pelo gerenciador de pacotes: macOS (Homebrew): brew install ffmpeg · Debian/Ubuntu: sudo apt install ffmpeg · Fedora: sudo dnf install ffmpeg"
  fi
fi

echo "==> Diagnóstico"
"$HELPER" doctor || true
echo
echo "Pronto. Reinicie o Chrome e abra o Baixaí: deve aparecer \"Aplicativo local conectado\"."
echo "Para remover: ./uninstall.sh"
