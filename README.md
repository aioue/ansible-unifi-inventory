# aioue.network

Dynamic inventory plugin for Ansible that discovers hosts from a UniFi OS controller (UDM, UCG, etc.). Built on top of [aiounifi](https://github.com/Kane610/aiounifi).

```shell
$ ansible-inventory -i inventory/unifi.yaml all --graph
@all:
  |--@ungrouped:
  |--@unifi_clients:
  |  |--phone
  |  |--laptop
  |  |--Kitchen Echo
  |  |--pc
  |  |--console
  |  |--nas
  |--@unifi_wireless_clients:
  |  |--phone
  |--@network_default:
  |  |--laptop
  |--@network_iot:
  |  |--Kitchen Echo
  |--@vlan_30:
  |  |--Kitchen Echo
  |--@vlan_iot:
  |  |--Kitchen Echo
  |--@unifi_wired_clients:
  |  |--pc
  |  |--console
  |  |--nas
  |--@ssid_iot:
  |  |--Kitchen Echo
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
- **API credentials**: A dedicated local admin user/password (2FA not supported) or an API token.
- **Python dependencies**: Install in the same Python environment as Ansible:
  ```bash
  pip install aiounifi aiohttp PyYAML
  ```

## Installation

You can install the `aioue.network` collection from this GitHub repository using the Ansible Galaxy CLI:

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
    # version: main
```

Then, install it with `ansible-galaxy collection install -r requirements.yml`.

## Configuration

This is an Ansible inventory plugin. Configuration is done via a YAML inventory file that uses the plugin.

### Create an Inventory File

Create a new inventory file (e.g., `unifi_inventory.yml`) with your settings.

**Important:** You must use the Fully Qualified Collection Name (FQCN) `aioue.network.unifi` for the `plugin` key.

```yaml
# Example: unifi_inventory.yml

# Use the FQCN for the plugin
plugin: aioue.network.unifi

# UniFi controller URL (required)
url: "https://192.168.1.1"

# --- Authentication ---
# Provide EITHER token OR username/password

# API Token (Preferred method)
# Leave empty to use username/password
token: "your-api-token-here"

# Username/Password (Alternative)
# Must be a LOCAL admin account without 2FA
username: "ansible-admin"
password: "your-password"
# ---------------------

# UniFi site name
site: "default"

# Set to false for self-signed certificates
verify_ssl: false

# Set to true to include APs, switches, etc.
include_devices: false

# Only include clients seen in the last 30 minutes
last_seen_minutes: 30

# Cache API results for 30 seconds
cache_ttl: 30
```

### Environment Variables

You can also provide configuration via environment variables, which will override settings in the YAML file.

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_TOKEN=your-api-token-here
export UNIFI_SITE=default
export UNIFI_VERIFY_SSL=false
```

## Usage

Once your collection is installed and your `unifi_inventory.yml` file is created, you can use it like any other Ansible inventory source.

### Use With ansible-inventory

```bash
# View full inventory as JSON
ansible-inventory -i unifi_inventory.yml --list

# Show hosts in a specific group
ansible-inventory -i unifi_inventory.yml --graph unifi_wired_clients

# See graph of all groups
ansible-inventory -i unifi_inventory.yml --graph
```

### Use With Ansible Ad-Hoc Commands

```bash
# Ping all discovered hosts
ansible -i unifi_inventory.yml all -m ping

# Target only wireless clients
ansible -i unifi_inventory.yml unifi_wireless_clients -m shell -a "uptime"

# Target a specific SSID group
ansible -i unifi_inventory.yml ssid_guest_wifi -m shell -a "uptime"
```

### Use With Ansible Playbooks

```bash
# Run a playbook against your UniFi inventory
ansible-playbook -i unifi_inventory.yml site.yml

# Limit the playbook to a dynamic group
ansible-playbook -i unifi_inventory.yml site.yml --limit unifi_clients
```

### Using Multiple Inventory Sources

Ansible can merge multiple inventory sources.

```bash
ansible-playbook -i static_hosts.yml -i unifi_inventory.yml site.yml
```

## Authentication

Two authentication methods are supported.

### API Token (Preferred)

1.  Log in to your UniFi controller as a **local** admin user.
2.  Go to `Settings > Network > Control Plane > Integrations > Network API` (or similar path).
3.  Create a new token.
4.  Use this token for the `token` config option or the `UNIFI_TOKEN` environment variable.

### Username/Password

You must use a **local admin account** (not a ui.com SSO account) and **2FA must be disabled** for this account.

1.  Go to `UniFi OS Settings > Admins & Users`.
2.  Create a new user.
3.  Select "Admin" role.
4.  **Crucially, select "Restrict to Local Access Only"**.
5.  Do **NOT** enable 2FA for this account.
6.  Use these credentials for the `username`/`password` config options or the `UNIFI_USERNAME`/`UNIFI_PASSWORD` environment variables.

**Note:** If both token and username/password are provided, the **token takes precedence**.

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
- `unifi_ugw` / `unifi_uxg` / `unifi_ucg` - UniFi gateways

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

### Host Variables (Devices)

Each device host includes:
- `ansible_host` - Management IP address
- `mac` - MAC address
- `ip` - IP address
- `model` - Device model
- `type` - Device type (uap, usw, ugw, etc.)
- `firmware_version` - Current firmware version
- `site` - UniFi site name
- `adopted` - boolean, adoption status
- `state` - Device state

## Configuration Options Reference

| Option | Env Var | Config Key | Default |
|--------|---------|------------|---------|
| Controller URL | `UNIFI_URL` | `url` | (required) |
| Username | `UNIFI_USERNAME` | `username` | "" |
| Password | `UNIFI_PASSWORD` | `password` | "" |
| API Token | `UNIFI_TOKEN` | `token` | "" |
| Site Name | `UNIFI_SITE` | `site` | `default` |
| Verify SSL | `UNIFI_VERIFY_SSL` | `verify_ssl` | `true` |
| Include Devices | `UNIFI_INCLUDE_DEVICES` | `include_devices` | `false` |
| Last Seen Minutes | `UNIFI_LAST_SEEN_MINUTES` | `last_seen_minutes` | `30` |
| Cache TTL | `UNIFI_CACHE_TTL` | `cache_ttl` | `30` |
| Cache Path | `UNIFI_CACHE_PATH` | `cache_path` | `./.cache/unifi_inventory.json` |

## Security Best Practices

### Don't Commit Secrets

- **Never commit** your `unifi_inventory.yml` file with real credentials.
- Use a local file and add it to `.gitignore`.
- Use Ansible Vault to encrypt the inventory file.

### Use Ansible Vault

Encrypt your sensitive inventory file:

```bash
# Encrypt config file
ansible-vault encrypt unifi_inventory.yml

# Use with inventory
ansible-playbook -i unifi_inventory.yml site.yml --ask-vault-pass
```

### Use Environment Variables

For CI/CD pipelines, use environment variables to inject secrets.

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_TOKEN=$VAULT_UNIFI_TOKEN
ansible-playbook -i unifi_inventory.yml site.yml
```

### Token vs Password

- Prefer **API tokens** over username/password.
- Tokens can be easily revoked without changing account credentials.

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
- **Two-Factor Authentication (2FA) is enabled on the account.** This plugin does not support 2FA.
- Using a ui.com SSO account instead of a local admin account.

**Solution:**
- Verify credentials.
- **You MUST use a local admin account with 2FA disabled.** See the "Authentication" section for instructions on how to create one.
- Regenerate your API token.

### No Hosts Returned

**Symptom:** Empty inventory

**Causes:**
- `last_seen_minutes` threshold is too low.
- No clients have been active recently.
- Wrong `site` name specified.

**Solution:**
- Increase `last_seen_minutes` to `1440` (24 hours) to see if stale clients appear.
- Verify your `site` name in the UniFi controller (it's often `default`).
- Enable devices to see your infrastructure: `include_devices: true`.

### Stale Cache Data

**Symptom:** Inventory doesn't reflect recent changes (new clients, IP changes).

**Solution:**
- Clear the cache file: `rm ./.cache/unifi_inventory.json` (or the path set in `cache_path`).
- Reduce `cache_ttl` for more frequent updates.
- Set `cache_ttl: 0` to disable caching entirely (not recommended for frequent runs).

### Network Timeouts

**Symptom:** Network request errors, "Connection refused".

**Causes:**
- Controller URL is incorrect or unreachable from where Ansible is running.
- Firewall is blocking HTTPS (port 443) access to the controller.

**Solution:**
- Verify controller URL.
- Test connectivity: `curl -k https://192.168.1.1` (replace with your URL).
- Check firewall rules.

## Advanced Usage

### Filter by Last Seen Time

Only include clients seen in the last 5 minutes:

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
last_seen_minutes: 5
```

### Include Infrastructure Devices

Include APs, switches, and gateways in the inventory:

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
include_devices: true
```

### Disable Caching

For real-time inventory without caching (will be slower and cause more API load):

```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
cache_ttl: 0
```

### Multiple Sites

For multi-site controllers, create separate inventory files for each site you want to query.

**`site_default.yml`:**
```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
site: "default"
```

**`site_branch.yml`:**
```yaml
plugin: aioue.network.unifi
url: "https://192.168.1.1"
token: "your-token"
site: "branch-office"
```

## Performance Notes

- **Caching is enabled by default** (`cache_ttl: 30` seconds) to reduce API calls.
- The first run will be slower (2-10 seconds) as it fetches data from the API.
- Subsequent runs within the TTL window will be very fast (< 100ms) as they read from the cache file.

## Upgrading from pre-collection versions

If you were using the plugin directly (copying `unifi.py` to your plugins directory), 1.0.0 has breaking changes:

1. **Install the collection:** `ansible-galaxy collection install git+https://github.com/aioue/ansible-unifi-inventory.git`
2. **Update inventory files:** change `plugin: unifi` to `plugin: aioue.network.unifi`
3. **Update ansible.cfg:** remove `unifi` from `enable_plugins` (the collection is auto-discovered). If you had `inventory_plugins = ./plugins/inventory`, that line can also be removed
4. **Remove the old plugin file** from `~/.ansible/plugins/inventory/` or your custom path
5. **Python 3.12+** is now required (was 3.11+)

## Contributing

For issues or enhancements, please ensure:
- Python 3.12+ compatibility
- Type hints for all functions
- PEP 8 code style

## License

GNU General Public License v3.0 or later (GPL-3.0+)

See [LICENSE](LICENSE) file for full text.

Copyright (c) 2025 Tom Paine (https://github.com/aioue)
