"""Inventory identity and persistent-cache regressions without a live controller."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from ansible.errors import AnsibleError
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import inventory_loader


@pytest.fixture
def plugin():
    result = inventory_loader.get("aioue.network.unifi")
    result.inventory = InventoryData()
    result.url = "https://controller.example"
    result.set_options(
        direct={"plugin": "aioue.network.unifi", "url": result.url, "username": "admin", "password": "secret"}
    )
    return result


def host(name="NAS", mac="aa:bb:cc:dd:ee:01", address="192.0.2.1", groups=None):
    return {
        "hostname": name,
        "hostvars": {"mac": mac, "ansible_host": address, "site": "default"},
        "groups": groups or ["unifi_clients"],
    }


def test_collisions_are_disambiguated_independently_of_fetch_order(plugin):
    records = [host(), host(mac="aa:bb:cc:dd:ee:02", address="192.0.2.2", groups=["unifi_devices"])]
    with patch.object(plugin.display, "warning") as warning:
        plugin._populate_inventory(records)
    names = set(plugin.inventory.hosts)
    assert names == {"NAS__aabbccddee01", "NAS__aabbccddee02"}
    assert warning.call_count == 2
    assert plugin.inventory.get_host("NAS__aabbccddee01").get_vars()["ansible_host"] == "192.0.2.1"
    assert plugin.inventory.get_host("NAS__aabbccddee02") in plugin.inventory.groups["unifi_devices"].hosts
    plugin.inventory = InventoryData()
    plugin._populate_inventory(list(reversed(records)))
    assert set(plugin.inventory.hosts) == names


def test_unique_names_keep_their_existing_spelling(plugin):
    plugin._populate_inventory([host("Living_Room")])
    assert set(plugin.inventory.hosts) == {"Living_Room"}


def test_sanitized_friendly_name_collisions_are_detected(plugin):
    records = []
    for name, mac in [("Living Room", "aa:bb:cc:dd:ee:01"), ("Living_Room", "aa:bb:cc:dd:ee:02")]:
        hostname, _friendly_name = plugin._resolve_client_hostname(mac, SimpleNamespace(name=name), "name")
        records.append(host(hostname, mac=mac))
    plugin._populate_inventory(records)
    assert set(plugin.inventory.hosts) == {"Living_Room__aabbccddee01", "Living_Room__aabbccddee02"}


def test_disambiguated_names_are_reused_for_existing_same_identity(plugin):
    records = [host(), host(mac="aa:bb:cc:dd:ee:02")]
    plugin._populate_inventory(records)
    plugin._populate_inventory(records)
    assert set(plugin.inventory.hosts) == {"NAS__aabbccddee01", "NAS__aabbccddee02"}


def test_filtered_hosts_do_not_cause_name_collisions(plugin, tmp_path):
    plugin.loader = DataLoader()
    source = tmp_path / "unifi.yml"
    source.write_text(
        yaml.safe_dump(
            {"plugin": plugin.NAME, "url": plugin.url, "filters": [{"exclude": "mac == 'aa:bb:cc:dd:ee:02'"}]}
        )
    )
    config = plugin.loader.load_from_file(str(source), trusted_as_template=True)
    plugin.set_options(direct=config)
    plugin._populate_inventory([host(), host(mac="aa:bb:cc:dd:ee:02")])
    assert set(plugin.inventory.hosts) == {"NAS"}


def test_collision_fail_policy_does_not_partially_populate_inventory(plugin):
    plugin.set_options(direct={"plugin": "aioue.network.unifi", "url": plugin.url, "hostname_collision": "fail"})
    with pytest.raises(AnsibleError, match="hostname collision"):
        plugin._populate_inventory([host("Unique", mac="aa:bb:cc:dd:ee:03"), host(), host(mac="aa:bb:cc:dd:ee:02")])
    assert not plugin.inventory.hosts


@pytest.mark.parametrize("name", ["all", "ungrouped", "unifi_clients"])
def test_group_names_cannot_be_used_as_hostnames(plugin, name):
    plugin._populate_inventory([host(name)])
    assert set(plugin.inventory.hosts) == {f"{name}__aabbccddee01"}


def test_disambiguation_reserves_existing_unique_hostnames(plugin):
    records = [host(), host(mac="aa:bb:cc:dd:ee:02"), host("NAS__aabbccddee01", mac="aa:bb:cc:dd:ee:03")]
    plugin._populate_inventory(records)
    assert len(plugin.inventory.hosts) == 3
    assert "NAS__aabbccddee01" in plugin.inventory.hosts
    assert plugin.inventory.get_host("NAS__aabbccddee01").get_vars()["mac"] == "aa:bb:cc:dd:ee:03"
    assert any(name.startswith("NAS__aabbccddee01__") for name in plugin.inventory.hosts)


@pytest.mark.parametrize(
    "static_vars", [{"ansible_user": "tom"}, {"ansible_host": "192.0.2.1"}, {"mac": "AA:BB:CC:DD:EE:01"}]
)
def test_matching_static_inventory_can_enrich_discovered_hosts(plugin, static_vars):
    plugin.inventory.add_host("NAS")
    for key, value in static_vars.items():
        plugin.inventory.set_variable("NAS", key, value)
    plugin._populate_inventory([host()])
    assert set(plugin.inventory.hosts) == {"NAS"}
    assert plugin.inventory.get_host("NAS").get_vars()["ansible_host"] == "192.0.2.1"
    if "ansible_user" in static_vars:
        assert plugin.inventory.get_host("NAS").get_vars()["ansible_user"] == "tom"


def test_conflicting_existing_inventory_host_is_preserved(plugin):
    plugin.inventory.add_host("NAS")
    plugin.inventory.set_variable("NAS", "ansible_host", "192.0.2.99")
    plugin._populate_inventory([host()])
    assert set(plugin.inventory.hosts) == {"NAS", "NAS__aabbccddee01"}
    assert plugin.inventory.get_host("NAS").get_vars()["ansible_host"] == "192.0.2.99"


def test_same_mac_on_another_controller_does_not_merge(plugin):
    plugin._populate_inventory([host()])
    plugin.url = "https://other-controller.example"
    plugin._populate_inventory([host(address="192.0.2.10")])
    assert set(plugin.inventory.hosts) == {"NAS", "NAS__aabbccddee01"}
    assert plugin.inventory.get_host("NAS").get_vars()["ansible_host"] == "192.0.2.1"


def test_same_mac_on_another_site_gets_a_distinct_stable_name(plugin):
    second = host(address="192.0.2.2")
    second["hostvars"]["site"] = "other"
    records = [host(), second]
    plugin._populate_inventory(records)
    names = set(plugin.inventory.hosts)
    assert len(names) == 2
    assert "NAS__aabbccddee01" in names
    assert {entry.get_vars()["site"] for entry in plugin.inventory.hosts.values()} == {"default", "other"}
    plugin.inventory = InventoryData()
    plugin._populate_inventory(list(reversed(records)))
    assert set(plugin.inventory.hosts) == names


def test_identical_duplicate_records_are_deduplicated(plugin):
    plugin._populate_inventory([host(), host()])
    assert set(plugin.inventory.hosts) == {"NAS"}


def test_conflicting_same_identity_records_fail_before_population(plugin):
    with pytest.raises(AnsibleError, match="Conflicting UniFi records"):
        plugin._populate_inventory([host(), host(address="192.0.2.2")])
    assert not plugin.inventory.hosts


@pytest.fixture
def cached_source(tmp_path):
    config = {
        "plugin": "aioue.network.unifi",
        "url": "https://controller.example",
        "username": "admin",
        "password": "secret-password",
        "site": "default",
        "cache": True,
        "cache_plugin": "jsonfile",
        "cache_connection": str(tmp_path / "cache"),
        "include_devices": True,
    }
    path = tmp_path / "inventory.unifi.yml"

    def write(changes=None):
        path.write_text(yaml.safe_dump({**config, **(changes or {})}), encoding="utf-8")
        return path

    write()
    return path, write


def parse_source(plugin, path: Path, cache=True):
    inventory = InventoryData()
    plugin.parse(inventory, DataLoader(), str(path), cache=cache)
    plugin.update_cache_if_changed()
    return inventory


def test_real_config_parse_cache_hit_refresh_and_secret_exclusion(plugin, cached_source):
    path, _write = cached_source
    fetch = AsyncMock(return_value=[host()])
    with patch.object(plugin, "_fetch_from_controller", fetch):
        first = parse_source(plugin, path)
        second = parse_source(plugin, path)
        assert fetch.await_count == 1
        assert first.get_host("NAS").get_vars() == second.get_host("NAS").get_vars()
        parse_source(plugin, path, cache=False)
        assert fetch.await_count == 2
    cached = plugin._cache[plugin.get_cache_key(str(path))]
    assert cached["version"] == 1
    assert "secret-password" not in json.dumps(cached)


@pytest.mark.parametrize(
    "change",
    [
        {"url": "https://other-controller.example"},
        {"site": "other"},
        {"hostname": "mac"},
        {"include_devices": False},
        {"exclude_clients": True},
        {"exclude_devices": True},
        {"last_seen_minutes": 60},
        {"allow_historical_addresses": False},
        {"strict_records": False},
    ],
)
def test_cache_invalidates_when_effective_configuration_changes(plugin, cached_source, change):
    path, write = cached_source
    fetch = AsyncMock(return_value=[host()])
    with patch.object(plugin, "_fetch_from_controller", fetch):
        parse_source(plugin, path)
        write(change)
        parse_source(plugin, path)
    assert fetch.await_count == 2


@pytest.mark.parametrize(
    "old_entry",
    [[host()], {"version": 0, "hosts": [host()]}, {"version": 1, "fingerprint": "stale", "hosts": [host()]}],
)
def test_legacy_or_mismatched_cache_entries_refresh(plugin, cached_source, old_entry):
    path, _write = cached_source
    fetch = AsyncMock(return_value=[host()])
    with patch.object(plugin, "_fetch_from_controller", fetch):
        parse_source(plugin, path)
        plugin._cache[plugin.get_cache_key(str(path))] = deepcopy(old_entry)
        plugin.update_cache_if_changed()
        parse_source(plugin, path)
    assert fetch.await_count == 2


def test_disabling_cache_always_fetches(plugin, cached_source):
    path, write = cached_source
    write({"cache": False})
    fetch = AsyncMock(return_value=[host()])
    with patch.object(plugin, "_fetch_from_controller", fetch):
        plugin.parse(InventoryData(), DataLoader(), str(path))
        # No cache plugin is loaded when cache is disabled.
        plugin.parse(InventoryData(), DataLoader(), str(path))
    assert fetch.await_count == 2
