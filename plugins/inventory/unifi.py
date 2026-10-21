# Copyright (c) 2025 Tom Paine (https://github.com/aioue)
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

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
    author:
        - Tom Paine (@aioue)
        - Lenny Shirley (@lennysh)
    requirements:
        - Python >= 3.14
        - aiounifi >= 97 (Python library)
        - aiohttp >= 3.14.5 (Python library)
        - pyotp >= 2.10.0 (Python library; required for O(totp_secret))
    description:
        - Discovers UniFi clients and optionally devices from a UniFi OS controller
        - Supports session token, username/password, and password with totp_secret (2FA / SSO)
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
            description:
                - UniFi OS session cookie value (C(TOKEN)); takes precedence over username/password.
                - This is an expiring login session, not a Network Integrations API key.
            type: str
            env:
                - name: UNIFI_TOKEN
        totp_secret:
            description:
                - TOTP shared secret for automated 2FA login (local or SSO accounts).
                - Requires the C(pyotp) dependency.
            type: str
            env:
                - name: UNIFI_TOTP_SECRET
        site:
            description: UniFi site name
            type: str
            default: default
            env:
                - name: UNIFI_SITE
        validate_certs:
            description: Verify SSL certificates when connecting to the UniFi controller.
            type: bool
            default: true
            aliases:
                - verify_ssl
            env:
                - name: UNIFI_VALIDATE_CERTS
                - name: UNIFI_VERIFY_SSL
        api_timeout:
            description: Timeout in seconds for UniFi API HTTP requests.
            type: int
            default: 30
            version_added: 1.2.0
        allow_historical_addresses:
            description:
                - Use C(last_ip) and C(fixed_ip) when UniFi reports neither a usable IPv4 nor a usable IPv6 address.
                - A current IPv6 address is used before those historical addresses.
                - Disable when only currently reported addresses should become C(ansible_host).
            type: bool
            default: true
            version_added: 1.3.0
        strict_records:
            description:
                - Fail discovery when a client or device record is malformed.
                - When V(false), skip malformed records with a warning.
            type: bool
            default: true
            version_added: 1.3.0
        include_devices:
            description: Include UniFi devices (APs, switches, gateways) in inventory
            type: bool
            default: false
            env:
                - name: UNIFI_INCLUDE_DEVICES
        exclude_clients:
            description:
                - Exclude UniFi clients from the inventory output.
                - Skips the client API fetch when set to V(true).
            type: bool
            default: false
            version_added: 1.2.0
            env:
                - name: UNIFI_EXCLUDE_CLIENTS
        exclude_devices:
            description:
                - Exclude UniFi infrastructure devices even when O(include_devices) is V(true).
                - Skips the device API fetch when set to V(true).
            type: bool
            default: false
            version_added: 1.2.0
            env:
                - name: UNIFI_EXCLUDE_DEVICES
        last_seen_minutes:
            description:
                - Only include clients seen within this many minutes.
                - Must be greater than zero. Zero is not "no limit"; a zero threshold would keep only a client seen in this exact second.
            type: int
            default: 30
            env:
                - name: UNIFI_LAST_SEEN_MINUTES
        hostname:
            description:
                - How to derive the inventory hostname for clients and devices.
                - V(mac) uses the MAC address with colons replaced by hyphens (e.g. aa-bb-cc-dd-ee-ff).
                - V(name) uses the UniFi friendly name with sanitization; the original name is stored in C(unifi_name).
                - A friendly name that sanitizes to an empty hostname falls back to the hyphenated MAC address.
                - A missing name uses the manufacturer and MAC suffix when the controller sent an OUI, and otherwise the MAC address.
            type: str
            default: name
            choices: [mac, name]
            env:
                - name: UNIFI_HOSTNAME
        hostname_collision:
            description:
                - How to handle inventory names shared by different UniFi hosts or existing inventory entries.
                - V(disambiguate) adds a stable MAC suffix to colliding names and emits a warning.
                - V(fail) stops inventory parsing before adding any hosts.
            type: str
            default: disambiguate
            choices: [disambiguate, fail]
            env:
                - name: UNIFI_HOSTNAME_COLLISION
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
# validate_certs defaults to true. For a controller certificate signed by a
# private CA, point SSL_CERT_FILE at that CA instead of disabling verification.

# Method B: local admin password (no 2FA)
plugin: aioue.network.unifi
url: https://192.168.1.1
username: admin
password: secret
site: default
validate_certs: true
include_devices: false
last_seen_minutes: 30
cache: true
cache_timeout: 30

# Method A: UniFi OS session cookie (token takes precedence if both are set)
plugin: aioue.network.unifi
url: https://192.168.1.1
token: your-TOKEN-cookie-value
validate_certs: true
cache: true
cache_timeout: 30

# Method C: password + TOTP (2FA or ui.com SSO)
plugin: aioue.network.unifi
url: https://192.168.1.1
username: your-account
password: secret
totp_secret: BASE32-TOTP-SEED
validate_certs: true

# Clients only (skip infrastructure devices)
# include_devices: true
# exclude_devices: true

# Optional: use MAC-based hostnames for stability when device names change
# hostname: mac
# Group wireless clients from the source above by SSID.
keyed_groups:
  - key: ssid
    prefix: ssid
    separator: ""
