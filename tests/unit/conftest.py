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
    # Artifact tests must import the installed build rather than the checkout.
    installed_path = os.environ.get("UNIFI_TEST_COLLECTIONS_PATH")
    if installed_path:
        installed_root = Path(installed_path).resolve()
        if not (installed_root / "ansible_collections" / "aioue" / "network").is_dir():
            raise RuntimeError(f"Collection is not installed under {installed_root}")
        _add_collections_path(installed_root)
        os.environ["ANSIBLE_COLLECTIONS_PATH"] = str(installed_root)
        return

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.is_symlink():
        try:
            if TARGET.resolve() == COLLECTION_ROOT.resolve():
                _add_collections_path(FAKE_COLLECTIONS)
                os.environ["ANSIBLE_COLLECTIONS_PATH"] = str(FAKE_COLLECTIONS)
                return
        except OSError:
            pass
        TARGET.unlink()
    if TARGET.exists():
        raise RuntimeError(f"Expected symlink at {TARGET}, found a real directory")
    TARGET.symlink_to(COLLECTION_ROOT, target_is_directory=True)

    # Only expose the workspace collection. Do not add ~/.ansible/collections to
    # sys.path: ansible_collections is a namespace package and the installed
    # release would shadow local plugin changes during development.
    _add_collections_path(FAKE_COLLECTIONS)
    os.environ["ANSIBLE_COLLECTIONS_PATH"] = str(FAKE_COLLECTIONS)


_ensure_collection_path()

# Ansible must install its namespace loader before tests import a collection directly.
from ansible.plugins.loader import init_plugin_loader

init_plugin_loader()
