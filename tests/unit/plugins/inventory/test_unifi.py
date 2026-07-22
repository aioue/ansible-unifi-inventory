"""Light unit tests for the UniFi inventory plugin (no live controller)."""

from __future__ import annotations

import enum
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ansible.errors import AnsibleError
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader

from ansible_collections.aioue.network.plugins.inventory.unifi import (
    InventoryModule,
    _build_poe_ports,
    _inventory_value,
    _login_rate_limit_message,
    mac_to_hostname,
    sanitize_group_name,
    sanitize_hostname,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("My Network", "my_network"),
        ("SSID-2.4GHz", "ssid_2_4ghz"),
        ("already_clean", "already_clean"),
        ("UPPER", "upper"),
    ],
)
def test_sanitize_group_name(raw: str, expected: str) -> None:
    assert sanitize_group_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Living Room TV", "Living_Room_TV"),
        ("no-spaces", "no-spaces"),
    ],
)
def test_sanitize_hostname(raw: str, expected: str) -> None:
    assert sanitize_hostname(raw) == expected


def test_mac_to_hostname() -> None:
    assert mac_to_hostname("AA:BB:CC:DD:EE:FF") == "aa-bb-cc-dd-ee-ff"


def test_inventory_value_serializes_enum() -> None:
    class SampleState(enum.IntEnum):
        CONNECTED = 1

    assert _inventory_value(SampleState.CONNECTED) == "CONNECTED"


def test_inventory_value_serializes_nested_structures() -> None:
    class PortState(enum.IntEnum):
        UP = 1

    payload = {
        "ports": [{"state": PortState.UP, "power": "4.5"}],
        "count": 2,
    }
    result = _inventory_value(payload)
    assert result == {"ports": [{"state": "UP", "power": "4.5"}], "count": 2}
    json.dumps(result)


@pytest.mark.parametrize(
    ("error", "expected_substring"),
    [
        (Exception("429 Too Many Requests"), "rate limit"),
        (
            Exception('{"code":"AUTHENTICATION_FAILED_LIMIT_REACHED"}'),
            "rate limit",
        ),
        (Exception("403 Forbidden"), None),
    ],
)
def test_login_rate_limit_message(error: Exception, expected_substring: str | None) -> None:
    message = _login_rate_limit_message(error)
    if expected_substring is None:
        assert message is None
    else:
        assert message is not None
        assert expected_substring in message.lower()


def test_build_poe_ports_filters_non_poe_ports() -> None:
    device = SimpleNamespace(
        port_table=[
            {"port_idx": 1, "name": "Port 1", "port_poe": False, "poe_enable": False},
            {
                "port_idx": 2,
                "name": "Port 2",
                "port_poe": True,
                "poe_enable": True,
                "poe_mode": "auto",
                "poe_power": "4.50",
                "poe_voltage": "48.00",
                "poe_good": True,
                "up": True,
                "is_uplink": False,
            },
        ]
    )

    ports = _build_poe_ports(device)

    assert len(ports) == 1
    assert ports[0]["port_idx"] == 2
    assert ports[0]["poe_mode"] == "auto"
    assert ports[0]["poe_power"] == "4.50"
    json.dumps(ports)


def test_template_option_resolves_jinja() -> None:
    plugin = InventoryModule()
    plugin.templar = SimpleNamespace(
        is_template=lambda value: "{{" in value,
        template=lambda value: "resolved-secret" if "password" in value else value,
    )

    with patch.object(plugin, "get_option", return_value="{{ vault_password }}"):
        assert plugin._template_option("password") == "resolved-secret"


def test_template_option_returns_plain_value() -> None:
    plugin = InventoryModule()

    with patch.object(plugin, "get_option", return_value="plain-password"):
        assert plugin._template_option("password") == "plain-password"


@pytest.mark.parametrize(
    ("mode", "client_attrs", "expected_hostname", "expected_unifi_name"),
    [
        ("mac", {}, "aa-bb-cc-dd-ee-ff", None),
        ("name", {"name": "Living Room TV"}, "Living_Room_TV", "Living Room TV"),
        (
            "name",
            {"oui": "Apple Inc"},
            "Apple_Inc_ddeeff",
            "Apple_Inc_ddeeff",
        ),
    ],
)
def test_resolve_client_hostname(
    mode: str,
    client_attrs: dict,
    expected_hostname: str,
    expected_unifi_name: str | None,
) -> None:
    plugin = InventoryModule()
    client = SimpleNamespace(**client_attrs)
    mac = "aa:bb:cc:dd:ee:ff"

    hostname, unifi_name = plugin._resolve_client_hostname(mac, client, mode)

    assert hostname == expected_hostname
    assert unifi_name == expected_unifi_name