"""

import asyncio
import enum
import hashlib
import ipaddress
import json
import logging
import math
import os
import re
import ssl
import time
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlsplit, urlunsplit

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable
from ansible_collections.community.library_inventory_filtering_v1.plugins.plugin_utils.inventory_filter import (
    filter_host,
    parse_filters,
)

AuthenticationRateLimitError = None

try:
    import aiohttp
    from aiounifi.controller import Controller
    from aiounifi.errors import (
        AiounifiException,
        BadGateway,
        Forbidden,
        LoginRequired,
        NoPermission,
        RequestError,
        ServiceUnavailable,
        TwoFaTokenRequired,
    )

    class ControllerRedirect(Exception):
        """The controller answered with a redirect, which this plugin does not follow."""

        def __init__(self, status: int) -> None:
            self.status = status
            super().__init__(f"UniFi controller returned HTTP {status} redirect")

    class _RedirectRefusingRequest:
        """Async context manager that refuses a 3xx from one ClientSession request.

        aiohttp discourages subclassing ClientSession. aiounifi calls
        ``async with session.request(...)``, so the guard has to live on the
        context manager rather than on ClientSession._request.
        """

        def __init__(self, inner, refuse_redirects: bool):
            self._inner = inner
            self._refuse_redirects = refuse_redirects
            self._entered = False

        async def __aenter__(self):
            response = await self._inner.__aenter__()
            self._entered = True
            # check_unifi_os already asked not to follow and reads a 302 as
            # "not UniFi OS". Login and API calls follow by default; refuse those.
            if self._refuse_redirects and 300 <= response.status < 400:
                status = response.status
                await self._inner.__aexit__(None, None, None)
                self._entered = False
                raise ControllerRedirect(status)
            return response

        async def __aexit__(self, exc_type, exc, tb):
            if not self._entered:
                return False
            return await self._inner.__aexit__(exc_type, exc, tb)

    class OriginLockedClientSession:
        """Keep UniFi HTTP on the origin already validated for this inventory source.

        aiounifi follows redirects by default. aiohttp resends a 307/308 JSON body,
        including a login password, and will follow an http Location onto another
        host. The inventory URL is restricted to one HTTPS origin, so a redirect
        is refused instead of being treated as API data.
        """

        def __init__(self, *args, **kwargs):
            self._session = aiohttp.ClientSession(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._session, name)

        def request(self, method, url, **kwargs):
            refuse_redirects = kwargs.get("allow_redirects", True) is not False
            kwargs["allow_redirects"] = False
            return _RedirectRefusingRequest(self._session.request(method, url, **kwargs), refuse_redirects)

        async def close(self):
            await self._session.close()

        async def __aenter__(self):
            await self._session.__aenter__()
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return await self._session.__aexit__(exc_type, exc, tb)

    try:
        from aiounifi.errors import AuthenticationRateLimitError
    except ImportError:
        AuthenticationRateLimitError = None  # type: ignore[misc, assignment]
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
    if not isinstance(name, str):
        raise ValueError("hostname must be a string")
    name = re.sub(r"[^\w.-]", "_", name.strip(), flags=re.UNICODE)
    if not name or not name.strip("_.-"):
        raise ValueError("hostname is empty after sanitization")
    return name


# InventoryData.add_host promotes these names to the implicit localhost. A DHCP
# hostname of localhost would then make `hosts: localhost` connect to that client.
_IMPLICIT_LOCALHOST = frozenset({"localhost", "127.0.0.1", "::1"})


def mac_to_hostname(mac: str) -> str:
    """Convert a MAC address to a stable inventory hostname."""
    return mac.replace(":", "-").lower()


def _hostname_from_friendly_name(name: str, mac: str) -> str:
    """Fall back to the MAC when a friendly name sanitizes to an empty hostname."""
    try:
        return sanitize_hostname(name)
    except ValueError as error:
        if error.args == ("hostname is empty after sanitization",):
            return mac_to_hostname(mac)
        raise


def _usable_address(value: Any, version: int) -> str | None:
    """Only advertise addresses usable without a controller-local interface scope."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("IP address must be a string")
    # A zone id names an interface on the controller, not a destination.
    if "%" in value:
        value = value.split("%", 1)[0]
    address = ipaddress.ip_address(value)
    # UniFi can put the other family in last_ip or ip. That slot is unused;
    # failing the record here drops a client that still has a usable address.
    if address.version != version:
        return None
    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local:
        return None
    return str(address)


def aiohttp_connector_ssl(validate_certs: bool):
    """Return the aiohttp C(TCPConnector) C(ssl=) value for TLS validation.

    When validation is disabled, return C(False) explicitly so aiohttp does not
    use the default SSL context, which can still verify certificates when
    C(REQUESTS_CA_BUNDLE) or C(SSL_CERT_FILE) is set in the environment.
    """
    if validate_certs:
        return None
    return False


def aiounifi_configuration_ssl_context(validate_certs: bool):
    """Return aiounifi C(Configuration) C(ssl_context=) value."""
    if validate_certs:
        return ssl.create_default_context()
    return False


def _inventory_value(value: Any) -> Any:
    """Return a JSON-serializable value for Ansible inventory host variables."""
    if value is None or isinstance(value, bool):
        return value
    # StrEnum members are isinstance(str) in Python 3.11+; handle enums first.
    if isinstance(value, enum.Enum):
        if isinstance(value, enum.StrEnum):
            return value.value
        return value.name
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_inventory_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _inventory_value(item) for key, item in value.items()}
    return str(value)


def _login_rate_limit_message(error: Exception) -> str | None:
    """Return a user-facing message when UniFi throttles authentication."""
    if AuthenticationRateLimitError is not None and isinstance(error, AuthenticationRateLimitError):
        return "UniFi login rate limit reached. Wait before retrying or increase inventory cache_timeout."

    # Match the auth-limit type and its stable code. A read can also return HTTP 429;
    # treating every "429" string as a login lockout hides that failure and can echo
    # the response body the message was built from.
    if "AUTHENTICATION_FAILED_LIMIT_REACHED" in str(error):
        return "UniFi login rate limit reached. Wait before retrying or increase inventory cache_timeout."
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


def _set_optional_hostvar(hostvars: Dict[str, Any], key: str, value: Any) -> None:
    """Set a host variable when the source value is present."""
    if value is None:
        return
    if isinstance(value, str) and not value:
        return
    hostvars[key] = _inventory_value(value)


