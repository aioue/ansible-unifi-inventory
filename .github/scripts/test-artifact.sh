#!/usr/bin/env bash
# Exercise the same archive that will be published, including Ansible's plugin loader.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "$#" -ne 1 ]; then
  echo "Usage: test-artifact.sh path/to/collection.tar.gz" >&2
  exit 1
fi
ARTIFACT="$1"
python "$ROOT/.github/scripts/check-artifact.py" "$ARTIFACT"
COLLECTIONS="$(mktemp -d "${TMPDIR:-/tmp}/unifi-artifact.XXXXXX")"
export ANSIBLE_COLLECTIONS_PATH="$COLLECTIONS"
ansible-galaxy collection install "$ARTIFACT" -p "$COLLECTIONS"
export UNIFI_TEST_COLLECTIONS_PATH="$COLLECTIONS"
ansible-doc -t inventory aioue.network.unifi > /dev/null
cd "$ROOT"
pytest tests/unit tests/integration -q
