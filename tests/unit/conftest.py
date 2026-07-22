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
    if TARGET.exists() and not TARGET.is_symlink():
        raise RuntimeError(f"Expected symlink at {TARGET}, found a real directory")
    if not TARGET.exists():
        TARGET.symlink_to(COLLECTION_ROOT, target_is_directory=True)

    # Only expose the workspace collection. Do not add ~/.ansible/collections to
    # sys.path: ansible_collections is a namespace package and the installed
    # release would shadow local plugin changes during development.
    _add_collections_path(FAKE_COLLECTIONS)
    os.environ["ANSIBLE_COLLECTIONS_PATH"] = str(FAKE_COLLECTIONS)


_ensure_collection_path()
