# UniFi Dynamic Ansible Inventory

Dynamic inventory plugin for Ansible that discovers hosts from a UniFi OS controller (UDM, UCG, etc.).

## What This Is

- **Dynamic inventory plugin** for Ansible that fetches UniFi network clients as inventory hosts
- **Supports UniFi OS controllers** (modern UniFi Dream Machine, Cloud Gateway, etc.)
- **Discovers clients** connected to your network (wired and wireless)
- **Optionally includes UniFi devices** (access points, switches, gateways)

## What This Is Not

- Not a UniFi controller configuration tool
- Not compatible with legacy UniFi controllers (pre-UniFi OS) without modification

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy plugin to Ansible directory
mkdir -p ~/.ansible/plugins/inventory
cp plugins/inventory/unifi.py ~/.ansible/plugins/inventory/

# 3. Enable plugin in ansible.cfg
cat >> ansible.cfg << 'EOF'
[inventory]
enable_plugins = unifi
EOF

# 4. Edit inventory file with your UniFi controller details
vi inventory/unifi.yaml

# 5. Test the inventory
ansible-inventory -i inventory/unifi.yaml --list
```

## Prerequisites

- **Python 3.11+** installed
- **Ansible 2.15+** installed
- **UniFi OS controller** accessible via network (UDM, UCG, etc.)
- **API credentials**: local admin username/password or API token

## Installation

### Step 1: Install Python Dependencies

Choose one of the following methods:

#### Option A: Install from requirements.txt (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt
```

#### Option B: Install dependencies directly

```bash
pip install aiounifi aiohttp PyYAML
```

#### Option C: Use pipx (recommended for system installations)

```bash
pipx install aiounifi aiohttp PyYAML
```

### Step 2: Install the Plugin

Choose one of the following methods to make the plugin available to Ansible:

#### Copy to Ansible Plugin Directory

```bash
# User-level installation
mkdir -p ~/.ansible/plugins/inventory
cp plugins/inventory/unifi.py ~/.ansible/plugins/inventory/

# Or system-level installation (requires sudo)
sudo mkdir -p /usr/share/ansible/plugins/inventory
sudo cp plugins/inventory/unifi.py /usr/share/ansible/plugins/inventory/
```

### Step 3: Enable the Plugin in ansible.cfg

Create or update your `ansible.cfg` to enable the UniFi inventory plugin:

```ini
[inventory]
enable_plugins = host_list, script, auto, yaml, ini, toml, unifi
```

**Important:** The plugin must be listed in `enable_plugins` for Ansible to recognize and use it.

If you're keeping the plugin in a custom location (not in standard Ansible paths), also add:

```ini
[defaults]
inventory_plugins = ./plugins/inventory
```

## Configuration

This is an Ansible inventory plugin. Configuration is done via YAML inventory files with the `plugin: unifi` directive.

### Enable the Plugin

Before using the plugin, ensure it's enabled in your `ansible.cfg`:

```ini
[inventory]
enable_plugins = unifi
```

### Create an Inventory File

Edit the provided inventory file (`inventory/unifi.yaml`) with your settings:

```yaml
plugin: unifi
url: "https://192.168.1.1"
token: "your-api-token-here"  # Or use username/password
site: "default"
verify_ssl: false  # Set true for valid certificates
include_devices: false
last_seen_minutes: 30
cache_ttl: 30
```

### Environment Variables

You can also use environment variables:

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_TOKEN=your-api-token-here
export UNIFI_SITE=default
export UNIFI_VERIFY_SSL=false
```

## Authentication

Two authentication methods are supported:

### Username/Password

Create a local admin without 2FA

`UniFi OS Settings > Admins & Users > Create New User -> Admin + Restrict to Local Access Only`

Provide credentials via config file or environment:

```yaml
plugin: unifi
url: "https://192.168.1.1"
username: "admin"
password: "your-password"
```

Or:

```bash
export UNIFI_USERNAME=admin
export UNIFI_PASSWORD=your-password
```

### API Token (UNTESTED)

After logging in as a the _local_ admin user, go to `Settings > Network > Control Plane > Integrations > Network API` and create a new token

Use the token in config or via `UNIFI_TOKEN` env var.

Leave empty to use username/password instead.

**Note:** If both token and username/password are provided, token takes precedence.


## Usage

### Use With Ansible

```bash
# Ping all discovered hosts
ansible -i inventory/unifi.yaml all -m ping

# Run playbook against wireless clients
ansible-playbook -i inventory/unifi.yaml site.yml \
  --limit unifi_wireless_clients

# Target specific SSID group
ansible -i inventory/unifi.yaml ssid_guest_wifi -m shell -a uptime
```

### Use With ansible-inventory

```bash
# View full inventory
ansible-inventory -i inventory/unifi.yaml --list

# Show hosts in a group
ansible-inventory -i inventory/unifi.yaml \
  --graph unifi_wired_clients
