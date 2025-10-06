#!/usr/bin/env bash
set -Eeuo pipefail

# transmission_add.sh — add magnet links to a local Transmission daemon
# Usage examples:
#   scripts/transmission_add.sh "magnet:?xt=urn:btih:..."
#   scripts/transmission_add.sh -w "$HOME/Downloads/Movies" "magnet:?xt=urn:btih:..."
#   scripts/transmission_add.sh -f data/selected_magnets.txt
#   scripts/transmission_add.sh -c data/low_quality_movies.csv  # uses 'magnet' column
#   scripts/transmission_add.sh -n user:pass "magnet:?xt=urn:btih:..." "magnet:?xt=urn:btih:..."

RPC_HOST=${RPC_HOST:-localhost}
RPC_PORT=${RPC_PORT:-9091}
RPC_AUTH=""
DOWNLOAD_DIR="${HOME}/Downloads"
CONF_DIR="${CONF_DIR:-${HOME}/.config/transmission-daemon}"
MAGNET_FILE=""
CSV_FILE=""

usage() {
  echo "Usage: $0 [-H host] [-p port] [-n user:pass] [-w download_dir] [-f magnets.txt] [-c magnets.csv] [magnet ...]" >&2
}

while getopts ":H:p:n:w:f:c:h" opt; do
  case $opt in
    H) RPC_HOST="$OPTARG" ;;
    p) RPC_PORT="$OPTARG" ;;
    n) RPC_AUTH="$OPTARG" ;;
    w) DOWNLOAD_DIR="$OPTARG" ;;
    f) MAGNET_FILE="$OPTARG" ;;
    c) CSV_FILE="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) echo "Missing argument for -$OPTARG" >&2; usage; exit 2 ;;
    \?) echo "Unknown option -$OPTARG" >&2; usage; exit 2 ;;
  esac
done
shift $((OPTIND-1))

# Build transmission-remote base args
TR=(transmission-remote "$RPC_HOST":"$RPC_PORT")
if [ -n "$RPC_AUTH" ]; then TR+=( -n "$RPC_AUTH" ); fi
if [ -n "$DOWNLOAD_DIR" ]; then TR+=( -w "$DOWNLOAD_DIR" ); fi

# Ensure daemon is running (start locally if RPC not reachable)
if ! "${TR[@]}" -si >/dev/null 2>&1; then
  echo "[transmission] RPC not reachable; starting local transmission-daemon..."
  mkdir -p "$CONF_DIR" "$DOWNLOAD_DIR"
  # Start daemon in background with chosen config and download dir
  transmission-daemon -g "$CONF_DIR" -w "$DOWNLOAD_DIR" >/dev/null 2>&1 || true
  # Wait for RPC to respond
  for i in {1..20}; do
    if "${TR[@]}" -si >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
  if ! "${TR[@]}" -si >/dev/null 2>&1; then
    echo "[transmission] ERROR: Unable to contact RPC at ${RPC_HOST}:${RPC_PORT}" >&2
    exit 1
  fi
fi

# Collect magnet links from CLI, file, or CSV
MAGNETS=()
for m in "$@"; do
  if [[ "$m" == magnet:* ]]; then MAGNETS+=("$m"); fi
done

if [ -n "$MAGNET_FILE" ]; then
  while IFS= read -r line; do
    [[ -n "$line" && "$line" == magnet:* ]] && MAGNETS+=("$line")
  done < "$MAGNET_FILE"
fi

if [ -n "$CSV_FILE" ]; then
  # Extract 'magnet' column robustly via Python csv module (portable: avoid mapfile)
  while IFS= read -r m; do
    [ -n "$m" ] && MAGNETS+=("$m")
  done < <(python3 - "$CSV_FILE" <<'PY'
import csv, sys
path=sys.argv[1]
with open(path, newline='', encoding='utf-8') as f:
  r = csv.DictReader(f)
  if not r.fieldnames:
    raise SystemExit(0)
  col = 'magnet' if 'magnet' in r.fieldnames else None
  if not col:
    for c in ('magnets','Magnet','MAGNET'):
      if c in r.fieldnames:
        col = c
        break
  if not col:
    raise SystemExit(0)
  for row in r:
    val = (row.get(col) or '').strip()
    if val.startswith('magnet:'):
      parts = [p.strip() for p in val.split('|')]
      for p in parts:
        if p.startswith('magnet:'):
          print(p)
PY
  )
fi

if [ ${#MAGNETS[@]} -eq 0 ]; then
  echo "[transmission] No magnets provided." >&2
  usage; exit 2
fi

echo "[transmission] Adding ${#MAGNETS[@]} magnet(s) to ${RPC_HOST}:${RPC_PORT} -> $DOWNLOAD_DIR"
for m in "${MAGNETS[@]}"; do
  echo "  + $m"
  "${TR[@]}" -a "$m"
done

echo "[transmission] Current torrents:"
"${TR[@]}" -l || true
