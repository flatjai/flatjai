#!/usr/bin/env bash
# Frozen snapshot: every page, extraction and tool answer FlatJai has cached,
# in one file, so a fresh clone can run the demo and the evaluation with FJ_OFFLINE=1 and no network.
#
#   scripts/snapshot.sh export [file]   -> data/snapshot-YYYY-MM-DD.tar.zst (default)
#   scripts/snapshot.sh import <file>   replaces the cache tables and adds the page blobs
#
# Holds: pages (cleaned text + raw HTML blobs), listings (extractions per model), cache (search,
# geocode, OTP). Not runs, chats or traces.
set -euo pipefail
cd "$(dirname "$0")/.."
TABLES=(pages listings cache)
PG=(docker compose exec -T postgres)

case "${1:-}" in
  export)
    out="${2:-data/snapshot-$(date +%F).tar.zst}"
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    "${PG[@]}" pg_dump -U flatjai -d flatjai --data-only $(printf -- '-t %s ' "${TABLES[@]}") > "$tmp/cache.sql"
    # only the blobs the pages table points to
    "${PG[@]}" psql -U flatjai -d flatjai -tAc "select distinct page_hash from pages" > "$tmp/hashes.txt"
    mkdir -p "$tmp/blobs"
    while read -r h; do
      [ -n "$h" ] || continue
      src="data/blobs/${h:0:2}/${h:2}"
      if [ -f "$src" ]; then mkdir -p "$tmp/data/blobs/${h:0:2}" && cp "$src" "$tmp/$src"; fi
    done < "$tmp/hashes.txt"
    tar -C "$tmp" -cf - cache.sql data | zstd -19 -T0 -q -o "$out" -f
    echo "wrote $out ($(du -h "$out" | cut -f1), $(wc -l < "$tmp/hashes.txt" | tr -d ' ') pages)"
    ;;
  import)
    file="${2:?usage: scripts/snapshot.sh import <file>}"
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    zstd -dc "$file" | tar -C "$tmp" -xf -
    { echo "begin; truncate ${TABLES[*]// /, } cascade;"; cat "$tmp/cache.sql"; echo "commit;"; } \
      | "${PG[@]}" psql -q -U flatjai -d flatjai -v ON_ERROR_STOP=1 > /dev/null
    mkdir -p data/blobs && cp -Rn "$tmp/data/blobs/." data/blobs/ 2>/dev/null || true
    echo "imported $file"
    ;;
  *) echo "usage: $0 export [file] | import <file>"; exit 2 ;;
esac
