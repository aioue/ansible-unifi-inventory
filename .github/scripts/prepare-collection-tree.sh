#!/usr/bin/env bash
# Lay out this collection under ansible_collections/aioue/network for ansible-test.
# Must live outside the main git checkout so ansible-test resolves the correct tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# SANITY_ROOT is only a parent directory. Never delete or replace caller-owned files.
SANITY_PARENT="$(cd "${SANITY_ROOT:-${TMPDIR:-/tmp}}" && pwd -P)"
case "$SANITY_PARENT/" in
  "$ROOT/"*) echo "Sanity trees must be outside the checkout" >&2; exit 1 ;;
esac
SANITY_TREE="$(mktemp -d "$SANITY_PARENT/unifi-sanity.XXXXXX")"

cd "$ROOT"
mkdir -p "$SANITY_TREE/ansible_collections/aioue"
rsync -a \
  --exclude .git \
  --exclude .venv \
  --exclude .pytest_cache \
  --exclude .ruff_cache \
  --exclude .sanity-tree \
  --exclude .sanity-collections \
  --exclude .sanity-tree-path \
  --exclude tests/_ansible_collections \
  --exclude dist \
  --exclude ansible_collections \
  --exclude '*.tar.gz' \
  ./ "$SANITY_TREE/ansible_collections/aioue/network/"

ANSIBLE_COLLECTIONS_PATH="$SANITY_TREE" ansible-galaxy collection install community.library_inventory_filtering_v1 \
  -p "$SANITY_TREE"

git -C "$SANITY_TREE" init -q
git -C "$SANITY_TREE" add -A
git -C "$SANITY_TREE" -c user.email=ci@localhost -c user.name=ci commit -q -m "sanity tree"

printf '%s\n' "$SANITY_TREE" > "$ROOT/.sanity-tree-path"
printf '%s\n' "$SANITY_TREE"
