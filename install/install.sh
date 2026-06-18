#!/usr/bin/env sh
set -eu

MODE="local"
ENDPOINT=""
TOKEN=""
VERSION="latest"
REPO="${CSGS_REPO:-decrystal/codex-work-trace}"
MARKETPLACE_SOURCE="${CSGS_MARKETPLACE_SOURCE:-https://github.com/${REPO}.git}"
INSTALL_DIR="${CSGS_INSTALL_DIR:-$HOME/.csgs/bin}"
INSTALL_PLUGIN="1"

usage() {
  cat <<'EOF'
Usage: install.sh [options]

Options:
  --mode local|remote       Install mode. Default: local
  --endpoint URL            Required for --mode remote
  --token TOKEN             Bearer token for remote MCP/API access
  --version VERSION         GitHub release version. Default: latest
  --repo OWNER/REPO         GitHub repository. Default: decrystal/codex-work-trace
  --install-dir DIR         Binary install directory. Default: ~/.csgs/bin
  --skip-plugin             Skip Codex plugin installation
  -h, --help                Show help

Environment overrides:
  CSGS_DOWNLOAD_BASE        Release download base URL
  CSGS_MARKETPLACE_SOURCE   Codex plugin marketplace source
  CODEX_BIN                 Codex CLI path
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --endpoint)
      ENDPOINT="${2:-}"
      shift 2
      ;;
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      MARKETPLACE_SOURCE="${CSGS_MARKETPLACE_SOURCE:-https://github.com/${REPO}.git}"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="${2:-}"
      shift 2
      ;;
    --skip-plugin)
      INSTALL_PLUGIN="0"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$MODE" != "local" ] && [ "$MODE" != "remote" ]; then
  echo "--mode must be local or remote" >&2
  exit 2
fi

if [ "$MODE" = "remote" ] && [ -z "$ENDPOINT" ]; then
  echo "--endpoint is required for remote mode" >&2
  exit 2
fi

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$os" in
  darwin) os="darwin" ;;
  linux) os="linux" ;;
  msys*|mingw*|cygwin*) os="windows" ;;
  *) echo "Unsupported OS: $os" >&2; exit 1 ;;
esac

case "$arch" in
  x86_64|amd64) arch="amd64" ;;
  arm64|aarch64) arch="arm64" ;;
  *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac

asset="csgs-${os}-${arch}"
if [ "$os" = "windows" ]; then
  asset="${asset}.exe"
fi

base="${CSGS_DOWNLOAD_BASE:-https://github.com/${REPO}/releases}"
if [ "$VERSION" = "latest" ]; then
  url="${base}/latest/download/${asset}"
else
  url="${base}/download/${VERSION}/${asset}"
fi

tmp="${TMPDIR:-/tmp}/csgs-install-$$"
rm -f "$tmp"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$url" -o "$tmp"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$url" -O "$tmp"
else
  echo "curl or wget is required" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"
csgs_bin="${INSTALL_DIR}/csgs"
if [ "$os" = "windows" ]; then
  csgs_bin="${INSTALL_DIR}/csgs.exe"
fi
mv "$tmp" "$csgs_bin"
chmod +x "$csgs_bin"

if [ "$INSTALL_PLUGIN" = "1" ]; then
  codex_bin="${CODEX_BIN:-}"
  if [ -z "$codex_bin" ] && command -v codex >/dev/null 2>&1; then
    codex_bin="$(command -v codex)"
  fi
  if [ -z "$codex_bin" ] && [ -x "/Applications/Codex.app/Contents/Resources/codex" ]; then
    codex_bin="/Applications/Codex.app/Contents/Resources/codex"
  fi

  if [ -n "$codex_bin" ] && "$codex_bin" plugin --help >/dev/null 2>&1; then
    "$codex_bin" plugin marketplace add "$MARKETPLACE_SOURCE" >/dev/null 2>&1 || true
    "$codex_bin" plugin add "csgs-${MODE}@csgs" >/dev/null 2>&1 || true
  else
    echo "Codex plugin CLI not found or does not support plugins; skipping plugin install." >&2
  fi
fi

if [ "$MODE" = "local" ]; then
  "$csgs_bin" install --mode local --runtime binary --bin "$csgs_bin"
else
  if [ -n "$TOKEN" ]; then
    "$csgs_bin" install --mode remote --endpoint "$ENDPOINT" --token "$TOKEN" --runtime binary --bin "$csgs_bin"
  else
    "$csgs_bin" install --mode remote --endpoint "$ENDPOINT" --runtime binary --bin "$csgs_bin"
  fi
fi

case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *)
    echo "Add this to your shell PATH if you want to run csgs directly:" >&2
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\"" >&2
    ;;
esac

echo "CSGS installed at $csgs_bin"