def test_build_client_host_includes_guest_and_firmware_flags() -> None:
    plugin = InventoryModule()
    client = SimpleNamespace(
        last_seen=1_700_000_000,
        ip="192.168.1.50",
        raw={"ip": "192.168.1.50"},
        name="Guest Phone",
        is_wired=False,
        essid="guest",
        is_guest=True,
        blocked=True,
        firmware_version="1.2.3",
        oui="Example Vendor",
    )

    with patch.object(plugin, "get_option", side_effect=lambda key: "name" if key == "hostname" else "default"):
        host = plugin._build_client_host(
            "aa:bb:cc:dd:ee:ff",
            client,
            vlan_names={},
            current_time=1_700_000_100,
            last_seen_threshold=3600,
        )

    assert host is not None
    assert host["hostvars"]["is_guest"] is True
    assert host["hostvars"]["blocked"] is True
    assert host["hostvars"]["firmware_version"] == "1.2.3"


def test_build_device_host_serializes_state_and_poe_ports() -> None:
    class DeviceState(enum.IntEnum):
        CONNECTED = 1

    device = SimpleNamespace(
        ip="192.168.1.252",
        name="Office Switch",
        type="usw",
        model="USW24",
        version="7.0.0",
        id="device-1",
        state=DeviceState.CONNECTED,
        adopted=True,
        upgradable=False,
        overheating=False,
        disabled=False,
        uptime=12345,
        uplink_depth=1,
        user_num_sta=8,
        uplink={"type": "wire", "uplink_mac": "aa:bb:cc:dd:ee:00"},
        system_stats=("12", "34", "12345"),
        port_table=[
            {
                "port_idx": 3,
                "name": "Port 3",
                "port_poe": True,
                "poe_enable": True,
                "poe_mode": "auto",
                "poe_power": "15.4",
                "poe_voltage": "48.0",
                "poe_good": True,
                "up": True,
                "is_uplink": False,
            }
        ],
    )

    plugin = InventoryModule()

    with patch.object(plugin, "get_option", side_effect=lambda key: "name" if key == "hostname" else "default"):
        host = plugin._build_device_host("aa:bb:cc:dd:ee:ff", device)

    assert host is not None
    assert host["hostname"] == "Office_Switch"
    assert host["hostvars"]["state"] == "CONNECTED"
    assert host["hostvars"]["client_count"] == 8
    assert host["hostvars"]["cpu_percent"] == "12"
    assert len(host["hostvars"]["poe_ports"]) == 1
    json.dumps(host["hostvars"])


def test_build_device_host_skips_devices_without_ip() -> None:
    plugin = InventoryModule()
    device = SimpleNamespace(ip=None, name="Offline AP", type="uap", model="U6", version="1")

    with patch.object(plugin, "get_option", return_value="name"):
        assert plugin._build_device_host("aa:bb:cc:dd:ee:ff", device) is None


def test_populate_inventory_serializes_enum_hostvars() -> None:
    class DeviceState(enum.IntEnum):
        CONNECTED = 1

    hosts = [
        {
            "hostname": "switch",
            "hostvars": {
                "ansible_host": "192.168.1.10",
                "state": DeviceState.CONNECTED,
                "poe_ports": [{"poe_mode": "auto", "poe_good": True}],
            },
            "groups": ["unifi_devices", "unifi_usw"],
        }
    ]

    plugin = InventoryModule()
    plugin.inventory = InventoryData()

    def fake_get_option(key):
        return {
            "strict": False,
            "filters": None,
            "compose": {},
            "groups": {},
            "keyed_groups": [],
        }.get(key)

    with patch.object(plugin, "get_option", side_effect=fake_get_option):
        plugin._populate_inventory(hosts)

    vars = plugin.inventory.get_host("switch").get_vars()
    assert vars["state"] == "CONNECTED"
    json.dumps(vars)


