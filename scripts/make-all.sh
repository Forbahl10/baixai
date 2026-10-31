#!/bin/sh
# Testa e gera todos os artefatos em dist/. Não publica nada.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
PY=${PYTHON:-.venv/bin/python}
# Ferramentas locais do projeto (opcional): Node e FFmpeg em .tools/
if [ -d .tools/node/bin ]; then
  PATH="$ROOT/.tools/node/bin:$ROOT/.tools/bin:$PATH"; export PATH
  BAIXAI_TOOLS_PATH="$ROOT/.tools/bin:$ROOT/.tools/node/bin"; export BAIXAI_TOOLS_PATH
fi
echo "== 1/6 testes do helper";    "$PY" -m pytest helper/tests -q
echo "== 2/6 tipos da extensão";   npx tsc -p extension/tsconfig.json --noEmit
echo "== 3/6 testes da extensão";  node scripts/test-extension.mjs 2>&1 | grep -E '^# (tests|pass|fail)'
echo "== 4/6 extensão (dir + zip)"; node scripts/build-extension.mjs
echo "== 5/6 pacote do helper";    scripts/package-helper.sh
echo "== 6/6 site";                scripts/build-site.sh >/dev/null && echo "dist/site pronto"
echo; cat dist/SHA256SUMS.txt
