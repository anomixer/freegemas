#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
DIST_DIR="${SCRIPT_DIR}/dist"

echo "=== Building Freegemas WebAssembly ==="

mkdir -p "${BUILD_DIR}"
mkdir -p "${DIST_DIR}"

cd "${BUILD_DIR}"
emcmake cmake "${SCRIPT_DIR}"
cmake --build . --parallel 4

# Copy outputs to dist/
cp index.html index.js index.wasm index.data "${DIST_DIR}/"
[ -f "${SCRIPT_DIR}/logo.png" ] && cp "${SCRIPT_DIR}/logo.png" "${DIST_DIR}/"
touch "${DIST_DIR}/.nojekyll"

echo "=== Build Complete! Outputs in ${DIST_DIR} ==="
echo "To preview locally: python3 -m http.server 8080 -d ${DIST_DIR}"
