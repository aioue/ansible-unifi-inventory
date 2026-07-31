#!/usr/bin/env bash
# Lay out this collection under ansible_collections/aioue/network for ansible-test.
# Must live outside the main git checkout so ansible-test resolves the correct tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SANITY_ROOT="${SANITY_ROOT:-$(mktemp -d)}"

cd "$ROOT"

rm -rf "$SANITY_ROOT"
mkdir -p "$SANITY_ROOT/ansible_collections/aioue"
rsync -a \
  --exclude .git \
  --exclude .venv \
  --exclude .pytest_cache \
  --exclude .ruff_cache \
  --exclude .sanity-tree \
  --exclude .sanity-collections \
  --exclude tests/_ansible_collections \
  --exclude dist \
  --exclude ansible_collections \
  --exclude '*.tar.gz' \
  ./ "$SANITY_ROOT/ansible_collections/aioue/network/"

ansible-galaxy collection install community.library_inventory_filtering_v1 \
  -p "$SANITY_ROOT" --force

git -C "$SANITY_ROOT" init -q
git -C "$SANITY_ROOT" add -A
git -C "$SANITY_ROOT" -c user.email=ci@localhost -c user.name=ci commit -q -m "sanity tree"

printf '%s' "$SANITY_ROOT" > "$ROOT/.sanity-tree-path"
