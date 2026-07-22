# Changelog

## 1.1.0 (2026-07-22)

**Breaking changes:**

- Removed `cache_ttl` and `cache_path` plugin options; use standard Ansible inventory caching (`cache`, `cache_plugin`, `cache_timeout` in `ansible.cfg` or inventory source config)

**Improvements:**

- Added standard Ansible inventory caching via the `inventory_cache` documentation fragment
- Added `hostname` option (`name` or `mac`); friendly names remain the default, with `mac` for stable keys
- Added Constructable inventory support: `keyed_groups`, `compose`, `groups`, and `filters` (via `community.library_inventory_filtering_v1`)
- Inventory files named `*.unifi.yml` or `*.unifi.yaml` are auto-detected by the plugin
- Declared dependency on `community.library_inventory_filtering_v1` (`>=1.0.0`)
- Added `meta/execution-environment.yml` for Ansible Execution Environment builds
- Pinned `aiounifi>=82.0.0` in `requirements.txt`
- Async controller fetch runs in a dedicated thread to avoid event-loop conflicts
- Avoids private `aiounifi` handler APIs where possible
- Connection options (`url`, `username`, `password`, `token`) support Jinja2 templating for vault lookups and variables in inventory files
- Added light unit tests and CI workflow (pytest)

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
