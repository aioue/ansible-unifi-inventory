#!/usr/bin/env bash
# Test declared floors as well as pip's latest compatible resolution.
set -euo pipefail
MODE="${1:-latest}"
case "$MODE" in
  minimum)
    CONSTRAINTS="$(mktemp "${TMPDIR:-/tmp}/unifi-constraints.XXXXXX")"
    sed '/^[A-Za-z]/!d; s/>=/==/' requirements.txt requirements-dev.txt tests/unit/requirements.txt > "$CONSTRAINTS"
    python -m pip install -r requirements-dev.txt -c "$CONSTRAINTS"
    ;;
  latest) python -m pip install -r requirements-dev.txt ;;
  *) echo "Unknown dependency mode: $MODE" >&2; exit 1 ;;
esac
ANSIBLE_COLLECTIONS_PATH="$PWD/tests/_ansible_collections" \
  ansible-galaxy collection install community.library_inventory_filtering_v1 -p tests/_ansible_collections
