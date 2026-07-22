# Copyright (c) 2025 Tom Paine (https://github.com/aioue)
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
UniFi Dynamic Ansible Inventory Plugin

Discovers UniFi clients and optionally devices from a UniFi OS controller
and provides them as Ansible inventory.

This plugin can be used in YAML inventory files with the 'plugin: aioue.network.unifi' directive.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
    name: unifi
    short_description: UniFi dynamic inventory plugin
    description:
        - Discovers UniFi clients and optionally devices from a UniFi OS controller
        - Supports both token-based and username/password authentication
        - Groups hosts by connection type (wired/wireless), SSID, VLAN, and device type
    extends_documentation_fragment:
        - ansible.builtin.constructed
        - ansible.builtin.inventory_cache
    options:
        plugin:
            description: Name of the plugin
            required: true
            choices: ['aioue.network.unifi']
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
        totp_secret:
            description:
                - TOTP shared secret for automated 2FA login (local or SSO accounts).
                - Requires aiounifi with C(totp_secret) support (see aiounifi PR #990); when unset, 2FA accounts must use token auth or a non-2FA local admin.
            type: str
            env:
                - name: UNIFI_TOTP_SECRET
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
        hostname:
            description:
                - How to derive the inventory hostname for clients and devices.
                - V(mac) uses the MAC address with colons replaced by hyphens (e.g. aa-bb-cc-dd-ee-ff).
                - V(name) uses the UniFi friendly name with sanitization; the original name is stored in C(unifi_name).
            type: str
            default: name
            choices: [mac, name]
            env:
                - name: UNIFI_HOSTNAME
        filters:
            description:
                - A list of include/exclude filters that allows to select/deselect hosts for this inventory.
                - Filters are processed sequentially until the first filter where O(filters[].exclude) or O(filters[].include) matches is found.
                - In case O(filters[].exclude) matches, the host is excluded, and in case O(filters[].include) matches, the host is included.
                - In case no filter matches, the host is included.
            type: list
            elements: dict
            version_added: 1.1.0
            suboptions:
                exclude:
                    description:
                        - A Jinja2 condition. If it matches for a host, that host is B(excluded).
                        - Exactly one of O(filters[].exclude) and O(filters[].include) can be specified.
                    type: str
                include:
                    description:
                        - A Jinja2 condition. If it matches for a host, that host is B(included).
                        - Exactly one of O(filters[].exclude) and O(filters[].include) can be specified.
                    type: str
"""

EXAMPLES = r"""
# Example inventory file: inventory/unifi.yaml
plugin: aioue.network.unifi
url: https://192.168.1.1
username: admin
password: secret
site: default
verify_ssl: false
include_devices: false
last_seen_minutes: 30
cache: true
cache_timeout: 30

# Example with token authentication
plugin: aioue.network.unifi
url: https://192.168.1.1
token: your-api-token-here
verify_ssl: false

# Optional: use MAC-based hostnames for stability when device names change
# hostname: mac
keyed_groups:
  - key: ssid
    prefix: ssid
    separator: ""
"""

import asyncio
import concurrent.futures
import enum
import inspect
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable
from ansible_collections.community.library_inventory_filtering_v1.plugins.plugin_utils.inventory_filter import (
    filter_host,
    parse_filters,
)

try:
    import aiohttp
    from aiounifi.controller import Controller
    from aiounifi.errors import (
        AiounifiException,
        LoginRequired,
        ResponseError,
        TwoFaTokenRequired,
    )
    from aiounifi.models.api import ApiRequest
    from aiounifi.models.configuration import Configuration

    HAS_AIOUNIFI = True
except ImportError:
    HAS_AIOUNIFI = False

VALID_PLUGIN_NAMES = ("aioue.network.unifi",)

logger = logging.getLogger(__name__)


def sanitize_group_name(name: str) -> str:
    """Sanitize group name to lowercase alphanumeric and underscore."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


def sanitize_hostname(name: str) -> str:
    """Sanitize a friendly name for use as an Ansible inventory hostname."""
    return name.replace(" ", "_")


def mac_to_hostname(mac: str) -> str:
    """Convert a MAC address to a stable inventory hostname."""
    return mac.replace(":", "-").lower()


def _inventory_value(value: Any) -> Any:
    """Return a JSON-serializable value for Ansible inventory host variables."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_inventory_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _inventory_value(item) for key, item in value.items()}
    return str(value)


def _login_rate_limit_message(error: Exception) -> Optional[str]:
    """Return a user-facing message when UniFi throttles authentication."""
    err = str(error)
    if "429" in err or "AUTHENTICATION_FAILED_LIMIT_REACHED" in err:
        return (
            "UniFi login rate limit reached. Wait before retrying, use token "
            "authentication, or increase inventory cache_timeout."
        )
    return None


def _build_poe_ports(device: Any) -> List[Dict[str, Any]]:
    """Summarize PoE-capable switch ports from a UniFi device."""
    port_table = getattr(device, "port_table", None) or []
    ports: List[Dict[str, Any]] = []

    for port in port_table:
        if not isinstance(port, dict):
            continue
        if not port.get("port_poe") and not port.get("poe_enable"):
            continue
        ports.append(
            {
                "port_idx": port.get("port_idx"),
                "name": port.get("name"),
                "up": port.get("up"),
                "poe_enable": port.get("poe_enable"),
                "poe_mode": port.get("poe_mode"),
                "poe_power": port.get("poe_power"),
                "poe_voltage": port.get("poe_voltage"),
                "poe_good": port.get("poe_good"),
                "is_uplink": port.get("is_uplink"),
            }
        )

    return _inventory_value(ports)


def _summarize_uplink(uplink: Any) -> Dict[str, Any]:
    """Return a compact uplink summary without rx/tx counter noise."""
    if not isinstance(uplink, dict):
        return _inventory_value(uplink)

    summary = {
        key: uplink.get(key)
        for key in (
            "type",
            "up",
            "speed",
            "max_speed",
            "media",
            "name",
            "port_idx",
            "uplink_mac",
            "uplink_device_name",
            "uplink_remote_port",
            "uplink_source",
            "full_duplex",
        )
        if uplink.get(key) is not None
    }
    return _inventory_value(summary)


def _build_outlets(device: Any) -> List[Dict[str, Any]]:
    """Summarize PDU/outlet state from a UniFi device."""
    outlet_table = getattr(device, "outlet_table", None) or []
    outlets: List[Dict[str, Any]] = []

    for outlet in outlet_table:
        if not isinstance(outlet, dict):
            continue
        outlets.append(
            {
                "index": outlet.get("index"),
                "name": outlet.get("name"),
                "relay_state": outlet.get("relay_state"),
                "cycle_enabled": outlet.get("cycle_enabled"),
                "outlet_caps": outlet.get("outlet_caps"),
            }
        )

    return _inventory_value(outlets)


def _set_optional_hostvar(
    hostvars: Dict[str, Any], key: str, value: Any
) -> None:
    """Set a host variable when the source value is present."""
    if value is None:
        return
    if isinstance(value, str) and not value:
        return
    hostvars[key] = _inventory_value(value)


def _iter_handler_items(handler: Any) -> Iterable[Tuple[str, Any]]:
    """Iterate (id, item) pairs from an aiounifi handler without private API access."""
    items_fn = getattr(handler, "items", None)
    if callable(items_fn):
        return items_fn()

    values_fn = getattr(handler, "values", None)
    if callable(values_fn):
        result = []
        for item in values_fn():
            item_id = getattr(item, "mac", None)
            if item_id is None and hasattr(item, "raw"):
                item_id = item.raw.get("mac")
            if item_id is not None:
                result.append((item_id, item))
        return result

    all_fn = getattr(handler, "all", None)
    if callable(all_fn):
        result = []
        for item in all_fn():
            item_id = getattr(item, "mac", None)
            if item_id is None and hasattr(item, "raw"):
                item_id = item.raw.get("mac")
            if item_id is not None:
                result.append((item_id, item))
        return result

    private_items = getattr(handler, "_items", None)
    if isinstance(private_items, dict):
        return private_items.items()

    return []


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    """UniFi dynamic inventory plugin."""

    NAME = "aioue.network.unifi"

    def verify_file(self, path):
        """Verify that the inventory file is valid for this plugin."""
        if not super(InventoryModule, self).verify_file(path):
            return False

        if path.endswith((".unifi.yaml", ".unifi.yml", "unifi.yaml", "unifi.yml")):
            return True

        try:
            import yaml

            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return isinstance(data, dict) and data.get("plugin") in VALID_PLUGIN_NAMES
        except Exception:
            return False

    def parse(self, inventory, loader, path, cache=True):
        """Parse inventory from UniFi controller."""
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        if not HAS_AIOUNIFI:
            raise AnsibleError(
                "The UniFi inventory plugin requires the 'aiounifi' and 'aiohttp' Python libraries. "
                "Install them with: pip install aiounifi aiohttp"
            )

        self._read_config_data(path)

        # Apply Jinja2 templating to connection options so vault lookups in
        # inventory files (e.g. secrets.yml) resolve before authentication.
        self.url = self._template_option("url")
        self.username = self._template_option("username") or ""
        self.password = self._template_option("password") or ""
        self.token = self._template_option("token") or ""
        self.totp_secret = self._template_option("totp_secret") or ""

        if not self.url:
            raise AnsibleError("UniFi controller URL is required")

        if not self.token and not (self.username and self.password):
            raise AnsibleError(
                "Authentication required: provide token or username+password"
            )

        cache_key = self.get_cache_key(path)
        user_cache_setting = self.get_option("cache")
        attempt_to_read_cache = user_cache_setting and cache
        if attempt_to_read_cache:
            try:
                results = self._cache[cache_key]
            except KeyError:
                results = None
        else:
            results = None

        if results is None:
            results = self._run_async(self._fetch_from_controller())
            if user_cache_setting:
                self._cache[cache_key] = results

        self._populate_inventory(results)

    def _template_option(self, option_name: str) -> Optional[str]:
        """Return an inventory option value, resolving Jinja2 templates if present."""
        value = self.get_option(option_name)
        if value is None:
            return None
        if self.templar.is_template(value):
            return self.templar.template(value)
        return value

    def _run_async(self, coro):
        """Run a coroutine in a dedicated thread with its own event loop."""
        def _target():
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(coro)
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_target).result()

    def _resolve_client_hostname(
        self, mac: str, client: Any, mode: str
    ) -> Tuple[str, Optional[str]]:
        """Return inventory hostname and optional original UniFi name."""
        friendly = (
            getattr(client, "name", None)
            or getattr(client, "hostname", None)
            or getattr(client, "display_name", None)
            or getattr(client, "alias", None)
            or getattr(client, "friendly_name", None)
        )

        if mode == "mac":
            return mac_to_hostname(mac), friendly

        if not friendly:
            oui = getattr(client, "oui", None)
            if oui:
                friendly = f"{oui.replace(' ', '_')}_{mac[-8:].replace(':', '')}"
            else:
                friendly = mac

        return sanitize_hostname(friendly), friendly

    def _resolve_device_hostname(
        self, mac: str, device: Any, mode: str
    ) -> Tuple[str, Optional[str]]:
        """Return inventory hostname and optional original UniFi name."""
        name = getattr(device, "name", None)

        if mode == "mac":
            return mac_to_hostname(mac), name

        if not name:
            model = getattr(device, "model", "device")
            name = f"{model}_{mac[-8:].replace(':', '')}"

        return sanitize_hostname(name), name

    def _build_client_host(
        self,
        mac: str,
        client: Any,
        vlan_names: Dict[int, str],
        current_time: float,
        last_seen_threshold: float,
    ) -> Optional[Dict[str, Any]]:
        """Build a host dict for a UniFi client, or None if it should be skipped."""
        last_seen = getattr(client, "last_seen", 0)
        if (current_time - last_seen) > last_seen_threshold:
            return None

        hostname_mode = self.get_option("hostname")
        hostname, unifi_name = self._resolve_client_hostname(mac, client, hostname_mode)

        ipv4 = getattr(client, "ip", None) or client.raw.get("ip")

        ipv6_addresses = client.raw.get("ipv6_addresses", [])
        ipv6 = None
        ipv6_link_local = None

        if ipv6_addresses:
            for addr in ipv6_addresses:
                if addr.startswith("fe80:"):
                    if not ipv6_link_local:
                        ipv6_link_local = addr
                else:
                    ipv6 = addr
                    break

            if not ipv6 and ipv6_link_local:
                ipv6 = ipv6_link_local

        ansible_host = ipv4 or ipv6
        if not ansible_host:
            return None

        is_wired = getattr(client, "is_wired", False)
        hostvars = {
            "ansible_host": ansible_host,
            "mac": mac,
            "is_wired": is_wired,
            "site": self.get_option("site"),
            "last_seen_unix": int(last_seen),
            "last_seen_iso": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_seen)
            ),
        }

        if unifi_name is not None:
            hostvars["unifi_name"] = unifi_name

        if ipv4:
            hostvars["ipv4"] = ipv4
            hostvars["ip"] = ipv4
        if ipv6:
            hostvars["ipv6"] = ipv6
        if ipv6_addresses and len(ipv6_addresses) > 1:
            hostvars["ipv6_addresses"] = ipv6_addresses

        if not is_wired:
            ssid = getattr(client, "essid", None)
            if ssid:
                hostvars["ssid"] = ssid
            ap_mac = getattr(client, "ap_mac", None)
            if ap_mac:
                hostvars["ap_mac"] = ap_mac
        else:
            sw_mac = getattr(client, "sw_mac", None)
            if sw_mac:
                hostvars["sw_mac"] = sw_mac
            sw_port = getattr(client, "sw_port", None)
            if sw_port:
                hostvars["port"] = sw_port

        vlan = getattr(client, "vlan", None) or client.raw.get("vlan")
        network = getattr(client, "network", None) or client.raw.get("network")
        network_id = getattr(client, "network_id", None) or client.raw.get(
            "network_id"
        )

        if network:
            hostvars["network"] = network
        if network_id:
            hostvars["network_id"] = network_id
        if vlan:
            hostvars["vlan"] = vlan
            vlan_name = vlan_names.get(vlan)
            if vlan_name:
                hostvars["vlan_name"] = vlan_name

        oui = getattr(client, "oui", None)
        if oui:
            hostvars["oui"] = oui

        if getattr(client, "is_guest", False):
            hostvars["is_guest"] = True
        if getattr(client, "blocked", False):
            hostvars["blocked"] = True

        firmware_version = getattr(client, "firmware_version", None)
        if firmware_version:
            hostvars["firmware_version"] = firmware_version

        _set_optional_hostvar(hostvars, "fixed_ip", getattr(client, "fixed_ip", None))
        _set_optional_hostvar(
            hostvars, "unifi_hostname", getattr(client, "hostname", None)
        )
        _set_optional_hostvar(
            hostvars, "device_name", getattr(client, "device_name", None)
        )
        _set_optional_hostvar(
            hostvars, "first_seen", getattr(client, "first_seen", None)
        )
        _set_optional_hostvar(
            hostvars, "association_time", getattr(client, "association_time", None)
        )
        _set_optional_hostvar(
            hostvars,
            "latest_association_time",
            getattr(client, "latest_association_time", None),
        )
        if is_wired:
            _set_optional_hostvar(
                hostvars, "switch_depth", getattr(client, "switch_depth", None)
            )
            _set_optional_hostvar(
                hostvars, "wired_rate_mbps", getattr(client, "wired_rate_mbps", None)
            )
        else:
            _set_optional_hostvar(
                hostvars, "powersave_enabled", getattr(client, "powersave_enabled", None)
            )

        groups = ["unifi_clients"]
        if is_wired:
            groups.append("unifi_wired_clients")
        else:
            groups.append("unifi_wireless_clients")
            ssid = hostvars.get("ssid")
            if ssid:
                groups.append(f"ssid_{sanitize_group_name(ssid)}")

        if network:
            groups.append(f"network_{sanitize_group_name(network)}")

        if vlan:
            groups.append(f"vlan_{vlan}")
            vlan_name = vlan_names.get(vlan)
            if vlan_name:
                groups.append(f"vlan_{sanitize_group_name(vlan_name)}")

        return {"hostname": hostname, "hostvars": hostvars, "groups": groups}

    def _build_device_host(self, mac: str, device: Any) -> Optional[Dict[str, Any]]:
        """Build a host dict for a UniFi device, or None if it should be skipped."""
        ip = getattr(device, "ip", None)
        if not ip:
            return None

        hostname_mode = self.get_option("hostname")
        hostname, unifi_name = self._resolve_device_hostname(mac, device, hostname_mode)

        dev_type = _inventory_value(getattr(device, "type", "unknown"))
        model = _inventory_value(getattr(device, "model", "unknown"))
        firmware = _inventory_value(getattr(device, "version", "unknown"))

        hostvars = {
            "ansible_host": ip,
            "mac": mac,
            "ip": ip,
            "model": model,
            "type": dev_type,
            "firmware_version": firmware,
            "site": self.get_option("site"),
        }

        _set_optional_hostvar(hostvars, "device_id", getattr(device, "id", None))
        _set_optional_hostvar(hostvars, "state", getattr(device, "state", None))
        _set_optional_hostvar(hostvars, "adopted", getattr(device, "adopted", None))
        _set_optional_hostvar(hostvars, "upgradable", getattr(device, "upgradable", None))
        _set_optional_hostvar(
            hostvars, "upgrade_to_firmware", getattr(device, "upgrade_to_firmware", None)
        )
        _set_optional_hostvar(hostvars, "overheating", getattr(device, "overheating", None))
        _set_optional_hostvar(hostvars, "disabled", getattr(device, "disabled", None))
        _set_optional_hostvar(hostvars, "uptime", getattr(device, "uptime", None))
        _set_optional_hostvar(
            hostvars, "uplink_depth", getattr(device, "uplink_depth", None)
        )
        _set_optional_hostvar(
            hostvars, "client_count", getattr(device, "user_num_sta", None)
        )
        uplink = getattr(device, "uplink", None)
        if uplink:
            hostvars["uplink"] = _summarize_uplink(uplink)

        _set_optional_hostvar(
            hostvars, "general_temperature", getattr(device, "general_temperature", None)
        )
        _set_optional_hostvar(hostvars, "fan_level", getattr(device, "fan_level", None))
        _set_optional_hostvar(hostvars, "has_fan", getattr(device, "has_fan", None))
        _set_optional_hostvar(
            hostvars, "has_temperature", getattr(device, "has_temperature", None)
        )
        _set_optional_hostvar(hostvars, "last_seen", getattr(device, "last_seen", None))
        _set_optional_hostvar(
            hostvars, "supports_led_ring", getattr(device, "supports_led_ring", None)
        )
        _set_optional_hostvar(
            hostvars, "led_override", getattr(device, "led_override", None)
        )
        _set_optional_hostvar(
            hostvars,
            "led_override_color",
            getattr(device, "led_override_color", None),
        )

        try:
            cpu, mem, uptime = device.system_stats
            _set_optional_hostvar(hostvars, "cpu_percent", cpu)
            _set_optional_hostvar(hostvars, "mem_percent", mem)
            _set_optional_hostvar(hostvars, "system_uptime", uptime)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

        poe_ports = _build_poe_ports(device)
        if poe_ports:
            hostvars["poe_ports"] = poe_ports

        outlets = _build_outlets(device)
        if outlets:
            hostvars["outlets"] = outlets

        if unifi_name is not None:
            hostvars["unifi_name"] = unifi_name

        groups = ["unifi_devices", sanitize_group_name(f"unifi_{dev_type}")]

        state = hostvars.get("state")
        if state:
            groups.append(sanitize_group_name(f"device_state_{state}"))

        if hostvars.get("upgradable"):
            groups.append("unifi_upgradable")

        if hostvars.get("overheating"):
            groups.append("unifi_overheating")

        if poe_ports and any(port.get("poe_good") for port in poe_ports):
            groups.append("unifi_poe_powered")

        return {"hostname": hostname, "hostvars": hostvars, "groups": groups}

    def _populate_inventory(self, hosts: List[Dict[str, Any]]) -> None:
        """Populate Ansible inventory from fetched host dicts."""
        strict = self.get_option("strict")
        filters = parse_filters(self.get_option("filters"))

        for host_data in hosts:
            hostname = host_data["hostname"]
            hostvars = {
                key: _inventory_value(value)
                for key, value in host_data["hostvars"].items()
            }
            groups = host_data.get("groups", [])

            if not filter_host(self, hostname, hostvars, filters):
                continue

            self.inventory.add_host(hostname)
            for key, value in hostvars.items():
                self.inventory.set_variable(hostname, key, value)

            self._set_composite_vars(
                self.get_option("compose"), hostvars, hostname, strict=strict
            )
            self._add_host_to_composed_groups(
                self.get_option("groups"), hostvars, hostname, strict=strict
            )
            self._add_host_to_keyed_groups(
                self.get_option("keyed_groups"), hostvars, hostname, strict=strict
            )

            for group_name in groups:
                self.inventory.add_group(group_name)
                self.inventory.add_child(group_name, hostname)

    async def _fetch_from_controller(self) -> List[Dict[str, Any]]:
        """Fetch inventory from UniFi controller."""
        hosts: List[Dict[str, Any]] = []

        url = self.url
        verify_ssl = self.get_option("verify_ssl")
        ssl_context = False if not verify_ssl else True

        connector = aiohttp.TCPConnector(
            ssl=ssl_context if ssl_context is False else None
        )
        session = aiohttp.ClientSession(connector=connector)

        try:
            token = self.token
            if token:
                from http.cookies import SimpleCookie

                from yarl import URL

                cookies = SimpleCookie()
                cookies["unifises"] = token
                session.cookie_jar.update_cookies(cookies, URL(url))

            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.hostname or parsed.path
            port = parsed.port or 443

            config_kwargs = {
                "session": session,
                "host": host,
                "username": self.username,
                "password": self.password,
                "port": port,
                "site": self.get_option("site"),
                "ssl_context": ssl_context,
            }
            if self.totp_secret and "totp_secret" in inspect.signature(
                Configuration
            ).parameters:
                config_kwargs["totp_secret"] = self.totp_secret

            config = Configuration(**config_kwargs)

            controller = Controller(config)

            if not token:
                try:
                    await controller.login()
                except LoginRequired:
                    raise AnsibleError("Authentication failed: check credentials")
                except TwoFaTokenRequired:
                    if self.totp_secret and "totp_secret" not in inspect.signature(
                        Configuration
                    ).parameters:
                        raise AnsibleError(
                            "2FA is required but installed aiounifi does not support "
                            "totp_secret yet. Upgrade aiounifi, use token authentication, "
                            "or use a local admin without 2FA."
                        )
                    raise AnsibleError(
                        "2FA is required. Set totp_secret (vault-friendly TOTP seed), use "
                        "token authentication, or create a local admin without 2FA."
                    )
                except (ResponseError, AiounifiException) as e:
                    rate_limit_message = _login_rate_limit_message(e)
                    if rate_limit_message:
                        raise AnsibleError(rate_limit_message)
                    raise AnsibleError(f"Controller error during login: {e}")

            try:
                await controller.clients.update()
                if self.get_option("include_devices"):
                    await controller.devices.update()
            except (AiounifiException, ResponseError) as e:
                if "403" in str(e) or "401" in str(e):
                    raise AnsibleError(
                        "Authorization failed. If using 2FA, create a local admin account "
                        "without 2FA for automation, or use token authentication."
                    )
                raise AnsibleError(f"Failed to fetch data from controller: {e}")

            vlan_names: Dict[int, str] = {}
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
                logger.warning(
                    "Failed to fetch network configuration for VLAN names: %s", e
                )

            current_time = time.time()
            last_seen_threshold = self.get_option("last_seen_minutes") * 60

            for mac, client in _iter_handler_items(controller.clients):
                host = self._build_client_host(
                    mac, client, vlan_names, current_time, last_seen_threshold
                )
                if host is not None:
                    hosts.append(host)

            if self.get_option("include_devices"):
                for mac, device in _iter_handler_items(controller.devices):
                    host = self._build_device_host(mac, device)
                    if host is not None:
                        hosts.append(host)

        except AiounifiException as e:
            raise AnsibleError(f"UniFi API error: {e}")
        except Exception as e:
            raise AnsibleError(f"Unexpected error: {e}")
        finally:
            await session.close()

        return hosts