```

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

## Ansible Integration

### Using ansible.cfg

Create or update `ansible.cfg`:

```ini
[defaults]
inventory = ./inventory/unifi.yaml
```

### Using Multiple Inventory Sources

Ansible can merge multiple inventory sources:

```bash
ansible-playbook -i static_hosts.yml \
  -i inventory/unifi.yaml site.yml
```

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

- **Never commit** `inventory/unifi.yaml` with real credentials
- The `.gitignore` file already excludes `inventory.yaml` and `.env`
- Use the provided example files as templates only

### Use Ansible Vault

Encrypt sensitive config files:

```bash
# Encrypt config file
ansible-vault encrypt inventory/unifi.yaml

# Use with inventory
ansible-playbook -i inventory/unifi.yaml site.yml \
  --ask-vault-pass
```

### Use Environment Variables

For CI/CD pipelines, use environment variables:

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_TOKEN=$VAULT_UNIFI_TOKEN
ansible-playbook -i inventory/unifi.yaml site.yml
```

### Token vs Password

- Prefer **API tokens** over username/password
- Tokens can be easily revoked without changing account credentials
- Tokens have narrower scope than full admin credentials

## Troubleshooting

### SSL Certificate Errors

**Symptom:** `SSL: CERTIFICATE_VERIFY_FAILED` errors

**Solution:** Self-signed certificates are common on UniFi controllers. Either:

1. Set `verify_ssl: false` in config (not recommended for production)
2. Add controller certificate to system trust store

### Authentication Failures

**Symptom:** "Authentication failed" or 403/401 errors

**Causes:**
- Incorrect username/password or token
- Token expired or revoked
- Local user disabled (must be local, not SSO)
- **Two-Factor Authentication (2FA) enabled on the account**

**Solution:**
- Verify credentials
- **For accounts with 2FA**: Create a separate local admin account without 2FA for automation
- Regenerate API token
- Ensure using a local admin account (not ui.com SSO account)

**Important**: This plugin does not support 2FA workflows. For automation, create a dedicated local admin account:
1. Navigate to: `https://<controller-ip>/network/default/admins/users`
   (Or: UniFi Network > Settings > Users and Admins)
2. Click **Add User** or **Add Local Admin**
3. Create a **non-default local user** (e.g., `ansible-automation`)
4. Set a strong password
5. **Do NOT enable 2FA** on this account
6. Grant "Limited Admin" or "Full Admin" permissions
7. Use these credentials in the inventory config

**Note**: The default SSO admin account cannot be used. You must create a separate local user specifically for automation.

### No Hosts Returned

**Symptom:** Empty inventory

**Causes:**
- `last_seen_minutes` threshold too strict
- No clients connected recently
- Wrong site name

**Solution:**
- Increase `last_seen_minutes` to `1440` (24 hours)
- Verify site name matches controller
- Enable devices to see infrastructure: `include_devices: true`

### Cache Stale Data

**Symptom:** Inventory doesn't reflect recent changes

**Solution:**
- Clear cache: `rm -rf .cache/`
- Reduce `cache_ttl` for more frequent updates
- Set `cache_ttl: 0` to disable caching

### Network Timeouts

**Symptom:** Network request error

**Causes:**
- Controller unreachable
- Firewall blocking
- Network issues

**Solution:**
- Verify controller URL is correct and accessible
- Check firewall rules allow HTTPS (port 443)
- Test with `curl -k https://192.168.1.1` to verify connectivity

### Permission Errors

**Symptom:** Cannot write cache file

**Solution:**
- Ensure `.cache/` directory is writable
- Run with appropriate user permissions
- Change `cache_path` to writable location

## Advanced Usage

### Filter by Last Seen Time

Only include clients seen in the last 5 minutes:

```yaml
plugin: unifi
url: "https://192.168.1.1"
token: "your-token"
last_seen_minutes: 5
```

### Include Infrastructure Devices

Include APs, switches, and gateways:

```yaml
plugin: unifi
url: "https://192.168.1.1"
token: "your-token"
include_devices: true
```

### Disable Caching

For real-time inventory without caching:

```yaml
plugin: unifi
url: "https://192.168.1.1"
token: "your-token"
cache_ttl: 0
```

### Multiple Sites

For multi-site controllers, create separate inventory files per site:

```yaml
plugin: unifi
url: "https://192.168.1.1"
token: "your-token"
site: "branch-office"
```

## Performance Notes

- **Caching is enabled by default** (30 second TTL) to reduce API calls
- First run may take 2-5 seconds to fetch and process data
- Cached runs return in < 100ms
- Large networks (1000+ clients) may take 5-10 seconds on first fetch
- Consider increasing `cache_ttl` for very large networks

## Contributing

This plugin is designed to be self-contained and production-ready. For issues or enhancements, ensure:

- Python 3.11+ compatibility
- Type hints for all functions
- Error handling with appropriate exit codes
- Logging to stderr only (stdout reserved for JSON)
- PEP 8 code style

## License

GNU General Public License v3.0 or later (GPL-3.0+)

See [LICENSE](LICENSE) file for full text.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Copyright (c) 2025 Tom Paine (https://github.com/aioue)