def test_verify_file_accepts_unifi_yml(tmp_path: Path) -> None:
    plugin = InventoryModule()
    inventory_file = tmp_path / "unifi.yml"
    inventory_file.write_text("plugin: aioue.network.unifi\n", encoding="utf-8")

    with patch(
        "ansible.plugins.inventory.BaseInventoryPlugin.verify_file",
        return_value=True,
    ):
        assert plugin.verify_file(str(inventory_file)) is True


def test_verify_file_accepts_plugin_directive(tmp_path: Path) -> None:
    plugin = InventoryModule()
    inventory_file = tmp_path / "inventory.yaml"
    inventory_file.write_text(
        "plugin: aioue.network.unifi\nurl: https://example.test\n",
        encoding="utf-8",
    )

    with patch(
        "ansible.plugins.inventory.BaseInventoryPlugin.verify_file",
        return_value=True,
    ):
        assert plugin.verify_file(str(inventory_file)) is True


def test_verify_file_rejects_unrelated_yaml(tmp_path: Path) -> None:
    plugin = InventoryModule()
    inventory_file = tmp_path / "hosts.yml"
    inventory_file.write_text("all:\n  hosts:\n    localhost:\n", encoding="utf-8")

    with patch(
        "ansible.plugins.inventory.BaseInventoryPlugin.verify_file",
        return_value=True,
    ):
        assert plugin.verify_file(str(inventory_file)) is False


def test_populate_inventory_from_fixture() -> None:
    fixture = Path(__file__).resolve().parents[3] / "fixtures" / "unifi_inventory.yml"
    hosts = [
        {
            "hostname": "phone",
            "hostvars": {
                "ansible_host": "192.168.1.50",
                "mac": "11:22:33:44:55:66",
                "is_wired": False,
                "ssid": "Home WiFi",
            },
            "groups": ["unifi_clients", "unifi_wireless_clients", "ssid_home_wifi"],
        }
    ]

    plugin = InventoryModule()
    plugin.inventory = InventoryData()

    def fake_get_option(key):
        return {
            "strict": False,
            "filters": None,
            "compose": {},
            "groups": {},
            "keyed_groups": [],
        }.get(key)

    with patch.object(plugin, "get_option", side_effect=fake_get_option):
        plugin._populate_inventory(hosts)

    assert "phone" in plugin.inventory.hosts
    assert plugin.inventory.get_host("phone").get_vars()["ansible_host"] == "192.168.1.50"
    assert "unifi_clients" in plugin.inventory.groups
    assert "phone" in [h.name for h in plugin.inventory.groups["unifi_clients"].hosts]
    assert fixture.exists()


@patch(
    "ansible_collections.aioue.network.plugins.inventory.unifi.HAS_AIOUNIFI",
    True,
)
def test_parse_with_mocked_controller(tmp_path: Path) -> None:
    inventory_file = tmp_path / "unifi.yml"
    inventory_file.write_text(
        "\n".join(
            [
                "plugin: aioue.network.unifi",
                "url: https://192.168.1.1",
                "token: test-token",
                "verify_ssl: false",
            ]
        ),
        encoding="utf-8",
    )

    mocked_hosts = [
        {
            "hostname": "laptop",
            "hostvars": {
                "ansible_host": "192.168.1.20",
                "mac": "aa:bb:cc:dd:ee:01",
                "is_wired": True,
                "site": "default",
            },
            "groups": ["unifi_clients", "unifi_wired_clients"],
        }
    ]

    plugin = InventoryModule()
    plugin.inventory = InventoryData()
    loader = DataLoader()

    options = {
        "url": "https://192.168.1.1",
        "token": "test-token",
        "username": "",
        "password": "",
        "cache": False,
        "strict": False,
        "filters": None,
        "compose": {},
        "groups": {},
        "keyed_groups": [],
    }

    def fake_run_async(coro):
        coro.close()
        return mocked_hosts

    with patch.object(plugin, "_read_config_data"):
        with patch.object(plugin, "get_option", side_effect=options.get):
            plugin.url = options["url"]
            plugin.username = options["username"]
            plugin.password = options["password"]
            plugin.token = options["token"]
            with patch.object(plugin, "_run_async", side_effect=fake_run_async):
                plugin.parse(plugin.inventory, loader, str(inventory_file), cache=False)

    assert "laptop" in plugin.inventory.hosts
    assert plugin.inventory.get_host("laptop").get_vars()["ansible_host"] == "192.168.1.20"
    assert "unifi_wired_clients" in plugin.inventory.groups
