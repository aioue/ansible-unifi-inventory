"""Make the local aioue.network collection importable for unit tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

COLLECTION_ROOT = Path(__file__).resolve().parents[2]
FAKE_COLLECTIONS = COLLECTION_ROOT / "tests" / "_ansible_collections"
TARGET = FAKE_COLLECTIONS / "ansible_collections" / "aioue" / "network"


def _add_collections_path(path: Path) -> None:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _ensure_collection_path() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if not TARGET.exists():
        TARGET.symlink_to(COLLECTION_ROOT, target_is_directory=True)

    paths = [
        FAKE_COLLECTIONS,
        Path.home() / ".ansible" / "collections",
    ]

    env_paths = []
    for path in paths:
        _add_collections_path(path)
        env_paths.append(str(path))

    existing = os.environ.get("ANSIBLE_COLLECTIONS_PATH", "")
    merged = os.pathsep.join(env_paths + ([existing] if existing else []))
    os.environ["ANSIBLE_COLLECTIONS_PATH"] = merged


_ensure_collection_path()
