#!/usr/bin/env bash
# =============================================================================
# install_apsimx.sh — Build and install the ApsimX CLI for MLPlayground
# =============================================================================
#
# Usage:
#   bash scripts/install_apsimx.sh [--output-dir /path/to/bin]
#
# What it does:
#   1. Checks for dotnet SDK (>= 8.0)
#   2. Clones ApsimX (shallow) if not already present
#   3. Publishes the apsim CLI as self-contained for the current platform
#   4. Prints the path to set as APSIMX_BIN in your .env
#
# After running this script, add to your .env:
#   APSIMX_BIN=/path/to/apsim_bin/apsim
# =============================================================================

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
APSIMX_REPO="https://github.com/APSIMInitiative/ApsimX.git"
CLONE_DIR="${APSIMX_CLONE_DIR:-/tmp/ApsimX}"
OUTPUT_DIR="${1:-${APSIMX_BIN_DIR:-/tmp/apsim_bin}}"
DOTNET_TARGET="net8.0"

# ── Detect platform ──────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS-$ARCH" in
  Darwin-arm64)  RID="osx-arm64"  ;;
  Darwin-x86_64) RID="osx-x64"    ;;
  Linux-aarch64) RID="linux-arm64" ;;
  Linux-x86_64)  RID="linux-x64"  ;;
  *)
    echo "ERROR: Unsupported platform: $OS-$ARCH"
    echo "Supported: macOS (arm64, x86_64), Linux (arm64, x86_64)"
    exit 1
    ;;
esac

echo "Platform: $OS-$ARCH → .NET RID: $RID"

# ── Check dotnet ─────────────────────────────────────────────────────────────
if ! command -v dotnet &>/dev/null; then
  echo "ERROR: dotnet SDK not found."
  echo "Install it from https://dot.net or via your package manager:"
  echo "  macOS:  brew install --cask dotnet-sdk"
  echo "  Ubuntu: apt-get install -y dotnet-sdk-8.0"
  exit 1
fi

DOTNET_VER=$(dotnet --version 2>/dev/null || echo "unknown")
echo "Found dotnet $DOTNET_VER"

# ── Clone ApsimX (shallow) ───────────────────────────────────────────────────
if [ -d "$CLONE_DIR/.git" ]; then
  echo "ApsimX already cloned at $CLONE_DIR — skipping clone."
else
  echo "Cloning ApsimX (shallow) from $APSIMX_REPO ..."
  git clone --depth=1 "$APSIMX_REPO" "$CLONE_DIR"
fi

# ── Build self-contained CLI ─────────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"
echo "Building ApsimX CLI → $OUTPUT_DIR  (this takes ~60 seconds) ..."
dotnet publish \
  "$CLONE_DIR/APSIM.Cli/APSIM.Cli.csproj" \
  --configuration Release \
  --framework "$DOTNET_TARGET" \
  --self-contained true \
  --runtime "$RID" \
  --output "$OUTPUT_DIR" \
  --nologo \
  -p:ErrorOnDuplicatePublishOutputFiles=false \
  2>&1

BINARY="$OUTPUT_DIR/apsim"

if [ ! -f "$BINARY" ]; then
  echo "ERROR: Expected binary not found at $BINARY after build."
  exit 1
fi

chmod +x "$BINARY"
echo ""
echo "✅  ApsimX CLI installed at: $BINARY"
echo ""
echo "Add to your .env (or docker-compose environment):"
echo "   APSIMX_BIN=$BINARY"
