#!/bin/sh
# Monta dist/site/ (página estática + pacotes). Não publica nada.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
VERSION=$(sed -n 's/.*"version": "\(.*\)".*/\1/p' package.json | head -1)
OUT=dist/site; rm -rf "$OUT"; mkdir -p "$OUT/downloads"
cp site/style.css "$OUT/"; cp extension/public/icons/icon-128.png "$OUT/"
MAC="dist/baixai-helper-$VERSION-macos-arm64.tar.gz"
SHA_MAC=$( [ -f "$MAC" ] && shasum -a 256 "$MAC" | cut -d' ' -f1 || echo "(pacote não gerado)")
for f in site/index.html site/privacidade.html; do
  sed -e "s/{{VERSION}}/$VERSION/g" -e "s/{{SHA_MAC}}/$SHA_MAC/g" "$f" > "$OUT/$(basename "$f")"
done
for f in "dist/baixai-extension-$VERSION.zip" "$MAC" "dist/baixai-source-$VERSION.tar.gz" dist/SHA256SUMS.txt; do [ -f "$f" ] && cp "$f" "$OUT/downloads/"; done
echo "Site em $OUT (pronto para hospedar; NÃO foi publicado)"; ls "$OUT" "$OUT/downloads"
