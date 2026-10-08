"""Reject build debris and unsafe paths before installing a collection artifact."""

import sys
import tarfile
from pathlib import PurePosixPath

ALLOWED_ROOTS = {
    "MANIFEST.json",
    "FILES.json",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "MAINTAINERS.md",
    "SECURITY.md",
    "LICENSE",
    "requirements.txt",
    "plugins",
    "meta",
    "docs",
    "inventory",
    "tests",
}
REQUIRED = {"MANIFEST.json", "FILES.json", "plugins/inventory/unifi.py", "meta/runtime.yml", "README.md"}


def main() -> None:
    with tarfile.open(sys.argv[1], "r:gz") as archive:
        names = []
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if not path.parts:
                continue
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise SystemExit(f"Unsafe artifact member: {member.name}")
            if path.parts[0] not in ALLOWED_ROOTS or any(
                (part.startswith(".") and str(path) != "inventory/.env.example")
                or part in {"ansible_collections", "_ansible_collections", "__pycache__"}
                for part in path.parts
            ):
                raise SystemExit(f"Unexpected artifact member: {member.name}")
            names.append(str(path))
        if len(names) != len(set(names)):
            raise SystemExit("Duplicate artifact members")
        missing = REQUIRED - set(names)
        if missing:
            raise SystemExit(f"Required artifact files missing: {sorted(missing)}")
    print(f"Validated {sys.argv[1]} ({len(names)} members)")


if __name__ == "__main__":
    main()
