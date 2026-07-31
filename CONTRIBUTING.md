# Contributing

Pull requests are welcome. If you are unsure about an approach, open an issue first.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r tests/unit/requirements.txt
pip install ansible-core pytest ruff pre-commit
ansible-galaxy collection install community.library_inventory_filtering_v1 \
  -p tests/_ansible_collections --force
pre-commit install
```

## Checks

Run these before opening a PR:

```bash
pre-commit run --all-files   # ruff lint + format
pytest tests/unit/ -q
./.github/scripts/prepare-collection-tree.sh
SANITY_ROOT="$(cat .sanity-tree-path)"
cd "$SANITY_ROOT/ansible_collections/aioue/network"
ANSIBLE_COLLECTIONS_PATH="$SANITY_ROOT" ansible-test sanity --local --color no
```

CI runs the same checks on every push and pull request to `main`.

## Code style

- [Ruff](https://docs.astral.sh/ruff/) for linting and formatting (`ruff.toml`).
- GPL-3.0-or-later for collection content.
- Inventory plugin docs use Ansible markup in the plugin `DOCUMENTATION` block.

## Pull requests

- Keep changes focused; one logical change per PR when possible.
- Add or update unit tests in `tests/unit/` (no live UniFi controller required).
- Update `CHANGELOG.md` under an `[Unreleased]` or version heading for user-visible changes.
- Do not commit secrets, live inventory files, or `.env` files.

## Reporting bugs

Include:

- Collection version (`ansible-galaxy collection list aioue.network`)
- aiounifi and aiohttp versions (`pip show aiounifi aiohttp`)
- UniFi OS / gateway model and firmware (approximate is fine)
- Sanitized inventory snippet (redact tokens and passwords)
- Full error output from `ansible-inventory -i your.unifi.yaml --graph -vvv`
