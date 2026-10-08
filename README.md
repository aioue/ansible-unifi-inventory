[![CI](https://github.com/aioue/ansible-unifi-inventory/actions/workflows/ci.yml/badge.svg)](https://github.com/aioue/ansible-unifi-inventory/actions/workflows/ci.yml)
[![Galaxy](https://img.shields.io/ansible/collection/v/aioue/network)](https://galaxy.ansible.com/ui/repo/published/aioue/network/)
[![Release](https://img.shields.io/github/v/release/aioue/ansible-unifi-inventory)](https://github.com/aioue/ansible-unifi-inventory/releases)

# aioue.network

An Ansible inventory plugin that discovers clients and optional infrastructure devices from a UniFi controller using [aiounifi](https://github.com/Kane610/aiounifi). It reads controller data; Ansible connection credentials and playbooks remain your responsibility.

## Quick start

Install the collection and its Python dependencies in the same environment that runs Ansible. Galaxy installs collection dependencies, but does not install Python libraries.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install 'ansible-core>=2.21.5' 'aiounifi>=97' 'aiohttp>=3.14.4' PyYAML pyotp
ansible-galaxy collection install aioue.network
```

Python 3.14 or newer is required. The current baseline is Ansible Core 2.21.5, aiounifi 97, and aiohttp 3.14.4. See [requirements.txt](requirements.txt) and [meta/runtime.yml](meta/runtime.yml).

Create `prod.unifi.yml`:

```yaml
plugin: aioue.network.unifi
url: https://unifi.example.net
site: default
validate_certs: true
include_devices: false
last_seen_minutes: 30
```

Supply a local controller account through the environment:

```bash
export UNIFI_USERNAME=ansible-inventory
read -r -s -p 'UniFi password: ' UNIFI_PASSWORD
export UNIFI_PASSWORD
ansible-inventory -i prod.unifi.yml --graph
ansible-inventory -i prod.unifi.yml --host nas-server
```

The password prompt above uses Bash. Use your shell's equivalent or a secret manager. Add private inventory files and `.env` files to your own project's `.gitignore`.

Inventory files named `*.unifi.yml` or `*.unifi.yaml` are recognised automatically; `inventory/unifi.yaml` also works. The `plugin` value must be `aioue.network.unifi`.

## Authentication and TLS

Password login is the unattended authentication option, with TOTP when required. `token` / `UNIFI_TOKEN` also accepts an existing UniFi OS `TOKEN` session cookie and takes precedence over password credentials. Session cookies expire; this mode skips login and cannot renew the session. Keep them secret.

Network API keys created under Integrations are a separate credential type and are unsupported by this plugin. Do not pass them as `token`.

Use a local account with access to the Network application. Password authentication accepts `username` and `password`, or `UNIFI_USERNAME` and `UNIFI_PASSWORD`. For accounts requiring TOTP, set `totp_secret` / `UNIFI_TOTP_SECRET` to the Base32 shared secret from authenticator setup.

Connection credentials support Jinja2 lookups, including encrypted files:

```yaml
username: "{{ (lookup('ansible.builtin.unvault', 'secrets.yml') | from_yaml).unifi_username }}"
password: "{{ (lookup('ansible.builtin.unvault', 'secrets.yml') | from_yaml).unifi_password }}"
```

Encrypt `secrets.yml` with Ansible Vault and pass `--ask-vault-pass` or your configured vault password source when loading inventory.

Certificate verification is enabled by default. Trust your controller's CA using the system trust store or `SSL_CERT_FILE`. Use `validate_certs: false` only when you accept an unverified TLS connection. `verify_ssl` remains an alias.

## Options

Inventory YAML values take precedence over environment values. Keep credentials out of YAML when you want environment injection. [inventory/.env.example](inventory/.env.example) lists supported environment names; the plugin does not load `.env` files automatically.

| YAML option | Environment | Default / purpose |
|-------------|-------------|-------------------|
| `url` | `UNIFI_URL` | Required controller base URL |
| `username` | `UNIFI_USERNAME` | Password login account |
| `password` | `UNIFI_PASSWORD` | Password login secret |
| `totp_secret` | `UNIFI_TOTP_SECRET` | Optional TOTP seed |
| `token` | `UNIFI_TOKEN` | Existing UniFi OS `TOKEN` session cookie |
| `site` | `UNIFI_SITE` | `default` |
| `validate_certs` | `UNIFI_VALIDATE_CERTS`, `UNIFI_VERIFY_SSL` | `true` |
| `api_timeout` | - | `30` seconds per request |
| `include_devices` | `UNIFI_INCLUDE_DEVICES` | `false` |
| `exclude_clients` | `UNIFI_EXCLUDE_CLIENTS` | `false`; skips client fetching |
| `exclude_devices` | `UNIFI_EXCLUDE_DEVICES` | `false`; overrides `include_devices` |
| `last_seen_minutes` | `UNIFI_LAST_SEEN_MINUTES` | `30`; client recency limit |
| `hostname` | `UNIFI_HOSTNAME` | `name` or `mac` |
| `hostname_collision` | `UNIFI_HOSTNAME_COLLISION` | `disambiguate` or `fail` |
| `strict_records` | - | `true`; fail on malformed controller records |
| `allow_historical_addresses` | - | `true`; allow last-known / reserved client IPs |

Run `ansible-doc -t inventory aioue.network.unifi` for the full option reference.

Friendly names become inventory hostnames with surrounding whitespace trimmed and characters outside letters, digits, underscores, dots, and hyphens replaced by underscores. The original is retained in `unifi_name`. Missing names fall back to manufacturer and MAC information. `hostname: mac` uses addresses such as `aa-bb-cc-dd-ee-ff` and keeps hostnames stable when friendly names change.

Duplicate hostnames are renamed with a MAC suffix, with an Ansible warning for each renamed host. This also applies to names that collide after sanitisation, such as `Living Room` and `Living_Room`. Unique names stay unchanged. Set `hostname_collision: fail` to stop inventory loading instead. Collisions with existing inventory names are checked when combining sources.

Malformed client/device records fail inventory loading by default. Set `strict_records: false` to skip them with warnings. This option is independent of Ansible's `strict` setting for composed expressions.

IPv4 is preferred, with usable IPv6 as fallback. Unscoped link-local IPv6 cannot be used as a connection address. By default, clients without a current address can use `last_ip` or `fixed_ip`; set `allow_historical_addresses: false` to restrict inventory to current addresses.

## Groups and host variables

Clients join `unifi_clients` and either `unifi_wired_clients` or `unifi_wireless_clients`. Available network metadata adds `ssid_<name>`, `network_<name>`, `vlan_<id>`, and `vlan_<name>` groups. Group names use lowercase letters, digits, and underscores.

With `include_devices: true`, infrastructure joins `unifi_devices` and its type group, such as `unifi_uap` or `unifi_usw`. State and capabilities can add `device_state_connected`, `unifi_upgradable`, `unifi_overheating`, or `unifi_poe_powered`.

Typical client variables:

```json
{
  "ansible_host": "192.168.30.13",
  "mac": "aa:bb:cc:dd:ee:ff",
  "unifi_name": "Kitchen Echo",
  "ipv4": "192.168.30.13",
  "is_wired": false,
  "site": "default",
  "ssid": "home.iot",
  "network": "IoT",
  "vlan": 30,
  "vlan_name": "IoT",
  "last_seen_unix": 1784745212,
  "last_seen_iso": "2026-07-22T18:33:32Z"
}
```

Clients can also expose IPv6 addresses, upstream AP/switch MACs, switch port, reservation address, guest/blocked status, lifecycle timestamps, and manufacturer information. Devices expose model, type, firmware, adoption/state, uptime, available firmware updates, uplink, PoE port, temperature, outlet, and system-stat information when reported. Optional variables are omitted when unavailable. Inspect a host with `ansible-inventory --host HOST` before using optional fields in expressions.

## Filtering and composed groups

Standard Ansible `compose`, `groups`, and `keyed_groups` options are supported, along with include/exclude `filters`:

```yaml
plugin: aioue.network.unifi
url: https://unifi.example.net
include_devices: true

# A matching include keeps a host; the first matching rule wins.
# Hosts with no matching rule are included.
filters:
  - exclude: ssid | default('') == 'Guest'

compose:
  ansible_user: "'automation'"

keyed_groups:
  - key: network
    prefix: network
    separator: "_"
```

Use `strict: true` to fail when a composed expression cannot be evaluated. This is Ansible's constructed-inventory option.

## Caching

Use Ansible inventory caching to reduce controller requests:

```yaml
cache: true
cache_plugin: ansible.builtin.jsonfile
cache_connection: .cache/unifi_inventory
cache_timeout: 30
```

The cache contains host addresses and network metadata. Keep it private. Configuration changes affecting fetched inventory invalidate existing entries; expired entries refresh automatically. To inspect current controller data, temporarily use `cache: false`.

The former `cache_ttl` / `cache_path` options and `UNIFI_CACHE_TTL` / `UNIFI_CACHE_PATH` variables were removed in 1.1.0. Use the standard Ansible options above.

## Usage

```bash
ansible-inventory -i prod.unifi.yml --list
ansible-inventory -i prod.unifi.yml --graph unifi_wired_clients
ansible-playbook -i prod.unifi.yml site.yml --limit unifi_clients
ansible-playbook -i static_hosts.yml -i prod.unifi.yml site.yml
```

Use separate inventory sources for different controllers or sites. Ensure connection credentials are available for each source.

## Troubleshooting

- Authentication failures: check the account, permissions, credential mode, and TOTP seed. Inventory caching reduces repeated password logins and controller rate limits.
- Certificate failures: trust the controller CA and use a URL matching its certificate.
- Empty inventory: check `site`, `last_seen_minutes`, exclusion switches, and filters. Devices require `include_devices: true`.
- Stale data: reduce `cache_timeout` or set `cache: false` for a fresh read.
- Timeouts: check controller reachability and `api_timeout`.

Include version information and sanitised errors when [reporting a bug](CONTRIBUTING.md#reporting-bugs). Follow [SECURITY.md](SECURITY.md) for vulnerabilities.

## Upgrading

```bash
ansible-galaxy collection install aioue.network --upgrade
python -m pip install --upgrade aiounifi aiohttp PyYAML pyotp
```

If upgrading a copied standalone plugin, install the collection, change the inventory directive to `plugin: aioue.network.unifi`, and remove custom discovery settings for the old plugin. Review [CHANGELOG.md](CHANGELOG.md) for release-specific changes.

## Development and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks, and [MAINTAINERS.md](MAINTAINERS.md) for releases.

[GPL-3.0-or-later](LICENSE). Copyright (c) 2025 Tom Paine.
