#!/usr/bin/env bash
set -euo pipefail

ESHOP_DIR="${1:?Usage: generate-eshop-map.sh <eshop-dir>}"
OUT="${2:-eshop-map.md}"

cat > "$OUT" <<'HEADER'
# eShop Service Map
| Service | Path | Key Entry Points | Description |
|---------|------|-------------------|-------------|
HEADER

for svc_dir in "$ESHOP_DIR"/src/*/; do
  [ -d "$svc_dir" ] || continue
  svc_name=$(basename "$svc_dir")
  rel_path="src/${svc_name}/"

  entries=""
  for f in Program.cs Startup.cs; do
    [ -f "${svc_dir}${f}" ] && entries="${entries:+${entries}, }${f}"
  done

  for f in $(find "$svc_dir" -maxdepth 2 -name "*Controller.cs" -o -name "*Service.cs" 2>/dev/null | head -3); do
    fname=$(basename "$f")
    entries="${entries:+${entries}, }${fname}"
  done

  [ -z "$entries" ] && entries="Program.cs"

  echo "| ${svc_name} | ${rel_path} | ${entries} | ${svc_name} service |" >> "$OUT"
done

echo "Generated $OUT with $(wc -l < "$OUT") lines"
