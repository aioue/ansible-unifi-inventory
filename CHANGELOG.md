# Changelog

## 1.1.6 (2026-07-22)

**Fixes:**

- Serialize aiounifi v92 `StrEnum` values (e.g. `DeviceType`) before Ansible inventory storage
- Map aiounifi `AuthenticationRateLimitError` when available (v91+)

**Dependencies:**

- Require aiounifi v91+ and `pyotp` (SSO 2FA and rate-limit support; tested with v92)

**Documentation:**

- Refresh README inventory examples from a live run with aiounifi v92

## 1.1.5 (2026-07-22)

**Improvements (closes parts of #4):**

- Client host variables: `fixed_ip`, `unifi_hostname`, `device_name`, lifecycle timestamps, `switch_depth`, `wired_rate_mbps`, `powersave_enabled`
- Device host variables: thermal fields, `last_seen`, LED state, `outlets` summary
- Trim `uplink` to a compact summary (drops rx/tx counters)
- Device groups: `device_state_*`, `unifi_upgradable`, `unifi_overheating`, `unifi_poe_powered`

**Tests:**

- Cover optional hostvar helpers, handler iteration, stale client filtering, thermal/outlet device fields, and status groups

## 1.1.4 (2026-07-22)

**Fixes:**

- Install `community.library_inventory_filtering_v1` into the test collections path in CI/release workflows

## 1.1.3 (2026-07-22)

**Improvements:**

- Expose additional device host variables from aiounifi: `device_id`, `upgradable`, `overheating`, `uptime`, `uplink`, `client_count`, system stats, and `poe_ports` (per-port PoE state on switches)
- Expose client `is_guest`, `blocked`, and `firmware_version` when reported by UniFi
- Add optional `totp_secret` inventory option (forward-compatible with [aiounifi PR #990](https://github.com/Kane610/aiounifi/pull/990) automated 2FA login)

**Fixes:**

- Install filtering collection into the test collections path so unit tests do not depend on `~/.ansible/collections`

**Tests:**

- Refresh README inventory examples from a live run (graph, PoE ports, device stats)

## 1.1.2 (2026-07-22)

**Fixes:**

- Serialize UniFi device enums (e.g. `DeviceState`) for Ansible inventory host variables when `include_devices: true`
- Sanitize all host variables before compose/keyed_groups processing
- Surface clearer errors when UniFi login rate limits are hit (429 / `AUTHENTICATION_FAILED_LIMIT_REACHED`)

**Documentation:**

- Refresh README inventory examples from a live run (clients, VLAN/SSID groups, and UniFi devices)

## 1.1.1 (2026-07-22)

**Fixes:**

- Inline `filters` plugin documentation so Galaxy import no longer fails on the external doc fragment
- Upgrade GitHub Actions to Node 24 runtimes (`checkout@v5`, `setup-python@v6`, `action-gh-release@v3`)
- Set `ANSIBLE_COLLECTIONS_PATH` during release prep to silence ansible-galaxy install warnings

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
