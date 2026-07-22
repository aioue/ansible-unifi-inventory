"""Light unit tests for the UniFi inventory plugin (no live controller)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader

from ansible_collections.aioue.network.plugins.inventory.unifi import (
    InventoryModule,
    _inventory_value,
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
    import enum

    class SampleState(enum.IntEnum):
        CONNECTED = 1

    assert _inventory_value(SampleState.CONNECTED) == "CONNECTED"


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
            with patch.object(plugin, "_run_async", side_effect=fake_run_async):
                plugin.parse(plugin.inventory, loader, str(inventory_file), cache=False)

    assert "laptop" in plugin.inventory.hosts
    assert plugin.inventory.get_host("laptop").get_vars()["ansible_host"] == "192.168.1.20"
    assert "unifi_wired_clients" in plugin.inventory.groups