def _reported_attribute(item: Any, name: str, raw_key: str | None = None) -> Any:
    """Return a controller field only when the record actually contained it.

    aiounifi properties often substitute 0 or False when the raw key is absent.
    Treating that sentinel as a measurement publishes epoch timestamps and
    false capability flags the controller never sent. Objects that store the
    value on the attribute itself, with no masking property, still resolve so
    tests can build records without copying every field into raw.
    """
    raw_key = raw_key or name
    raw = getattr(item, "raw", None)
    raw_dict = raw if isinstance(raw, dict) else None
    prop = getattr(type(item), name, None)
    if raw_dict is not None and raw_key not in raw_dict and isinstance(prop, property):
        return None
    if isinstance(prop, property) or raw_dict is None or raw_key not in raw_dict:
        try:
            # getattr(obj, name, default) turns a property's AttributeError into
            # the default, which would hide a present but unusable value.
            return getattr(item, name)
        except KeyError:
            return None
        except AttributeError:
            if isinstance(prop, property):
                raise
            return None
        except AssertionError as error:
            # A missing key is absence. A present value that fails the property's
            # type assert is a malformed record and must reach strict_records.
            if raw_dict is None or (raw_dict.get(raw_key) is None and raw_dict.get(name) is None):
                return None
            raise ValueError(f"invalid {name}") from error
    return raw_dict[raw_key]


def _is_timeout(error: BaseException) -> bool:
    """True when an aiounifi wrapper hid an HTTP or asyncio timeout."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if isinstance(current, TimeoutError):
            return True
        seen.add(id(current))
        # `raise RequestError(...) from None` clears __cause__ but leaves __context__.
        current = current.__cause__ or current.__context__
    return False


def _iter_handler_items(handler: Any) -> Iterable[Tuple[str, Any]]:
    """Iterate (id, item) pairs from an aiounifi handler's public items() view."""
    items_fn = getattr(handler, "items", None)
    if callable(items_fn):
        return items_fn()
    raise AnsibleError("Installed aiounifi handler has no supported item iterator")


