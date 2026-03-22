# Changelog

## 1.0.0 (2026-03-22)

**Breaking changes:**

- Converted to Ansible collection `aioue.network` - install via `ansible-galaxy collection install`
- Plugin FQCN is now `aioue.network.unifi` (was `unifi`)
- Inventory files must use `plugin: aioue.network.unifi`
- Minimum Python version raised to 3.12 (was 3.11)

**Improvements:**

- Collection structure (`galaxy.yml`, `meta/runtime.yml`) for standard installation
- `verify_file()` now uses YAML parsing instead of fragile string matching
- `aiounifi` dependency changed from exact pin to `>=77` floor
- Improved README with collection install instructions, migration guide, and auth docs
- `ansible.cfg` moved to `ansible.cfg.example` (not needed when installed as a collection)

**Contributors:**

- Lenny Shirley ([@lennysh](https://github.com/lennysh)) - initial collection conversion
