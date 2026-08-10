#!/usr/bin/env bash
# Write GitHub release notes for a tag from CHANGELOG.md.
#
# Usage: extract-changelog.sh <version> [changelog-file]
#   version: 1.2.0 or v1.2.0
set -euo pipefail

VERSION="${1#v}"
CHANGELOG="${2:-CHANGELOG.md}"
TAG="v${VERSION}"
REPO="${GITHUB_REPOSITORY:-aioue/ansible-unifi-inventory}"

if [[ ! -f "$CHANGELOG" ]]; then
  echo "Missing ${CHANGELOG}" >&2
  exit 1
fi

section="$(
  awk -v ver="$VERSION" '
    /^## / {
      if (found) exit
      if ($2 == ver) {
        found = 1
        next
      }
    }
    found { print }
  ' "$CHANGELOG"
)"

if [[ -z "${section//[$'\t\r\n ']/}" ]]; then
  echo "No CHANGELOG.md section for version ${VERSION}" >&2
  exit 1
fi

printf '%s\n' "$section"

echo
if prev="$(git describe --tags --abbrev=0 "${TAG}^" 2>/dev/null)"; then
  echo "**Full Changelog**: https://github.com/${REPO}/compare/${prev}...${TAG}"
fi