def _remember_group(groups: List[str], sources: Dict[str, List[str]], group: str, label: Any) -> None:
    """Record a sanitized group and the controller name that produced it."""
    groups.append(group)
    if label is None:
        return
    text = str(label)
    bucket = sources.setdefault(group, [])
    if text not in bucket:
        bucket.append(text)


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    """UniFi dynamic inventory plugin."""

    NAME = "aioue.network.unifi"

    def verify_file(self, path):
        """Verify that the inventory file is valid for this plugin."""
        if not super().verify_file(path):
            return False

        # Basename match: endswith("unifi.yml") also claims myunifi.yml and not-unifi.yaml.
        filename = os.path.basename(path)
        if filename in ("unifi.yaml", "unifi.yml") or filename.endswith((".unifi.yaml", ".unifi.yml")):
            return True

        try:
            import yaml

            with open(path) as f:
                data = yaml.safe_load(f)
            return isinstance(data, dict) and data.get("plugin") in VALID_PLUGIN_NAMES
        except Exception:
            return False

    def parse(self, inventory, loader, path, cache=True):
        """Parse inventory from UniFi controller."""
        super().parse(inventory, loader, path, cache)

        if not HAS_AIOUNIFI:
            raise AnsibleError(
                "The UniFi inventory plugin requires the 'aiounifi' and 'aiohttp' Python libraries. "
                "Install them with: pip install aiounifi aiohttp"
            )

        self._read_config_data(path)

        # Apply Jinja2 templating to connection options so vault lookups in
        # inventory files (e.g. secrets.yml) resolve before authentication.
        self.url = self._template_option("url")
        self.token = self._template_option("token") or ""
        # Unused password/vault lookups must not break session-token authentication.
        self.username = "" if self.token else self._template_option("username") or ""
        self.password = "" if self.token else self._template_option("password") or ""
        self.totp_secret = "" if self.token else self._template_option("totp_secret") or ""

        if not self.url:
            raise AnsibleError("UniFi controller URL is required")

        if not self.token and not (self.username and self.password):
            raise AnsibleError("Authentication required: provide token or username+password")

        self._validate_options()

        cache_key = self.get_cache_key(path)
        fingerprint = self._cache_fingerprint()
        user_cache_setting = self.get_option("cache")
        attempt_to_read_cache = user_cache_setting and cache
        if attempt_to_read_cache:
            try:
                entry = self._cache[cache_key]
                results = (
                    entry["hosts"]
                    if isinstance(entry, dict)
                    and entry.get("version") == 1
                    and entry.get("fingerprint") == fingerprint
                    and isinstance(entry.get("hosts"), list)
                    else None
                )
            except KeyError:
                results = None
        else:
            results = None

        if results is None:
            results = self._run_async(self._fetch_from_controller())
            if user_cache_setting:
                self._cache[cache_key] = {"version": 1, "fingerprint": fingerprint, "hosts": results}

        self._populate_inventory(results)

    def _cache_fingerprint(self) -> str:
        """Invalidate fetched data when its effective source or selection changes."""
        options = {
            key: self.get_option(key)
            for key in (
                "site",
                "hostname",
                "include_devices",
                "exclude_clients",
                "exclude_devices",
                "last_seen_minutes",
                "allow_historical_addresses",
                "strict_records",
                "validate_certs",
            )
        }
        # Authentication material must never be copied into persistent cache data.
        options["url"] = self.url
        return hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()

    def _template_option(self, option_name: str) -> str | None:
        """Return an inventory option value, resolving Jinja2 templates if present."""
        value = self.get_option(option_name)
        if value is None:
            return None
        if self.templar.is_template(value):
            return self.templar.template(value)
        return value

    def _validate_options(self) -> None:
        """Reject settings that would silently change endpoints or remove time limits."""
        try:
            parsed = urlsplit(self.url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in ("", "/")
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError
            port = parsed.port
            if port == 0:
                raise ValueError
            self.url = urlunsplit(("https", parsed.netloc.lower(), "", "", ""))
        except ValueError, TypeError:
            raise AnsibleError(
                "url must be an HTTPS controller origin, with optional port and no credentials or path"
            ) from None
        if self.get_option("api_timeout") <= 0:
            raise AnsibleError("api_timeout must be greater than zero")
        if self.get_option("last_seen_minutes") <= 0:
            raise AnsibleError("last_seen_minutes must be greater than zero")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.get_option("site")):
            raise AnsibleError("site must contain only letters, numbers, underscores, or hyphens")
        if self.get_option("exclude_clients") and not (
            self.get_option("include_devices") and not self.get_option("exclude_devices")
        ):
            raise AnsibleError("Nothing to fetch from UniFi: enable clients or devices")

    def _run_async(self, coro):
        """Run the controller fetch on this thread.

        asyncio.run cancels the task on Ctrl-C. A worker thread would not see
        that signal, and shutting the thread's executor down waits until the
        HTTP call finishes, so ansible-inventory could ignore Ctrl-C for the
        whole timeout and retry budget.
        """
        return asyncio.run(coro)

    def _resolve_client_hostname(self, mac: str, client: Any, mode: str) -> Tuple[str, str | None]:
        """Return inventory hostname and optional original UniFi name."""
        friendly = (
            getattr(client, "name", None)
            or getattr(client, "hostname", None)
            or getattr(client, "display_name", None)
            or getattr(client, "alias", None)
            or getattr(client, "friendly_name", None)
        )
        if not isinstance(friendly, str) or not friendly.strip():
            friendly = None

        if mode == "mac":
            return mac_to_hostname(mac), friendly

        if friendly is None:
            oui = getattr(client, "oui", None)
            if oui:
                fallback = f"{oui.replace(' ', '_')}_{mac[-8:].replace(':', '')}"
            else:
                fallback = mac
            return _hostname_from_friendly_name(fallback, mac), None

        return _hostname_from_friendly_name(friendly, mac), friendly

    def _resolve_device_hostname(self, mac: str, device: Any, mode: str) -> Tuple[str, str | None]:
        """Return inventory hostname and optional original UniFi name."""
        name = getattr(device, "name", None)
        if not isinstance(name, str) or not name.strip():
            name = None

        if mode == "mac":
            return mac_to_hostname(mac), name

        if name is None:
            # Device.model raises KeyError when the controller omitted it, so the
            # getattr default never runs. The prefix is only a hostname label.
            model = _reported_attribute(device, "model") or "device"
            fallback = f"{model}_{mac[-8:].replace(':', '')}"
            return _hostname_from_friendly_name(fallback, mac), None

        return _hostname_from_friendly_name(name, mac), name

    def _build_client_host(
        self,
        mac: str,
        client: Any,
        vlan_names: Dict[int, str],
        current_time: float,
        last_seen_threshold: float,
    ) -> Dict[str, Any] | None:
        """Build a host dict for a UniFi client, or None if it should be skipped."""
        raw = getattr(client, "raw", None) or {}
        if not isinstance(raw, dict):
            raise ValueError("client raw data must be a dictionary")
        # aiounifi's Client.last_seen returns 0 when the key is absent, which the age
        # check then treats as 1970 and drops with no warning. Missing is malformed.
        reported_last_seen = _reported_attribute(client, "last_seen")
        if reported_last_seen is None:
            raise ValueError("last_seen is missing")
        last_seen = float(reported_last_seen)
        if not math.isfinite(last_seen) or last_seen < 0:
            raise ValueError("last_seen must be a finite, non-negative Unix timestamp")
        if (current_time - last_seen) > last_seen_threshold:
            return None

        hostname_mode = self.get_option("hostname")
        hostname, unifi_name = self._resolve_client_hostname(mac, client, hostname_mode)

        # UniFi omits plain ip for some DHCP-reserved wired clients; last_ip/fixed_ip remain.
        # The same field can hold a current IPv6 address. A family mismatch is not absence.
        reported_ip = getattr(client, "ip", None) or raw.get("ip")
        ipv4 = _usable_address(reported_ip, 4)
        address_source = "ip"

        ipv6_addresses = raw.get("ipv6_addresses") or []
        if not isinstance(ipv6_addresses, list):
            raise ValueError("ipv6_addresses must be a list")
        usable_ipv6 = []
        for addr in ipv6_addresses:
            if not isinstance(addr, str):
                raise ValueError("ipv6_addresses entries must be strings")
            address = _usable_address(addr, 6)
            if address and address not in usable_ipv6:
                usable_ipv6.append(address)
        current_ipv6 = _usable_address(reported_ip, 6)
        if current_ipv6 and current_ipv6 not in usable_ipv6:
            usable_ipv6.insert(0, current_ipv6)
        ipv6 = usable_ipv6[0] if usable_ipv6 else None

        # A current IPv6 address is a current address. Historical IPv4 is only used
        # when the controller reported neither a usable IPv4 nor a usable IPv6 address,
        # so a stale last_ip cannot point ansible_host at a different host.
        if not ipv4 and not ipv6 and self.get_option("allow_historical_addresses") is not False:
            for source, value in (
                ("last_ip", raw.get("last_ip")),
                ("fixed_ip", _reported_attribute(client, "fixed_ip")),
            ):
                ipv4 = _usable_address(value, 4)
                if ipv4:
                    address_source = source
                    break

        ansible_host = ipv4 or ipv6
        if not ansible_host:
            return None

        # Client.is_wired returns False when the key is absent. That sentinel
        # would publish a wireless client and skip its switch fields.
        is_wired = _reported_attribute(client, "is_wired")
        if is_wired is None:
            raise ValueError("is_wired is missing")
        if not isinstance(is_wired, bool):
            raise ValueError("is_wired must be a boolean")
        hostvars = {
            "ansible_host": ansible_host,
            "mac": mac,
            "is_wired": is_wired,
            "site": self.get_option("site"),
            "last_seen_unix": int(last_seen),
            "last_seen_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_seen)),
            "address_source": address_source if ipv4 else "ipv6",
        }

        if unifi_name is not None:
            hostvars["unifi_name"] = unifi_name

        if ipv4:
            hostvars["ipv4"] = ipv4
            hostvars["ip"] = ipv4
        if ipv6:
            hostvars["ipv6"] = ipv6
        if usable_ipv6:
            hostvars["ipv6_addresses"] = usable_ipv6

        if not is_wired:
            ssid = getattr(client, "essid", None)
            if ssid:
                hostvars["ssid"] = ssid
            ap_mac = getattr(client, "access_point_mac", None) or getattr(client, "ap_mac", None) or raw.get("ap_mac")
            if ap_mac:
                hostvars["ap_mac"] = ap_mac
        else:
            sw_mac = getattr(client, "switch_mac", None) or getattr(client, "sw_mac", None) or raw.get("sw_mac")
            if sw_mac:
                hostvars["sw_mac"] = sw_mac
            sw_port = getattr(client, "switch_port", None) or getattr(client, "sw_port", None) or raw.get("sw_port")
            if sw_port:
                # Ansible reserves "port"; this is a physical switch port, not a connection port.
                hostvars["switch_port"] = sw_port

        vlan = getattr(client, "vlan", None) or raw.get("vlan")
        if vlan is not None:
            vlan = int(vlan)
            if not 0 <= vlan <= 4094:
                raise ValueError("vlan must be between zero and 4094")
        network = getattr(client, "network", None) or raw.get("network")
        network_id = getattr(client, "network_id", None) or raw.get("network_id")

        if network:
            hostvars["network"] = network
        if network_id:
            hostvars["network_id"] = network_id
        # VLAN 0 is untagged. It stays inside the legal range so strict_records
        # does not fail the client, and it does not create a vlan_0 group.
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

        fixed_ip = _reported_attribute(client, "fixed_ip")
        if fixed_ip:
            fixed_ip = _usable_address(fixed_ip, 4)
        _set_optional_hostvar(hostvars, "fixed_ip", fixed_ip)
        _set_optional_hostvar(hostvars, "unifi_hostname", _reported_attribute(client, "hostname"))
        _set_optional_hostvar(hostvars, "device_name", _reported_attribute(client, "device_name"))
        _set_optional_hostvar(hostvars, "first_seen", _reported_attribute(client, "first_seen"))
        _set_optional_hostvar(
            hostvars, "association_time", _reported_attribute(client, "association_time", "assoc_time")
        )
        _set_optional_hostvar(
            hostvars,
            "latest_association_time",
            _reported_attribute(client, "latest_association_time", "latest_assoc_time"),
        )
        if is_wired:
            _set_optional_hostvar(hostvars, "switch_depth", _reported_attribute(client, "switch_depth", "sw_depth"))
            _set_optional_hostvar(hostvars, "wired_rate_mbps", _reported_attribute(client, "wired_rate_mbps"))
        else:
            _set_optional_hostvar(hostvars, "powersave_enabled", _reported_attribute(client, "powersave_enabled"))

        groups = ["unifi_clients"]
        group_sources: Dict[str, List[str]] = {}
        if is_wired:
            groups.append("unifi_wired_clients")
        else:
            groups.append("unifi_wireless_clients")
            ssid = hostvars.get("ssid")
            if ssid:
                _remember_group(groups, group_sources, f"ssid_{sanitize_group_name(ssid)}", ssid)

        if network:
            _remember_group(groups, group_sources, f"network_{sanitize_group_name(network)}", network)

        if vlan:
            groups.append(f"vlan_{vlan}")
            vlan_name = vlan_names.get(vlan)
            if vlan_name:
                _remember_group(groups, group_sources, f"vlan_{sanitize_group_name(vlan_name)}", vlan_name)

        return {
            "hostname": hostname,
            "hostvars": hostvars,
            "groups": groups,
            "group_sources": group_sources,
        }

    def _build_device_host(self, mac: str, device: Any) -> Dict[str, Any] | None:
        """Build a host dict for a UniFi device, or None if it should be skipped."""
        value = getattr(device, "ip", None)
        ip = _usable_address(value, ipaddress.ip_address(value).version) if value else None
        if not ip:
            return None

        hostname_mode = self.get_option("hostname")
        hostname, unifi_name = self._resolve_device_hostname(mac, device, hostname_mode)

        dev_type = _inventory_value(_reported_attribute(device, "type") or "unknown")
        model = _reported_attribute(device, "model")
        firmware = _reported_attribute(device, "version")

        hostvars = {
            "ansible_host": ip,
            "mac": mac,
            "ip": ip,
            "type": dev_type,
            "site": self.get_option("site"),
        }
        # getattr(device, "model", "unknown") never applies that default: the property
        # exists and raises KeyError when the controller omitted the field.
        if model is not None:
            hostvars["model"] = _inventory_value(model)
        if firmware is not None:
            hostvars["firmware_version"] = _inventory_value(firmware)

        _set_optional_hostvar(hostvars, "device_id", _reported_attribute(device, "id", "device_id"))
        _set_optional_hostvar(hostvars, "state", _reported_attribute(device, "state"))
        _set_optional_hostvar(hostvars, "adopted", _reported_attribute(device, "adopted"))
        _set_optional_hostvar(hostvars, "upgradable", _reported_attribute(device, "upgradable"))
        _set_optional_hostvar(hostvars, "upgrade_to_firmware", _reported_attribute(device, "upgrade_to_firmware"))
        _set_optional_hostvar(hostvars, "overheating", _reported_attribute(device, "overheating"))
        _set_optional_hostvar(hostvars, "disabled", _reported_attribute(device, "disabled"))
        _set_optional_hostvar(hostvars, "uptime", _reported_attribute(device, "uptime"))
        _set_optional_hostvar(hostvars, "uplink_depth", _reported_attribute(device, "uplink_depth"))
        _set_optional_hostvar(hostvars, "client_count", _reported_attribute(device, "user_num_sta", "user-num_sta"))
        uplink = _reported_attribute(device, "uplink")
        if uplink:
            hostvars["uplink"] = _summarize_uplink(uplink)

        _set_optional_hostvar(hostvars, "general_temperature", _reported_attribute(device, "general_temperature"))
        _set_optional_hostvar(hostvars, "fan_level", _reported_attribute(device, "fan_level"))
        _set_optional_hostvar(hostvars, "has_fan", _reported_attribute(device, "has_fan"))
        _set_optional_hostvar(hostvars, "has_temperature", _reported_attribute(device, "has_temperature"))
        _set_optional_hostvar(hostvars, "last_seen", _reported_attribute(device, "last_seen"))
        _set_optional_hostvar(
            hostvars, "supports_led_ring", _reported_attribute(device, "supports_led_ring", "hw_caps")
        )
        _set_optional_hostvar(hostvars, "led_override", _reported_attribute(device, "led_override"))
        _set_optional_hostvar(hostvars, "led_override_color", _reported_attribute(device, "led_override_color"))

        # A missing system-stats object is optional. A present value that is not
        # an object raises from the property and fails strict_records.
        stats = _reported_attribute(device, "system_stats", "system-stats")
        if stats is not None:
            cpu, mem, uptime = stats
            _set_optional_hostvar(hostvars, "cpu_percent", cpu)
            _set_optional_hostvar(hostvars, "mem_percent", mem)
            _set_optional_hostvar(hostvars, "system_uptime", uptime)

        poe_ports = _build_poe_ports(device)
        if poe_ports:
            hostvars["poe_ports"] = poe_ports

        outlets = _build_outlets(device)
        if outlets:
            hostvars["outlets"] = outlets

        if unifi_name is not None:
            hostvars["unifi_name"] = unifi_name

        groups = ["unifi_devices"]
        group_sources: Dict[str, List[str]] = {}
        _remember_group(groups, group_sources, sanitize_group_name(f"unifi_{dev_type}"), dev_type)

        state = hostvars.get("state")
        if state:
            _remember_group(groups, group_sources, sanitize_group_name(f"device_state_{state}"), state)

        if hostvars.get("upgradable"):
            groups.append("unifi_upgradable")

        if hostvars.get("overheating"):
            groups.append("unifi_overheating")

        if poe_ports and any(port.get("poe_good") for port in poe_ports):
            groups.append("unifi_poe_powered")

        return {
            "hostname": hostname,
            "hostvars": hostvars,
            "groups": groups,
            "group_sources": group_sources,
        }

    def _host_identity(self, hostvars: Dict[str, Any]) -> Tuple[str, str, str]:
        """MAC identity is local to a controller and site, not a friendly name."""
        return (
            hostvars.get("unifi_controller", getattr(self, "url", "")),
            str(hostvars.get("site", self.get_option("site") or "default")),
            re.sub(r"[^a-z0-9]", "", str(hostvars.get("mac", "")).lower()),
        )

    def _existing_host_matches(self, hostname: str, hostvars: Dict[str, Any]) -> bool:
        """Allow static host variables to enrich the same discovered machine."""
        existing = self.inventory.get_host(hostname)
        if existing is None:
            return True
        previous = existing.get_vars()
        if previous.get("unifi_controller"):
            return self._host_identity(previous) == self._host_identity(hostvars)
        if previous.get("mac"):
            return self._host_identity(previous)[1:] == self._host_identity(hostvars)[1:]
        return not previous.get("ansible_host") or previous["ansible_host"] == hostvars.get("ansible_host")

    def _prefer_device_record(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any] | None:
        """Keep the infrastructure device when the same MAC is also a station row.

        Wireless-uplinked access points appear in both /stat/sta and /stat/device.
        Those two host dicts differ, and treating that as a corrupt MAC aborts
        discovery for every host. Two clients, or two devices, still conflict.
        """
        existing_groups = existing.get("groups") or []
        new_groups = new.get("groups") or []
        existing_device = "unifi_devices" in existing_groups
        new_device = "unifi_devices" in new_groups
        existing_client = "unifi_clients" in existing_groups
        new_client = "unifi_clients" in new_groups
        if existing_client and not existing_device and new_device:
            return new
        if new_client and not new_device and existing_device:
            return existing
        return None

    def _warn_collapsed_groups(self, hosts: List[Dict[str, Any]]) -> None:
        """Warn once when different controller names sanitize to one group."""
        sources: Dict[str, List[str]] = {}
        for host in hosts:
            for group, labels in host.get("group_sources", {}).items():
                bucket = sources.setdefault(group, [])
                for label in labels:
                    if label not in bucket:
                        bucket.append(label)
        for group, labels in sorted(sources.items()):
            if len(labels) > 1:
                rendered = ", ".join(repr(label) for label in sorted(labels))
                self.display.warning(f"UniFi group name collision for {group!r} from {rendered}")

    def _assign_hostnames(self, hosts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve every collision before mutating inventory to avoid partial merges."""
        identities: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        unique_hosts = []
        for host in hosts:
            identity = self._host_identity(host["hostvars"])
            if identity[2]:
                if identity in identities:
                    chosen = identities[identity]
                    if host != chosen:
                        preferred = self._prefer_device_record(chosen, host)
                        if preferred is None:
                            raise AnsibleError(f"Conflicting UniFi records for MAC {host['hostvars']['mac']}")
                        if preferred is not chosen:
                            identities[identity] = preferred
                            unique_hosts = [preferred if item is chosen else item for item in unique_hosts]
                    continue
                identities[identity] = host
            unique_hosts.append(host)

        counts: Dict[str, int] = {}
        for host in unique_hosts:
            counts[host["hostname"]] = counts.get(host["hostname"], 0) + 1
        groups = set(self.inventory.groups)
        groups.update(group for host in unique_hosts for group in host.get("groups", []))
        reserved = set(counts) | set(self.inventory.hosts) | groups

        def available(name: str, hostvars: Dict[str, Any]) -> bool:
            return name not in reserved or (
                name not in counts
                and name not in groups
                and name in self.inventory.hosts
                and self._existing_host_matches(name, hostvars)
            )

        assigned = []
        collision_counts: Dict[str, int] = {}
        for host in sorted(unique_hosts, key=lambda item: (item["hostname"], self._host_identity(item["hostvars"]))):
            hostname = host["hostname"]
            collision = (
                counts[hostname] > 1
                or hostname in groups
                or hostname in _IMPLICIT_LOCALHOST
                or not self._existing_host_matches(hostname, host["hostvars"])
            )
            if collision:
                if self.get_option("hostname_collision") == "fail":
                    raise AnsibleError(
                        f"UniFi hostname collision for {hostname!r}; rename the hosts or use hostname_collision: disambiguate"
                    )
                identity = self._host_identity(host["hostvars"])
                if not identity[2]:
                    raise AnsibleError(f"Cannot disambiguate UniFi hostname {hostname!r} without a MAC address")
                resolved = f"{hostname}__{identity[2]}"
                if not available(resolved, host["hostvars"]):
                    digest = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:12]
                    resolved = f"{resolved}__{digest}"
                    index = 2
                    while not available(resolved, host["hostvars"]):
                        resolved = f"{hostname}__{identity[2]}__{digest}_{index}"
                        index += 1
                reserved.add(resolved)
                collision_counts[hostname] = collision_counts.get(hostname, 0) + 1
                host = {**host, "hostname": resolved}
            assigned.append(host)
        for name, count in sorted(collision_counts.items()):
            suffix = "host" if count == 1 else "hosts"
            self.display.warning(f"UniFi hostname collision for {name!r}; disambiguated {count} {suffix}")
        return assigned

    def _populate_inventory(self, hosts: List[Dict[str, Any]]) -> None:
        """Populate Ansible inventory from fetched host dicts."""
        strict = self.get_option("strict")
        filters = parse_filters(self.get_option("filters"))

        selected = []
        for host in hosts:
            hostvars = {key: _inventory_value(value) for key, value in host["hostvars"].items()}
            hostvars["unifi_controller"] = getattr(self, "url", "")
            if filter_host(self, host["hostname"], hostvars, filters):
                selected.append({**host, "hostvars": hostvars})

        self._warn_collapsed_groups(selected)

        for host_data in self._assign_hostnames(selected):
            hostname = host_data["hostname"]
            hostvars = host_data["hostvars"]
            groups = host_data.get("groups", [])
            self.inventory.add_host(hostname)
            for key, value in hostvars.items():
                self.inventory.set_variable(hostname, key, value)

            self._set_composite_vars(self.get_option("compose"), hostvars, hostname, strict=strict)
            self._add_host_to_composed_groups(self.get_option("groups"), hostvars, hostname, strict=strict)
            self._add_host_to_keyed_groups(self.get_option("keyed_groups"), hostvars, hostname, strict=strict)

            for group_name in groups:
                self.inventory.add_group(group_name)
                self.inventory.add_child(group_name, hostname)

    async def _read_with_retry(self, operation):
        """Retry transient reads, never bad credentials or authentication throttling."""
        for attempt in range(3):
            try:
                return await operation()
            except (TimeoutError, BadGateway, ServiceUnavailable, RequestError) as error:
                cause = error
                if isinstance(error, RequestError) and not isinstance(error, (BadGateway, ServiceUnavailable)):
                    cause = error.__context__
                # ClientPayloadError is a truncated body. It is not a connection error,
                # so without this the first partial /stat/sta response aborts discovery.
                transient = isinstance(
                    cause,
                    (
                        BadGateway,
                        ServiceUnavailable,
                        asyncio.TimeoutError,
                        aiohttp.ClientConnectionError,
                        aiohttp.ClientPayloadError,
                    ),
                )
                if isinstance(cause, aiohttp.ClientSSLError) or not transient or attempt == 2:
                    raise
                await asyncio.sleep(attempt + 1)

    async def _fetch_handler_records(self, controller, handler):
        """Validate raw records before aiounifi can skip missing IDs or overwrite duplicates."""
        response = await self._read_with_retry(lambda: controller.request(handler.api_request))
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise AnsibleError("Invalid UniFi inventory response: expected a data list")
        records = {}
        for record in response["data"]:
            mac = record.get("mac") if isinstance(record, dict) else None
            if not isinstance(mac, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
                if self.get_option("strict_records") is not False:
                    raise AnsibleError("Malformed UniFi record: missing or invalid MAC address")
                self.display.warning("Malformed UniFi record: missing or invalid MAC address; skipping")
                continue
            identity = mac.lower()
            if identity in records and record != records[identity]:
                # Conflicting identities cannot be safely selected even in permissive mode.
                raise AnsibleError(f"Conflicting UniFi records for MAC {mac}")
            records[identity] = record
        handler.process_raw(list(records.values()))

    def _append_record(self, hosts, mac, item, builder, *args):
        """Keep malformed records visible and apply the explicit failure policy."""
        try:
            if not isinstance(mac, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
                raise ValueError("invalid MAC address")
            host = builder(mac, item, *args)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as error:
            message = f"Malformed UniFi record {mac!r}: {type(error).__name__}"
            if self.get_option("strict_records") is not False:
                raise AnsibleError(message + "; set strict_records: false to skip it") from error
            self.display.warning(message + "; skipping")
            return
        if host is not None:
            hosts.append(host)

    def _vlan_names_from_response(self, networks_response: Any) -> Dict[int, str]:
        """Map VLAN ids to names, skipping a bad row instead of dropping the rest."""
        vlan_names: Dict[int, str] = {}
        data = networks_response.get("data") if isinstance(networks_response, dict) else None
        if not isinstance(data, list):
            self.display.warning("Unable to fetch VLAN names (invalid response); VLAN IDs are still available")
            return vlan_names
        for network in data:
            if not isinstance(network, dict):
                self.display.warning("Skipping malformed UniFi network record while building VLAN names")
                continue
            vlan_id = network.get("vlan")
            name = network.get("name")
            # A missing id, or 0, is the untagged network rather than a named VLAN.
            if not vlan_id or not name:
                continue
            try:
                vlan_names[int(vlan_id)] = name
            except TypeError, ValueError:
                self.display.warning(f"Skipping UniFi network {name!r} with VLAN id {vlan_id!r}")
        return vlan_names

    def _controller_error(self, error: Exception) -> AnsibleError | None:
        """Translate a controller failure without echoing response bodies.

        Returns None for exceptions this plugin did not raise and does not recognize,
        so a programming error still surfaces with its original traceback.
        """
        if isinstance(error, ControllerRedirect):
            return AnsibleError("UniFi controller redirected the request; redirects are not followed")
        if isinstance(error, LoginRequired):
            message = (
                "Session token expired or invalid; token requires the TOKEN login cookie, not a Network API key"
                if self.token
                else "Authentication failed: check username, password, and totp_secret"
            )
            return AnsibleError(message)
        if isinstance(error, (Forbidden, NoPermission)):
            return AnsibleError("UniFi account is not authorized to read this site's inventory")
        if isinstance(error, TwoFaTokenRequired) or (
            isinstance(error, RequestError) and "no totp_secret configured" in str(error)
        ):
            return AnsibleError("2FA is required; configure totp_secret with the authenticator's shared secret")
        if isinstance(error, TimeoutError) or _is_timeout(error):
            return AnsibleError("UniFi API request timed out; check reachability or increase api_timeout")
        if isinstance(error, AiounifiException):
            message = _login_rate_limit_message(error)
            return AnsibleError(message or f"UniFi API request failed ({type(error).__name__})")
        if isinstance(error, json.JSONDecodeError):
            return AnsibleError(f"UniFi API request failed ({type(error).__name__})")
        return None

    async def _fetch_from_controller(self) -> List[Dict[str, Any]]:
        """Fetch inventory from a UniFi OS controller."""
        from yarl import URL

        hosts: List[Dict[str, Any]] = []
        fetch_clients = not self.get_option("exclude_clients")
        fetch_devices = self.get_option("include_devices") and not self.get_option("exclude_devices")
        if not fetch_clients and not fetch_devices:
            raise AnsibleError("Nothing to fetch from UniFi: enable clients or devices")

        validate_certs = self.get_option("validate_certs")
        timeout = aiohttp.ClientTimeout(total=self.get_option("api_timeout"))
        connector = aiohttp.TCPConnector(ssl=aiohttp_connector_ssl(validate_certs))
        # Controllers commonly use IP origins; aiohttp otherwise rejects their login cookies.
        session = OriginLockedClientSession(
            connector=connector, timeout=timeout, cookie_jar=aiohttp.CookieJar(unsafe=True)
        )
        try:
            parsed = urlsplit(self.url)
            host = parsed.hostname
            # aiounifi builds its HTTPS URL from host/port, including IPv6 brackets.
            if ":" in host:
                host = f"[{host}]"
            config = Configuration(
                session=session,
                host=host,
                port=parsed.port or 443,
                username=self.username,
                password=self.password,
                site=self.get_option("site"),
                ssl_context=aiounifi_configuration_ssl_context(validate_certs),
                totp_secret=self.totp_secret or None,
            )
            controller = Controller(config)
            if self.token:
                # Detection selects /proxy/network and clears cookies, so set TOKEN afterwards.
                await self._read_with_retry(controller.connectivity.check_unifi_os)
                session.cookie_jar.update_cookies({"TOKEN": self.token}, URL(self.url))
            else:
                # Repeating login can lock out the account; retries are restricted to reads.
                await controller.login()
            # aiounifi97 recursively reauthenticates on persistent read401s, resetting
            # its retry flag each login. Disable that path to prevent account lockouts.
            controller.connectivity.can_retry_login = False
            if not controller.connectivity.is_unifi_os:
                raise AnsibleError("This plugin requires a UniFi OS controller")

            if fetch_clients:
                await self._fetch_handler_records(controller, controller.clients)
            if fetch_devices:
                await self._fetch_handler_records(controller, controller.devices)

            vlan_names: Dict[int, str] = {}
            if fetch_clients:
                try:
                    networks_response = await self._read_with_retry(
                        lambda: controller.request(ApiRequest(method="get", path="/rest/networkconf"))
                    )
                except (TimeoutError, AiounifiException, json.JSONDecodeError) as error:
                    # Network names are optional enrichment; discovery can succeed without them.
                    self.display.warning(
                        f"Unable to fetch VLAN names ({type(error).__name__}); VLAN IDs are still available"
                    )
                    networks_response = None
                if networks_response is not None:
                    vlan_names = self._vlan_names_from_response(networks_response)

            current_time = time.time()
            last_seen_threshold = self.get_option("last_seen_minutes") * 60
            if fetch_clients:
                for mac, client in _iter_handler_items(controller.clients):
                    self._append_record(
                        hosts, mac, client, self._build_client_host, vlan_names, current_time, last_seen_threshold
                    )
            if fetch_devices:
                for mac, device in _iter_handler_items(controller.devices):
                    self._append_record(hosts, mac, device, self._build_device_host)
        except AnsibleError:
            raise
        except Exception as error:
            # Do not chain the controller exception: aiounifi puts raw response
            # bytes on ResponseError, and Ansible prints the cause chain.
            translated = self._controller_error(error)
            if translated is None:
                raise
            raise translated from None
        finally:
            await session.close()
        return hosts
