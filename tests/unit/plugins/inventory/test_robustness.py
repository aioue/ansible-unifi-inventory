"""Reject unsafe settings and malformed records without hiding useful inventory."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiounifi.errors import BadGateway, Forbidden, LoginRequired, RequestError, ServiceUnavailable
from ansible.errors import AnsibleError
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import inventory_loader

from ansible_collections.aioue.network.plugins.inventory.unifi import InventoryModule, _iter_handler_items

MAC = "aa:bb:cc:dd:ee:ff"
MODULE = "ansible_collections.aioue.network.plugins.inventory.unifi"


@pytest.fixture
def plugin():
    inventory = InventoryModule()
    options = {"hostname": "name", "site": "default", "strict_records": True, "allow_historical_addresses": True}
    inventory.get_option = options.get
    inventory.display = MagicMock()
    inventory.options = options
    return inventory


def client(**changes):
    return SimpleNamespace(**({"name": "NAS", "last_seen": 1000, "ip": "192.168.1.2", "raw": {}} | changes))


def append_client(plugin, record):
    hosts = []
    plugin._append_record(hosts, MAC, record, plugin._build_client_host, {}, 1000, 1800)
    return hosts


@pytest.mark.parametrize(
    "settings",
    [
        {"url": value}
        for value in (
            "http://controller.test",
            "https://user:password@controller.test",
            "https://controller.test/path",
            "https://controller.test?site=other",
            "https://controller.test#fragment",
            "https://controller.test:0",
            "https://controller.test:65536",
            "https://controller.test:abc",
            "https://",
        )
    ]
    + [{"api_timeout": 0}, {"api_timeout": -1}, {"last_seen_minutes": -1}, {"site": "../default"}, {"site": ""}],
)
def test_invalid_settings_fail_before_controller_access(tmp_path, settings):
    path = tmp_path / "test.unifi.yml"
    path.write_text(
        json.dumps({"plugin": "aioue.network.unifi", "url": "https://controller.test", "token": "session"} | settings)
    )
    inventory = inventory_loader.get("aioue.network.unifi")
    with patch.object(inventory, "_fetch_from_controller", new_callable=AsyncMock) as fetch:
        with pytest.raises(AnsibleError):
            inventory.parse(InventoryData(), DataLoader(), str(path))
        fetch.assert_not_called()


@pytest.mark.parametrize("address", ["FE80::1", "fe80::1%eth0", "::", "::1", "FF02::1"])
def test_unusable_ipv6_does_not_become_connection_address(plugin, address):
    assert append_client(plugin, client(ip=None, raw={"ipv6_addresses": [address]})) == []


def test_usable_ipv6_is_normalized_and_historical_policy_is_respected(plugin):
    plugin.options["allow_historical_addresses"] = False
    record = client(ip=None, raw={"last_ip": "192.168.1.8", "fixed_ip": "192.168.1.9"})
    assert append_client(plugin, record) == []
    record.raw["ipv6_addresses"] = ["FE80::1", "FD00::ABCD"]
    hostvars = append_client(plugin, record)[0]["hostvars"]
    assert hostvars["ansible_host"] == "fd00::abcd"
    assert hostvars["address_source"] == "ipv6"
    record.ip = "192.168.1.10"
    assert append_client(plugin, record)[0]["hostvars"]["ansible_host"] == "192.168.1.10"


@pytest.mark.parametrize(
    "changes",
    [
        {"ip": "999.1.2.3"},
        {"ip": 123},
        {"raw": {"ipv6_addresses": [None]}},
        {"raw": {"ipv6_addresses": ["not-an-address"]}},
        {"raw": {"ipv6_addresses": "fd00::1"}},
        {"last_seen": float("nan")},
        {"last_seen": float("inf")},
        {"last_seen": -1},
        {"raw": {"vlan": 5000}},
    ],
)
@pytest.mark.parametrize("strict", [True, False])
def test_malformed_clients_follow_explicit_failure_policy(plugin, changes, strict):
    plugin.options["strict_records"] = strict
    if strict:
        with pytest.raises(AnsibleError, match="Malformed UniFi record"):
            append_client(plugin, client(**changes))
        plugin.display.warning.assert_not_called()
    else:
        assert append_client(plugin, client(**changes)) == []
        plugin.display.warning.assert_called_once()
        assert "skipping" in plugin.display.warning.call_args.args[0]


class OptionalDevice(SimpleNamespace):
    @property
    def upgradable(self):
        return self.raw["upgradable"]

    @property
    def overheating(self):
        value = self.raw.get("overheating")
        assert isinstance(value, bool)
        return value


def test_missing_optional_device_properties_preserve_device(plugin):
    device = OptionalDevice(ip="192.168.1.20", name="Switch", raw={})
    host = plugin._build_device_host(MAC, device)
    assert host["hostvars"]["ansible_host"] == device.ip
    assert "upgradable" not in host["hostvars"]
    assert "overheating" not in host["hostvars"]
    device.raw["overheating"] = "invalid"
    with pytest.raises(AnsibleError, match="Malformed UniFi record"):
        plugin._append_record([], MAC, device, plugin._build_device_host)


def request_error(cause):
    error = RequestError("transport error")
    error.__context__ = cause
    return error


@pytest.mark.parametrize(
    "failure", [BadGateway(), ServiceUnavailable(), TimeoutError(), request_error(aiohttp.ClientConnectionError())]
)
def test_transient_reads_recover_and_have_bounded_retries(plugin, failure):
    operation = AsyncMock(side_effect=[failure, "response"])
    with patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock) as sleep:
        assert asyncio.run(plugin._read_with_retry(operation)) == "response"
        assert operation.await_count == 2
        sleep.assert_awaited_once()
    operation = AsyncMock(side_effect=failure)
    with patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock) as sleep:
        with pytest.raises(type(failure)):
            asyncio.run(plugin._read_with_retry(operation))
        assert operation.await_count == 3
        assert sleep.await_count == 2


@pytest.mark.parametrize(
    "failure",
    [
        LoginRequired(),
        Forbidden(),
        request_error(aiohttp.ClientSSLError(None, OSError("certificate"))),
        RequestError("invalid response"),
    ],
)
def test_authentication_and_certificate_failures_are_not_retried(plugin, failure):
    operation = AsyncMock(side_effect=failure)
    with patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock) as sleep:
        with pytest.raises(type(failure)):
            asyncio.run(plugin._read_with_retry(operation))
        operation.assert_awaited_once()
        sleep.assert_not_awaited()


def test_unsupported_handler_is_an_error():
    with pytest.raises(AnsibleError, match="no supported item iterator"):
        _iter_handler_items(object())
