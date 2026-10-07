#!/usr/bin/env bash
# Wraps the PyInstaller onedir build (dist/RVTripVisualizer, built first via
# `pyinstaller packaging/pyinstaller.spec` from the repo root) into a
# self-contained AppImage. Usage: packaging/linux/build_appimage.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST="$ROOT/dist/RVTripVisualizer"
APPDIR="$ROOT/dist/AppDir"
OUT="$ROOT/dist/RVTripVisualizer-x86_64.AppImage"

if [ ! -d "$DIST" ]; then
  echo "Expected a PyInstaller build at $DIST - run:"
  echo "  pyinstaller packaging/pyinstaller.spec"
  exit 1
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -r "$DIST"/* "$APPDIR/usr/bin/"
cp "$ROOT/packaging/icons/icon_256.png" "$APPDIR/rv-trip-visualizer.png"

cat > "$APPDIR/rv-trip-visualizer.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=RV Trip Visualizer
Exec=RVTripVisualizer
Icon=rv-trip-visualizer
Categories=Utility;
Terminal=false
EOF

cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/RVTripVisualizer" "$@"
EOF
chmod +x "$APPDIR/AppRun"

APPIMAGETOOL="$ROOT/dist/appimagetool.AppImage"
if [ ! -x "$APPIMAGETOOL" ]; then
  echo "Downloading appimagetool..."
  curl -L -o "$APPIMAGETOOL" \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$APPIMAGETOOL"
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUT"
echo "Wrote $OUT"
