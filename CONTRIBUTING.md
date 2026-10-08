# Contributing

Pull requests are welcome. Keep changes focused and include a reproduction for bug fixes.

## Development setup

Use Python 3.14 or newer:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
bash .github/scripts/install-ci-dependencies.sh latest
```

The dependency installer uses `requirements-dev.txt` and installs the collection dependency for source tests. Use `minimum` instead of `latest` to test declared dependency floors. No live controller is needed for the automated suite.

## Checks

```bash
ruff check .
ruff format --check .
pytest tests/unit tests/integration -q
mkdir -p dist
ansible-galaxy collection build --output-path dist/
bash .github/scripts/test-artifact.sh dist/aioue-network-*.tar.gz
bash .github/scripts/prepare-collection-tree.sh
SANITY_TREE="$(cat .sanity-tree-path)"
cd "$SANITY_TREE/ansible_collections/aioue/network"
ANSIBLE_COLLECTIONS_PATH="$SANITY_TREE" ansible-test sanity --local --python 3.14 --color no
```

Use a fresh output directory for each build. The artifact script checks package contents, installs the archive into a temporary collection path, and runs the suite against the installed plugin. Integration tests use a fake HTTP controller with real Ansible and aiounifi.

The sanity helper creates a fresh temporary child directory. `SANITY_ROOT`, if supplied, selects its parent; it never deletes the supplied directory. Temporary test trees remain available for inspection.

CI runs Ruff, source and installed-artifact tests, and Ansible sanity with minimum and latest dependency resolutions. Add tests for changed behaviour, update the plugin's `DOCUMENTATION` block for options, and record user-visible changes in `CHANGELOG.md`.

Do not commit secrets, live inventory files, or `.env` files. Collection content uses GPL-3.0-or-later.

## Reporting bugs

Include the collection version (`ansible-galaxy collection list aioue.network`), Python/Ansible versions, dependency versions (`python -m pip show aiounifi aiohttp`), controller model/firmware, a sanitised inventory snippet, and the error from `ansible-inventory -i your.unifi.yml --graph -vvv`. Redact credentials, controller identifiers, and private addresses. Follow [SECURITY.md](SECURITY.md) for vulnerabilities.
