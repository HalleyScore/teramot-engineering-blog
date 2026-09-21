#!/usr/bin/env bash
# Generate the raster icon set in static/ from static/brand/teramot-favicon.svg.
#
# Why this exists: Blowfish ships its own blowfish-branded favicon.ico,
# apple-touch-icon.png, android-chrome-*.png and site.webmanifest in the
# theme's static/. Hugo publishes those to the site root, so overriding only
# the <link> tags in layouts/partials/favicons.html left the theme's icons
# being served at the well-known paths -- which is what Slack, iMessage and
# other unfurlers fall back to, because none of them render an SVG favicon.
# Files here shadow the theme's, because project static/ wins over theme
# static/ at the same path.
#
# Re-run after changing the brand mark:
#
#     ./scripts/gen-favicons.sh
#
# Requires: rsvg-convert (librsvg), magick (ImageMagick 7).

set -euo pipefail

cd "$(dirname "$0")/.."

SRC="static/brand/teramot-favicon.svg"
OUT="static"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for tool in rsvg-convert magick; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
done
[ -f "$SRC" ] || { echo "missing source mark: $SRC" >&2; exit 1; }

# The mark is 212x195, so it never fills a square canvas. Render it wide at
# high resolution once, then letterbox that master into each square size.
rsvg-convert -w 2048 -a -o "$WORK/mark.png" "$SRC"

# square <out> <size> <mark-fraction> <background>
# mark-fraction: how much of the canvas width the mark spans. Small icons need
# to be tighter or the mark turns to mush; app icons need room because the OS
# rounds the corners and crops into them.
square() {
  local out=$1 size=$2 fraction=$3 background=$4
  local mark_width
  mark_width=$(awk "BEGIN{printf \"%d\", $size * $fraction}")
  magick "$WORK/mark.png" \
    -resize "${mark_width}x" \
    -background "$background" -gravity center \
    -extent "${size}x${size}" \
    -strip \
    "$out"
}

# Browser tab icons: transparent, so they sit on whatever the tab background
# is, matching how the SVG behaves.
square "$WORK/favicon-16.png"  16 0.92 none
square "$WORK/favicon-32.png"  32 0.92 none
square "$WORK/favicon-48.png"  48 0.92 none
cp "$WORK/favicon-16.png" "$OUT/favicon-16x16.png"
cp "$WORK/favicon-32.png" "$OUT/favicon-32x32.png"
magick "$WORK/favicon-16.png" "$WORK/favicon-32.png" "$WORK/favicon-48.png" "$OUT/favicon.ico"

# App and unfurl icons: opaque. iOS composites a transparent apple-touch-icon
# onto black, and the mark's own blues would disappear into it.
square "$OUT/apple-touch-icon.png"        180 0.76 white
square "$OUT/android-chrome-192x192.png"  192 0.76 white
square "$OUT/android-chrome-512x512.png"  512 0.76 white

printf '%-32s %s\n' "generated:" "from $SRC"
for f in favicon.ico favicon-16x16.png favicon-32x32.png apple-touch-icon.png \
         android-chrome-192x192.png android-chrome-512x512.png; do
  printf '  %-30s %s\n' "$f" "$(magick identify -format '%wx%h %b' "$OUT/$f" 2>/dev/null || echo '?')"
done
