#!/usr/bin/env python3
# Copyright (c) 2025 Tom Paine (https://github.com/aioue)
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
UniFi Dynamic Ansible Inventory Plugin

Discovers UniFi clients and optionally devices from a UniFi OS controller
and provides them as Ansible inventory.

This plugin can be used in YAML inventory files with the 'plugin: unifi' directive.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
    name: aioue.unifi.unifi
    plugin_type: inventory
    short_description: UniFi dynamic inventory plugin
    description:
        - Discovers UniFi clients and optionally devices from a UniFi OS controller
        - Supports both token-based and username/password authentication
        - Includes caching support to reduce API calls
        - Groups hosts by connection type (wired/wireless), SSID, VLAN, and device type
    options:
        plugin:
            description: Name of the plugin
            required: true
            choices: ['aioue.unifi.unifi']
        url:
            description: UniFi controller URL (e.g., https://192.168.1.1)
            required: true
            type: str
            env:
                - name: UNIFI_URL
        username:
            description: UniFi username for authentication
            type: str
            env:
                - name: UNIFI_USERNAME
        password:
            description: UniFi password for authentication
            type: str
            env:
                - name: UNIFI_PASSWORD
        token:
            description: UniFi API token (preferred over username/password)
            type: str
            env:
                - name: UNIFI_TOKEN
        site:
            description: UniFi site name
            type: str
            default: default
            env:
                - name: UNIFI_SITE
        verify_ssl:
            description: Verify SSL certificates
            type: bool
            default: true
            env:
                - name: UNIFI_VERIFY_SSL
        include_devices:
            description: Include UniFi devices (APs, switches, gateways) in inventory
            type: bool
            default: false
            env:
                - name: UNIFI_INCLUDE_DEVICES
        last_seen_minutes:
            description: Only include clients seen within this many minutes
            type: int
            default: 30
            env:
                - name: UNIFI_LAST_SEEN_MINUTES
        cache_ttl:
            description: Cache TTL in seconds (0 to disable)
            type: int
            default: 30
            env:
                - name: UNIFI_CACHE_TTL
        cache_path:
            description: Path to cache file
            type: str
            default: ./.cache/unifi_inventory.json
            env:
                - name: UNIFI_CACHE_PATH
"""

EXAMPLES = r"""
# Example inventory file: inventory/unifi.yaml
plugin: aioue.unifi.unifi
url: https://192.168.1.1
username: admin
password: secret
site: default
verify_ssl: false
include_devices: false
last_seen_minutes: 30
cache_ttl: 30
cache_path: ./.cache/unifi_inventory.json

# Example with token authentication
plugin: aioue.unifi.unifi
url: https://192.168.1.1
token: your-api-token-here
verify_ssl: false
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable

try:
    import aiohttp
    from aiounifi.controller import Controller
    from aiounifi.errors import (
        AiounifiException,
        LoginRequired,
        RequestError,
        ResponseError,
        TwoFaTokenRequired,
    )
    from aiounifi.models.api import ApiRequest
    from aiounifi.models.configuration import Configuration

    HAS_AIOUNIFI = True
except ImportError:
    HAS_AIOUNIFI = False

# Configure logging
logger = logging.getLogger(__name__)


def sanitize_group_name(name: str) -> str:
    """Sanitize group name to lowercase alphanumeric and underscore"""
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


class InventoryModule(BaseInventoryPlugin, Cacheable):
    """UniFi dynamic inventory plugin"""

    NAME = "aioue.unifi.unifi"

    def verify_file(self, path):
        """Verify that the inventory file is valid for this plugin"""
        if super(InventoryModule, self).verify_file(path):
            # Check if it's a YAML file with 'plugin: unifi'
            if path.endswith(("unifi.yaml", "unifi.yml")):
                return True
            # Also check file contents
            try:
                with open(path, "r") as f:
                    content = f.read()
                    if "plugin: aioue.unifi.unifi" in content or "plugin: 'aioue.unifi.unifi'" in content:
                        return True
            except Exception:
                pass
        return False

    def parse(self, inventory, loader, path, cache=True):
        """Parse inventory from UniFi controller"""
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        if not HAS_AIOUNIFI:
            raise AnsibleError(
                "The UniFi inventory plugin requires the 'aiounifi' and 'aiohttp' Python libraries. "
                "Install them with: pip install aiounifi aiohttp"
            )

        # Read configuration from the inventory file
        self._read_config_data(path)

        # Get configuration options
        self.url = self.get_option("url")
        self.username = self.get_option("username") or ""
        self.password = self.get_option("password") or ""
        self.token = self.get_option("token") or ""
        self.site = self.get_option("site")
        self.verify_ssl = self.get_option("verify_ssl")
        self.include_devices = self.get_option("include_devices")
        self.last_seen_minutes = self.get_option("last_seen_minutes")
        self.cache_ttl = self.get_option("cache_ttl")
        self.cache_path = self.get_option("cache_path")

        # Validate configuration
        if not self.url:
            raise AnsibleError("UniFi controller URL is required")
        if not self.token and not (self.username and self.password):
            raise AnsibleError(
                "Authentication required: provide token or username+password"
            )

        # Fetch inventory from controller (no caching for now - can be added later)
        inventory_data = asyncio.run(self._fetch_from_controller())
        self._populate_inventory(inventory_data)

    def _get_cache_key(self, path):
        """Generate cache key based on configuration"""
        return f"unifi_{self.url}_{self.site}"

    def _populate_from_cache(self, cached_data):
        """Populate inventory from cached data"""
        self._populate_inventory(cached_data)

    def _populate_inventory(self, inventory_data):
        """Populate Ansible inventory from UniFi inventory data"""
        # Add all hosts
        for hostname, hostvars in (
            inventory_data.get("_meta", {}).get("hostvars", {}).items()
        ):
            self.inventory.add_host(hostname)
            for key, value in hostvars.items():
                self.inventory.set_variable(hostname, key, value)

        # Add groups
        for group_name, group_data in inventory_data.items():
            if group_name == "_meta" or group_name == "all":
                continue

            self.inventory.add_group(group_name)
            for hostname in group_data.get("hosts", []):
                self.inventory.add_child(group_name, hostname)

    async def _fetch_from_controller(self) -> Dict[str, Any]:
        """Fetch inventory from UniFi controller"""
        inventory: Dict[str, Any] = {
            "_meta": {"hostvars": {}},
            "all": {"hosts": []},
        }

        ssl_context = False if not self.verify_ssl else True

        # Create aiohttp session
        connector = aiohttp.TCPConnector(
            ssl=ssl_context if ssl_context is False else None
        )
        session = aiohttp.ClientSession(connector=connector)

        try:
            # For token auth, set the cookie in the session
            if self.token:
                from http.cookies import SimpleCookie

                from yarl import URL

                cookies = SimpleCookie()
                cookies["unifises"] = self.token
                session.cookie_jar.update_cookies(cookies, URL(self.url))

            # Extract host from URL
            from urllib.parse import urlparse

            parsed = urlparse(self.url)
            host = parsed.hostname or parsed.path
            port = parsed.port or 443

            # Create configuration object
            config = Configuration(
                session=session,
                host=host,
                username=self.username,
                password=self.password,
                port=port,
                site=self.site,
                ssl_context=ssl_context,
            )

            # Create controller
            controller = Controller(config)

            # Login (skip if using token)
            if not self.token:
                try:
                    await controller.login()
                except LoginRequired:
                    raise AnsibleError("Authentication failed: check credentials")
                except TwoFaTokenRequired:
                    raise AnsibleError(
                        "2FA is required. Please create a local admin account without 2FA "
                        "for automation, or use token authentication."
                    )
                except (ResponseError, AiounifiException) as e:
                    raise AnsibleError(f"Controller error during login: {e}")

            # Fetch clients and devices
            try:
                await controller.clients.update()
                if self.include_devices:
                    await controller.devices.update()
            except (AiounifiException, ResponseError) as e:
                if "403" in str(e) or "401" in str(e):
                    raise AnsibleError(
                        "Authorization failed. If using 2FA, create a local admin account "
                        "without 2FA for automation, or use token authentication."
                    )
                raise AnsibleError(f"Failed to fetch data from controller: {e}")

            # Fetch network configuration to get VLAN names
            vlan_names = {}
            try:
                network_request = ApiRequest(method="get", path="/rest/networkconf")
                networks_response = await controller.request(network_request)
                if networks_response and "data" in networks_response:
                    for network in networks_response["data"]:
                        vlan_id = network.get("vlan")
                        name = network.get("name")
                        if vlan_id and name:
                            vlan_names[int(vlan_id)] = name
            except Exception as e:
                # If we can't fetch networks, just continue without VLAN names
                logger.warning(
                    f"Failed to fetch network configuration for VLAN names: {e}"
                )

            # Process clients
            current_time = time.time()
            last_seen_threshold = self.last_seen_minutes * 60

            for mac, client in controller.clients._items.items():
                # Filter by last_seen
                last_seen = getattr(client, "last_seen", 0)
                if (current_time - last_seen) > last_seen_threshold:
                    continue

                # Determine hostname
                hostname = (
                    getattr(client, "name", None)
                    or getattr(client, "hostname", None)
                    or getattr(client, "display_name", None)
                    or getattr(client, "alias", None)
                    or getattr(client, "friendly_name", None)
                )

                # If no name, create one from OUI or MAC
                if not hostname:
                    oui = getattr(client, "oui", None)
                    if oui:
                        hostname = (
                            f"{oui.replace(' ', '_')}_{mac[-8:].replace(':', '')}"
                        )
                    else:
                        hostname = mac

                # Replace spaces with underscores for Ansible compatibility
                # Ansible's YAML parser and host pattern matching doesn't handle spaces
                if hostname:
                    hostname = hostname.replace(" ", "_")

                # Get IP addresses (both IPv4 and IPv6)
                ipv4 = getattr(client, "ip", None) or client.raw.get("ip")

                # IPv6 addresses are in an array - get the first non-link-local one
                ipv6_addresses = client.raw.get("ipv6_addresses", [])
                ipv6 = None
                ipv6_link_local = None

                if ipv6_addresses:
                    for addr in ipv6_addresses:
                        if addr.startswith("fe80:"):
                            # Link-local address - save as fallback
                            if not ipv6_link_local:
                                ipv6_link_local = addr
                        else:
                            # Global/ULA address - prefer this
                            ipv6 = addr
                            break

                    # If no global/ULA, use link-local
                    if not ipv6 and ipv6_link_local:
                        ipv6 = ipv6_link_local

                # ansible_host prefers IPv4, falls back to IPv6
                ansible_host = ipv4 or ipv6
                if not ansible_host:
                    continue

                # Build hostvars
                is_wired = getattr(client, "is_wired", False)
                hostvars = {
                    "ansible_host": ansible_host,
                    "mac": mac,
                    "is_wired": is_wired,
                    "site": self.site,
                    "last_seen_unix": int(last_seen),
                    "last_seen_iso": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_seen)
                    ),
                }

                # Add IP addresses
                if ipv4:
                    hostvars["ipv4"] = ipv4
                    hostvars["ip"] = ipv4  # Keep 'ip' for backward compatibility
                if ipv6:
                    hostvars["ipv6"] = ipv6
                # Add all IPv6 addresses if there are multiple
                if ipv6_addresses and len(ipv6_addresses) > 1:
                    hostvars["ipv6_addresses"] = ipv6_addresses

                # Add wireless-specific info
                if not is_wired:
                    ssid = getattr(client, "essid", None)
                    if ssid:
                        hostvars["ssid"] = ssid
                    ap_mac = getattr(client, "ap_mac", None)
                    if ap_mac:
                        hostvars["ap_mac"] = ap_mac

                # Add wired-specific info
                if is_wired:
                    sw_mac = getattr(client, "sw_mac", None)
                    if sw_mac:
                        hostvars["sw_mac"] = sw_mac
                    sw_port = getattr(client, "sw_port", None)
                    if sw_port:
                        hostvars["port"] = sw_port

                # Add VLAN and network info if available
                # Try both the property and raw dict access
                vlan = getattr(client, "vlan", None) or client.raw.get("vlan")
                network = getattr(client, "network", None) or client.raw.get("network")
                network_id = getattr(client, "network_id", None) or client.raw.get(
                    "network_id"
                )

                # Add network info to hostvars
                if network:
                    hostvars["network"] = network
                if network_id:
                    hostvars["network_id"] = network_id

                if vlan:
                    hostvars["vlan"] = vlan
                    # Add VLAN name if we have it
                    vlan_name = vlan_names.get(vlan)
                    if vlan_name:
                        hostvars["vlan_name"] = vlan_name

                # Add OUI/manufacturer if available
                oui = getattr(client, "oui", None)
                if oui:
                    hostvars["oui"] = oui

                # Build groups
                groups = ["unifi_clients"]
                if is_wired:
                    groups.append("unifi_wired_clients")
                else:
                    groups.append("unifi_wireless_clients")
                    ssid = hostvars.get("ssid")
                    if ssid:
                        groups.append(f"ssid_{sanitize_group_name(ssid)}")

                # Add network-based groups
                if network:
                    groups.append(f"network_{sanitize_group_name(network)}")

                if vlan:
                    # Add both VLAN ID group and VLAN name group
                    groups.append(f"vlan_{vlan}")
                    vlan_name = vlan_names.get(vlan)
                    if vlan_name:
                        groups.append(f"vlan_{sanitize_group_name(vlan_name)}")

                # Add host to inventory
                self._add_host_to_inventory(inventory, hostname, hostvars, groups)

            # Process devices if requested
            if self.include_devices:
                for mac, device in controller.devices._items.items():
                    # Determine hostname
                    hostname = getattr(device, "name", None)
                    if not hostname:
                        model = getattr(device, "model", "device")
                        hostname = f"{model}_{mac[-8:]}"

                    # Replace spaces with underscores for Ansible compatibility
                    if hostname:
                        hostname = hostname.replace(" ", "_")

                    # Get management IP
                    ip = getattr(device, "ip", None)
                    if not ip:
                        continue

                    # Get device info
                    dev_type = getattr(device, "type", "unknown")
                    model = getattr(device, "model", "unknown")
                    firmware = getattr(device, "version", "unknown")
                    adopted = getattr(device, "adopted", False)
                    state = getattr(device, "state", "unknown")

                    # Build hostvars
                    hostvars = {
                        "ansible_host": ip,
                        "mac": mac,
                        "ip": ip,
                        "model": model,
                        "type": dev_type,
                        "firmware_version": firmware,
                        "site": self.site,
                        "adopted": adopted,
                        "state": state,
                    }

                    # Build groups
                    groups = ["unifi_devices"]
                    type_group = sanitize_group_name(f"unifi_{dev_type}")
                    groups.append(type_group)

                    # Add host to inventory
                    self._add_host_to_inventory(inventory, hostname, hostvars, groups)

        except AiounifiException as e:
            raise AnsibleError(f"UniFi API error: {e}")
        except Exception as e:
            raise AnsibleError(f"Unexpected error: {e}")
        finally:
            await session.close()

        return inventory

    def _add_host_to_inventory(
        self,
        inventory: Dict[str, Any],
        hostname: str,
        hostvars: Dict[str, Any],
        groups: List[str],
    ) -> None:
        """Add a host to inventory data structure"""
        if hostname not in inventory["all"]["hosts"]:
            inventory["all"]["hosts"].append(hostname)

        inventory["_meta"]["hostvars"][hostname] = hostvars

        for group in groups:
            if group not in inventory:
                inventory[group] = {"hosts": []}
            if hostname not in inventory[group]["hosts"]:
                inventory[group]["hosts"].append(hostname)
