#!/usr/bin/env bash
# Build the React frontend (frontend/dist) on a machine without Node installed,
# e.g. a Cloudera AI session or job. Installs a pinned Node LTS into ~/.local/node
# (Vite 8 needs Node >= 22.12) the first time, then runs `npm ci && npm run build`.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_VERSION="${NODE_VERSION:-v22.14.0}"
NODE_DIR="${NODE_DIR:-$HOME/.local/node}"

if [ ! -x "$NODE_DIR/bin/node" ]; then
  echo "+ installing Node $NODE_VERSION into $NODE_DIR"
  mkdir -p "$(dirname "$NODE_DIR")"
  tmp="$(mktemp -d)"
  curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-x64.tar.xz" | tar -xJ -C "$tmp"
  rm -rf "$NODE_DIR"
  mv "$tmp/node-${NODE_VERSION}-linux-x64" "$NODE_DIR"
  rm -rf "$tmp"
fi
export PATH="$NODE_DIR/bin:$PATH"
export npm_config_cache="${npm_config_cache:-$HOME/.cache/npm}"
echo "+ node $(node --version), npm $(npm --version)"

cd "$REPO_ROOT/frontend"
if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
npm run build
echo "+ built $REPO_ROOT/frontend/dist ($(du -sh dist | cut -f1))"
