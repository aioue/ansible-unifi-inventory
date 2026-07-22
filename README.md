# aioue.network

[![CI](https://github.com/aioue/ansible-unifi-inventory/actions/workflows/ci.yml/badge.svg)](https://github.com/aioue/ansible-unifi-inventory/actions/workflows/ci.yml)
[![Galaxy](https://img.shields.io/ansible/collection/v/aioue/network)](https://galaxy.ansible.com/ui/repo/published/aioue/network/)
[![Release](https://img.shields.io/github/v/release/aioue/ansible-unifi-inventory)](https://github.com/aioue/ansible-unifi-inventory/releases)
[![License](https://img.shields.io/github/license/aioue/ansible-unifi-inventory)](LICENSE)

Dynamic inventory plugin for Ansible that discovers hosts from a UniFi OS controller (UDM, UCG, etc.). Built on top of [aiounifi](https://github.com/Kane610/aiounifi).

```shell
$ ansible-inventory -i inventory/unifi.yaml all --graph
@all:
  |--@ungrouped:
  |--@unifi_clients:
  |  |--Kitchen_Echo
  |  |--nas-server
  |  |--Study_Proxmox
  |  |--phone
  |  |--homeassistant
  |  |--Study_Mac_Mini_Ethernet
  |--@unifi_wireless_clients:
  |  |--Kitchen_Echo
  |  |--phone
  |--@unifi_wired_clients:
  |  |--nas-server
  |  |--Study_Proxmox
  |  |--homeassistant
  |  |--Study_Mac_Mini_Ethernet
  |--@network_default:
  |  |--nas-server
  |  |--Study_Proxmox
  |  |--homeassistant
  |  |--Study_Mac_Mini_Ethernet
  |  |--phone
  |--@network_iot:
  |  |--Kitchen_Echo
  |--@vlan_30:
  |  |--Kitchen_Echo
  |--@vlan_iot:
  |  |--Kitchen_Echo
  |--@ssid_home_iot:
  |  |--Kitchen_Echo
  |--@ssid_home_wifi:
  |  |--phone
  |--@unifi_devices:
  |  |--U6_Pro
  |  |--U6_Mesh
  |  |--USW_Flex
  |  |--USW_Ultra
  |  |--Dream_Machine
  |--@unifi_uap:
  |  |--U6_Pro
  |  |--U6_Mesh
  |--@unifi_usw:
  |  |--USW_Flex
  |  |--USW_Ultra
  |--@unifi_udm:
  |  |--Dream_Machine
```

Example host variables (`include_devices: true` in the inventory file; output sanitized from a live run):

```shell
$ ansible-inventory -i inventory/unifi.yaml --host Kitchen_Echo
{
  "ansible_host": "192.168.30.13",
  "ip": "192.168.30.13",
  "mac": "48:78:5e:fa:7c:e1",
  "is_wired": false,
  "ssid": "home.iot",
  "vlan": 30,
  "vlan_name": "IoT",
  "network": "IoT",
  "oui": "Amazon Technologies Inc.",
  "last_seen_iso": "2026-07-22T18:17:02Z",
  "unifi_name": "Kitchen Echo"
}

$ ansible-inventory -i inventory/unifi.yaml --host nas-server
{
  "ansible_host": "192.168.1.148",
  "ip": "192.168.1.148",
  "mac": "bc:24:11:af:77:dd",
  "is_wired": true,
  "network": "Default",
  "oui": "Example Vendor Inc.",
  "last_seen_iso": "2026-07-22T18:17:14Z",
  "unifi_name": "nas-server"
}

$ ansible-inventory -i inventory/unifi.yaml --host U6_Pro
{
  "ansible_host": "192.168.1.252",
  "ip": "192.168.1.252",
  "mac": "ac:8b:a9:43:b5:cd",
  "model": "UAP6MP",
  "type": "uap",
  "firmware_version": "6.8.2.15592",
  "device_id": "671113bfba911339bf2be6c8",
  "state": "CONNECTED",
  "upgradable": false,
  "overheating": false,
  "uptime": 4767038,
  "client_count": 7,
  "cpu_percent": "7.7",
  "mem_percent": "65.6",
  "system_uptime": "4767038",
  "uplink": {
    "type": "wire",
    "up": true,
    "speed": 1000,
    "uplink_mac": "28:70:4e:6d:f9:32",
    "uplink_device_name": "USW Ultra"
  },
  "unifi_name": "U6 Pro"
}

$ ansible-inventory -i inventory/unifi.yaml --host USW_Flex
{
  "ansible_host": "192.168.1.231",
  "ip": "192.168.1.231",
  "mac": "94:2a:6f:fe:0e:e5",
  "type": "usw",
  "model": "USWED37",
  "firmware_version": "2.1.8.971",
  "state": "CONNECTED",
  "client_count": 5,
  "cpu_percent": "11.0",
  "mem_percent": "82.8",
  "poe_ports": [
    {
      "port_idx": 6,
      "name": "Port 6",
      "up": true,
      "poe_enable": true,
      "poe_mode": "auto",
      "poe_power": "6.00",
      "poe_voltage": "47.24",
      "poe_good": true,
      "is_uplink": false
    },
    {
      "port_idx": 7,
      "name": "Port 7",
      "up": true,
      "poe_enable": true,
      "poe_mode": "auto",
      "poe_power": "13.50",
      "poe_voltage": "47.05",
      "poe_good": true,
      "is_uplink": false
    }
  ],
  "unifi_name": "USW Flex 2.5G 8 PoE"
}
```

## What This Is

- **Dynamic inventory plugin** for Ansible that fetches UniFi network clients as inventory hosts.
- **Supports UniFi OS controllers** (modern UniFi Dream Machine, Cloud Gateway, etc.).
- **Discovers clients** connected to your network (wired and wireless).
- **Optionally includes UniFi devices** (access points, switches, gateways).

## What This Is Not

- Not a UniFi controller configuration tool.
- Not compatible with legacy UniFi controllers (pre-UniFi OS) without modification.

## Prerequisites

- **Python 3.12+** (newer `aiounifi` releases may require 3.13+; check `pip install` output)
- **Ansible 2.15+**
- **UniFi OS controller** accessible via network (UDM, UCG, etc.).
- **API credentials**: API token (preferred), local admin without 2FA, or username/password with `totp_secret` when using a 2FA-enabled account (requires a recent aiounifi release with [PR #990](https://github.com/Kane610/aiounifi/pull/990) support).
- **Python dependencies**: Install in the same Python environment as Ansible:
  ```bash
  pip install -r requirements.txt
  ```

## Installation

Install the `aioue.network` collection from this GitHub repository:

```shell
ansible-galaxy collection install git+https://github.com/aioue/ansible-unifi-inventory.git
```

You can also include it in a `requirements.yml` file:

```yaml
---
collections:
  - name: aioue.network
    source: https://github.com/aioue/ansible-unifi-inventory.git
    type: git
    # If you need a specific version, you can specify a branch or tag:
    # version: v1.1.0
```

Then install with `ansible-galaxy collection install -r requirements.yml`.

## Configuration

This is an Ansible inventory plugin. Configuration is done via a YAML inventory file that uses the plugin.

### Inventory File Naming

Name inventory files `*.unifi.yml` or `*.unifi.yaml` so Ansible auto-detects the plugin without listing it in `enable_plugins`. Examples: `prod.unifi.yml`, `inventory/unifi.yaml`.

If you use a different filename, set `plugin: aioue.network.unifi` explicitly in the file.

### Create an Inventory File

Create a new inventory file (e.g., `prod.unifi.yml`) with your settings.

**Important:** Use the Fully Qualified Collection Name (FQCN) `aioue.network.unifi` for the `plugin` key.

```yaml
# Example: prod.unifi.yml

plugin: aioue.network.unifi

# UniFi controller URL (required)
url: "https://192.168.1.1"

# --- Authentication ---
# Provide EITHER token OR username/password

# API Token (Preferred method)
token: "your-api-token-here"

# Username/Password (Alternative)
# Must be a LOCAL admin account without 2FA
username: "ansible-admin"
password: "your-password"
# ---------------------

# Templated credentials (e.g. Ansible Vault lookups) are also supported:
# username: "{{ lookup('ansible.builtin.unvault', 'secrets.yml') | from_yaml | json_query('unifi_username') }}"
# password: "{{ lookup('ansible.builtin.unvault', 'secrets.yml') | from_yaml | json_query('unifi_password') }}"

site: "default"
verify_ssl: false
include_devices: false
last_seen_minutes: 30

# Optional: use MAC-based hostnames when device names are missing or unstable
# hostname: mac
```

### Hostname Option

The `hostname` option controls which UniFi field becomes the Ansible inventory hostname:

| Value | Source |
|-------|--------|
| `name` (default) | UniFi friendly name with sanitization; original stored in `unifi_name` |
| `mac` | MAC address with colons replaced by hyphens (e.g. `aa-bb-cc-dd-ee-ff`) |

When using `name`, hosts without a friendly name fall back to OUI plus MAC suffix, or the raw MAC.
When using `mac`, the friendly name (if any) is still available in the `unifi_name` host variable.

### Constructable Inventory (keyed_groups, compose, filters)

The plugin supports standard Constructable inventory options for dynamic grouping and host variable composition.

**keyed_groups** - create groups from host variables:

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"

keyed_groups:
  - key: ssid
    prefix: ssid
    separator: "_"
  - key: vlan_name
    prefix: vlan
    separator: "_"
  - key: network
    prefix: network
    separator: "_"
```

**compose** - set or override host variables:

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"

compose:
  ansible_host: ip | default(ipv6)
  device_label: name | default(mac)
```

**filters** - include or exclude hosts (requires `community.library_inventory_filtering_v1`):

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"

filters:
  - include: is_wired
  - exclude: ssid == "Guest"
```

### Inventory Caching

As of 1.1.0, use Ansible's built-in inventory caching instead of plugin-specific `cache_ttl` / `cache_path` options (removed in 1.1.0).

Configure caching in `ansible.cfg`:

```ini
[inventory]
cache = true
cache_plugin = ansible.builtin.jsonfile
cache_timeout = 30
cache_connection = /tmp/ansible_inventory_cache
```

Or per inventory source in your inventory file:

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
cache: true
cache_plugin: ansible.builtin.jsonfile
cache_timeout: 30
```

See [Ansible inventory cache documentation](https://docs.ansible.com/ansible/latest/inventory_guide/index.html#inventory-plugins-and-caching) for available cache plugins and options.

### Environment Variables

You can also provide configuration via environment variables, which override settings in the YAML file.

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_TOKEN=your-api-token-here
export UNIFI_SITE=default
export UNIFI_VERIFY_SSL=false
```

## Usage

Once the collection is installed and your inventory file is created, use it like any other Ansible inventory source.

### Use With ansible-inventory

```bash
# View full inventory as JSON
ansible-inventory -i prod.unifi.yml --list

# Show hosts in a specific group
ansible-inventory -i prod.unifi.yml --graph unifi_wired_clients

# See graph of all groups
ansible-inventory -i prod.unifi.yml --graph
```

### Use With Ansible Ad-Hoc Commands

```bash
# Ping all discovered hosts
ansible -i prod.unifi.yml all -m ping

# Target only wireless clients
ansible -i prod.unifi.yml unifi_wireless_clients -m shell -a "uptime"

# Target a specific SSID group
ansible -i prod.unifi.yml ssid_guest_wifi -m shell -a "uptime"
```

### Use With Ansible Playbooks

```bash
ansible-playbook -i prod.unifi.yml site.yml
ansible-playbook -i prod.unifi.yml site.yml --limit unifi_clients
```

### Using Multiple Inventory Sources

```bash
ansible-playbook -i static_hosts.yml -i prod.unifi.yml site.yml
```

## Authentication

Two authentication methods are supported.

### API Token (Preferred)

1. Log in to your UniFi controller as a **local** admin user.
2. Go to `Settings > Network > Control Plane > Integrations > Network API` (or similar path).
3. Create a new token.
4. Use this token for the `token` config option or the `UNIFI_TOKEN` environment variable.

### Username/Password

For password login you have three options:

1. **API token** (see above) - no login call, avoids rate limits.
2. **Local admin without 2FA** - simplest password flow for automation.
3. **`totp_secret`** - TOTP seed for accounts with 2FA enabled (local or SSO). Requires aiounifi with [automated 2FA login](https://github.com/Kane610/aiounifi/pull/990) (`Configuration.totp_secret`). Vault-friendly:

```yaml
username: "{{ vault_unifi_username }}"
password: "{{ vault_unifi_password }}"
totp_secret: "{{ vault_unifi_totp_secret }}"
```

For option 2, create a **local admin account** (not a ui.com SSO account) with 2FA disabled:

1. Go to `UniFi OS Settings > Admins & Users`.
2. Create a new user with the "Admin" role.
3. Select **Restrict to Local Access Only**.
4. Do **NOT** enable 2FA for this account.
5. Use these credentials for `username`/`password` or `UNIFI_USERNAME`/`UNIFI_PASSWORD`.

**Note:** If both token and username/password are provided, the **token takes precedence**.

Connection options (`url`, `username`, `password`, `token`, `totp_secret`) support Jinja2 templating, so you can reference Ansible Vault lookups or variables directly in the inventory file.

## Inventory Schema

### Groups

The plugin creates these dynamic groups:

**For clients:**
- `unifi_clients` - all discovered clients
- `unifi_wireless_clients` - wireless clients only
- `unifi_wired_clients` - wired clients only
- `ssid_<name>` - clients on specific SSID (e.g., `ssid_guest_wifi`)
- `vlan_<id>` - clients on specific VLAN ID (e.g., `vlan_10`)
- `vlan_<name>` - clients on specific VLAN name (e.g., `vlan_guest_network`)
- `network_<name>` - clients on specific network (e.g., `network_iot`)

**For devices (when `include_devices: true`):**
- `unifi_devices` - all UniFi devices
- `unifi_uap` - UniFi access points
- `unifi_usw` - UniFi switches
- `unifi_ugw` / `unifi_uxg` / `unifi_ucg` / `unifi_udm` - UniFi gateways

Additional groups can be created with `keyed_groups` (see above).

### Host Variables (Clients)

Each client host includes:
- `ansible_host` - IP address (IPv4 preferred, IPv6 fallback)
- `mac` - MAC address
- `ip` / `ipv4` - IPv4 address (if available)
- `ipv6` - IPv6 address (if available)
- `ipv6_addresses` - All IPv6 addresses (if multiple)
- `is_wired` - boolean, true if wired connection
- `site` - UniFi site name
- `last_seen_unix` - Unix timestamp of last seen
- `last_seen_iso` - ISO 8601 timestamp of last seen
- `ssid` - SSID name (wireless only)
- `ap_mac` - AP MAC address (wireless only)
- `sw_mac` - Switch MAC address (wired only)
- `port` - Switch port number (wired only)
- `vlan` - VLAN ID (if available)
- `vlan_name` - VLAN name (if available)
- `network` - Network name (if available)
- `network_id` - Network ID (if available)
- `oui` - Device manufacturer OUI (if available)
- `is_guest` - boolean, true for guest network clients
- `blocked` - boolean, true when blocked in UniFi
- `firmware_version` - Client firmware version (when reported by UniFi)

### Host Variables (Devices)

Each device host includes:
- `ansible_host` - Management IP address
- `mac` - MAC address
- `ip` - IP address
- `model` - Device model
- `type` - Device type (uap, usw, ugw, udm, etc.)
- `firmware_version` - Current firmware version
- `site` - UniFi site name
- `device_id` - UniFi device ID
- `state` - Device state (e.g. `CONNECTED`)
- `adopted` - boolean, adoption status
- `upgradable` - boolean, firmware update available
- `upgrade_to_firmware` - Target firmware when upgradable
- `overheating` - boolean, thermal warning state
- `disabled` - boolean, administratively disabled
- `uptime` - Device uptime in seconds
- `uplink_depth` - Hops to gateway
- `client_count` - Connected client count (`user_num_sta`)
- `uplink` - Uplink details (type, remote MAC, etc.)
- `cpu_percent` / `mem_percent` / `system_uptime` - From `system-stats`
- `poe_ports` - List of PoE-capable switch ports with power state (switches only)

## Configuration Options Reference

| Option | Env Var | Config Key | Default |
|--------|---------|------------|---------|
| Controller URL | `UNIFI_URL` | `url` | (required) |
| Username | `UNIFI_USERNAME` | `username` | "" |
| Password | `UNIFI_PASSWORD` | `password` | "" |
| API Token | `UNIFI_TOKEN` | `token` | "" |
| TOTP Secret | `UNIFI_TOTP_SECRET` | `totp_secret` | "" |
| Site Name | `UNIFI_SITE` | `site` | `default` |
| Verify SSL | `UNIFI_VERIFY_SSL` | `verify_ssl` | `true` |
| Include Devices | `UNIFI_INCLUDE_DEVICES` | `include_devices` | `false` |
| Last Seen Minutes | `UNIFI_LAST_SEEN_MINUTES` | `last_seen_minutes` | `30` |
| Hostname Source | `UNIFI_HOSTNAME` | `hostname` | `name` |

Inventory caching is configured via standard Ansible options (`cache`, `cache_plugin`, `cache_timeout`), not plugin-specific keys.

## Security Best Practices

### Don't Commit Secrets

- **Never commit** inventory files with real credentials.
- Use a local file and add it to `.gitignore`.
- Use Ansible Vault to encrypt the inventory file.

### Use Ansible Vault

```bash
ansible-vault encrypt prod.unifi.yml
ansible-playbook -i prod.unifi.yml site.yml --ask-vault-pass
```

### Use Environment Variables

For CI/CD pipelines, use environment variables to inject secrets.

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_TOKEN=$VAULT_UNIFI_TOKEN
ansible-playbook -i prod.unifi.yml site.yml
```

### Token vs Password

- Prefer **API tokens** over username/password.
- Tokens can be revoked without changing account credentials.

## Troubleshooting

### SSL Certificate Errors

**Symptom:** `SSL: CERTIFICATE_VERIFY_FAILED` errors

**Solution:** Self-signed certificates are common on UniFi controllers.
- Set `verify_ssl: false` in your inventory config file (easiest, but less secure).
- Add your controller's certificate to your system trust store.

### Authentication Failures

**Symptom:** "Authentication failed" or 403/401 errors

**Causes:**
- Incorrect username/password or token.
- Token expired or revoked.
- **Two-Factor Authentication (2FA)** on a password account without `totp_secret` configured.
- Installed aiounifi is too old for `totp_secret` (upgrade after [PR #990](https://github.com/Kane610/aiounifi/pull/990) is released).
- Using a ui.com SSO account without token or `totp_secret`.

**Solution:**
- Verify credentials.
- Prefer **token authentication** for automation (avoids login rate limits).
- For 2FA accounts, set `totp_secret` once aiounifi supports it, or use a local admin without 2FA.
- Regenerate your API token.

### No Hosts Returned

**Symptom:** Empty inventory

**Causes:**
- `last_seen_minutes` threshold is too low.
- No clients have been active recently.
- Wrong `site` name specified.
- `filters` excluding all hosts.

**Solution:**
- Increase `last_seen_minutes` to `1440` (24 hours).
- Verify your `site` name in the UniFi controller (often `default`).
- Enable devices: `include_devices: true`.
- Review `filters` rules.

### Stale Inventory Data

**Symptom:** Inventory doesn't reflect recent changes (new clients, IP changes).

**Solution:**
- Clear the Ansible inventory cache directory (path set in `cache_connection`).
- Reduce `cache_timeout` for more frequent updates.
- Disable caching temporarily: `cache: false`.

### Network Timeouts

**Symptom:** Network request errors, "Connection refused".

**Causes:**
- Controller URL is incorrect or unreachable from where Ansible is running.
- Firewall blocking HTTPS (port 443) access.

**Solution:**
- Verify controller URL.
- Test connectivity: `curl -k https://192.168.1.1`
- Check firewall rules.

## Advanced Usage

### Filter by Last Seen Time

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
last_seen_minutes: 5
```

### Include Infrastructure Devices

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
include_devices: true
```

### Multiple Sites

Create separate inventory files per site:

**`site_default.unifi.yml`:**
```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
site: "default"
```

**`site_branch.unifi.yml`:**
```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
site: "branch-office"
```

## Performance Notes

- Enable Ansible inventory caching to reduce UniFi API calls on repeated runs.
- The first uncached run is slower (typically 2-10 seconds) while data is fetched from the API.
- Cached runs within the `cache_timeout` window are much faster.

## Upgrading

### From 1.0.0

1. Upgrade: `ansible-galaxy collection install aioue.network --upgrade`
2. Remove `cache_ttl` and `cache_path` from inventory files; configure Ansible inventory cache (see above)
3. Optionally set `hostname: mac` for stable MAC-based host keys
4. Optionally rename inventory files to `*.unifi.yml` for auto-detection

### From pre-collection versions

If you copied `unifi.py` into a local plugins directory:

1. Install the collection: `ansible-galaxy collection install aioue.network`
2. Update inventory files: `plugin: unifi` → `plugin: aioue.network.unifi`
3. Remove custom `inventory_plugins` / `enable_plugins` entries for the old plugin
4. Remove the old plugin file from `~/.ansible/plugins/inventory/` or your custom path

## Releasing a New Version

1. Bump `version:` in `galaxy.yml`
2. Update `CHANGELOG.md`
3. Commit, tag, and push:

```bash
git tag v1.x.x
git push origin v1.x.x
```

The GitHub Actions workflow builds the collection, publishes to Ansible Galaxy, and creates a GitHub Release.

## Contributing

For issues or enhancements, please ensure:
- Python 3.12+ compatibility
- Type hints for all functions
- PEP 8 code style

## License

GNU General Public License v3.0 or later (GPL-3.0+)

See [LICENSE](LICENSE) file for full text.

Copyright (c) 2025 Tom Paine (https://github.com/aioue)
