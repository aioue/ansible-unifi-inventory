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
    return SimpleNamespace(
        **({"name": "NAS", "last_seen": 1000, "ip": "192.168.1.2", "is_wired": False, "raw": {}} | changes)
    )


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
    + [
        {"api_timeout": 0},
        {"api_timeout": -1},
        {"last_seen_minutes": -1},
        {"last_seen_minutes": 0},
        {"site": "../default"},
        {"site": ""},
    ],
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
    "failure",
    [
        BadGateway(),
        ServiceUnavailable(),
        TimeoutError(),
        request_error(aiohttp.ClientConnectionError()),
        request_error(aiohttp.ClientPayloadError()),
    ],
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


def test_current_ipv6_beats_historical_ipv4_and_drops_unusable_addresses(plugin):
    record = client(ip=None, raw={"last_ip": "192.0.2.50", "ipv6_addresses": ["fe80::1", "2001:db8::10"]})
    hostvars = append_client(plugin, record)[0]["hostvars"]
    assert hostvars["ansible_host"] == "2001:db8::10"
    assert hostvars["address_source"] == "ipv6"
    assert hostvars["ipv6_addresses"] == ["2001:db8::10"]


def test_ipv6_in_the_ip_field_beats_historical_ipv4(plugin):
    record = client(ip="2001:db8::10", raw={"last_ip": "192.0.2.8"})
    hostvars = append_client(plugin, record)[0]["hostvars"]
    assert hostvars["ansible_host"] == "2001:db8::10"
    assert hostvars["address_source"] == "ipv6"


def test_scoped_ipv6_is_published_without_the_zone(plugin):
    record = client(ip=None, raw={"ipv6_addresses": ["fd00::ABCD%en0"]})
    hostvars = append_client(plugin, record)[0]["hostvars"]
    assert hostvars["ansible_host"] == "fd00::abcd"
    assert hostvars["ipv6_addresses"] == ["fd00::abcd"]


def test_wrong_family_historical_address_uses_the_next_source(plugin):
    record = client(ip=None, raw={"last_ip": "2001:db8::50", "fixed_ip": "192.0.2.10"})
    hostvars = append_client(plugin, record)[0]["hostvars"]
    assert hostvars["ansible_host"] == "192.0.2.10"
    assert hostvars["address_source"] == "fixed_ip"


def test_loopback_fixed_ip_is_not_published(plugin):
    record = client(raw={"ip": "192.168.1.2", "fixed_ip": "127.0.0.1"})
    assert "fixed_ip" not in append_client(plugin, record)[0]["hostvars"]


def test_sparse_aiounifi_client_omits_sentinel_defaults(plugin):
    from aiounifi.models.client import Client

    record = Client({"mac": MAC, "ip": "192.168.1.9", "last_seen": 1000, "name": "📺", "is_wired": True})
    host = append_client(plugin, record)[0]
    assert host["hostname"] == "aa-bb-cc-dd-ee-ff"
    for key in ("first_seen", "association_time", "latest_association_time", "wired_rate_mbps"):
        assert key not in host["hostvars"]


def test_missing_name_without_oui_uses_underscore_mac(plugin):
    host = append_client(plugin, client(name=None))[0]
    assert host["hostname"] == "aa_bb_cc_dd_ee_ff"
    assert "unifi_name" not in host["hostvars"]


def test_missing_is_wired_follows_strict_records(plugin):
    from aiounifi.models.client import Client

    record = Client({"mac": MAC, "ip": "192.168.1.9", "last_seen": 1000, "name": "phone"})
    with pytest.raises(AnsibleError, match="Malformed UniFi record"):
        append_client(plugin, record)
    plugin.options["strict_records"] = False
    plugin.display.warning.reset_mock()
    assert append_client(plugin, record) == []


def test_missing_last_seen_follows_strict_records(plugin):
    from aiounifi.models.client import Client

    record = Client({"mac": MAC, "ip": "192.168.1.9", "name": "phone", "is_wired": True})
    with pytest.raises(AnsibleError, match="Malformed UniFi record"):
        append_client(plugin, record)
    plugin.options["strict_records"] = False
    plugin.display.warning.reset_mock()
    assert append_client(plugin, record) == []


def test_sparse_aiounifi_device_reports_adoption_and_omits_missing_fields(plugin):
    from aiounifi.models.device import Device

    device = Device({"mac": MAC, "ip": "192.168.1.2", "name": "AP", "type": "uap", "adopted": True})
    host = plugin._build_device_host(MAC, device)
    assert host is not None
    assert host["hostvars"]["adopted"] is True
    for key in ("model", "firmware_version", "uptime", "upgradable", "has_fan", "cpu_percent"):
        assert key not in host["hostvars"]


def test_unnamed_device_without_model_uses_device_prefix(plugin):
    from aiounifi.models.device import Device

    device = Device({"mac": MAC, "ip": "192.168.1.2", "type": "uap"})
    host = plugin._build_device_host(MAC, device)
    assert host is not None
    assert host["hostname"] == "device_ddeeff"


def test_non_dict_system_stats_fails_strict_records(plugin):
    from aiounifi.models.device import Device

    device = Device(
        {
            "mac": MAC,
            "ip": "192.168.1.2",
            "name": "AP",
            "type": "uap",
            "model": "U6",
            "version": "1",
            "system-stats": "bad",
        }
    )
    with pytest.raises(AnsibleError, match="Malformed UniFi record"):
        plugin._append_record([], MAC, device, plugin._build_device_host)


def test_non_integer_station_count_fails_strict_records(plugin):
    from aiounifi.models.device import Device

    device = Device(
        {
            "mac": MAC,
            "ip": "192.168.1.2",
            "name": "AP",
            "type": "uap",
            "model": "U6",
            "version": "1",
            "user-num_sta": "8",
        }
    )
    with pytest.raises(AnsibleError, match="Malformed UniFi record"):
        plugin._append_record([], MAC, device, plugin._build_device_host)


def test_one_bad_network_row_keeps_the_other_vlan_names(plugin):
    names = plugin._vlan_names_from_response(
        {
            "data": [
                {"vlan": 10, "name": "Servers"},
                {"vlan": "nope", "name": "Bad"},
                "not-a-dict",
                {"vlan": 20, "name": "IoT"},
            ]
        }
    )
    assert names == {10: "Servers", 20: "IoT"}
    assert plugin.display.warning.call_count == 2
    plugin.display.warning.reset_mock()
    assert plugin._vlan_names_from_response({}) == {}
    assert "invalid response" in plugin.display.warning.call_args.args[0]


def test_collapsed_group_names_warn_once(plugin):
    plugin.inventory = InventoryData()

    def build(essid, mac):
        record = client(name=essid, is_wired=False, essid=essid)
        hosts = []
        plugin._append_record(hosts, mac, record, plugin._build_client_host, {}, 1000, 1800)
        return hosts[0]

    plugin.display.warning.reset_mock()
    plugin._warn_collapsed_groups([build("Home WiFi", "aa:bb:cc:dd:ee:01"), build("home_wifi", "aa:bb:cc:dd:ee:02")])
    assert plugin.display.warning.call_count == 1
    assert "ssid_home_wifi" in plugin.display.warning.call_args.args[0]


def test_controller_errors_do_not_echo_response_bodies(plugin):
    from aiounifi.errors import NoPermission, ResponseError

    plugin.token = ""
    wrapped = RequestError("wrapped")
    wrapped.__context__ = TimeoutError("stall")
    timeout = plugin._controller_error(wrapped)
    assert "api_timeout" in str(timeout)
    assert "stall" not in str(timeout)
    assert "authorized" in str(plugin._controller_error(NoPermission("secret-body")))
    throttled = plugin._controller_error(ResponseError("Call https://controller received 429: b'secret-body'"))
    assert "rate limit" not in str(throttled).lower()
    assert "secret-body" not in str(throttled)
    try:
        json.loads("{")
    except json.JSONDecodeError as error:
        decoded = plugin._controller_error(error)
    assert "JSONDecodeError" in str(decoded)
    sso = plugin._controller_error(RequestError("SSO MFA required but no totp_secret configured"))
    assert "totp_secret" in str(sso)
    assert "SSO MFA" not in str(sso)


def test_run_async_propagates_keyboard_interrupt(plugin):
    async def boom():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        plugin._run_async(boom())


def test_session_does_not_follow_login_redirect():
    from aiohttp import web

    from ansible_collections.aioue.network.plugins.inventory.unifi import (
        ControllerRedirect,
        OriginLockedClientSession,
    )

    async def scenario():
        followed = {"count": 0}

        async def login(_request):
            raise web.HTTPTemporaryRedirect(location="http://127.0.0.1:9/collect")

        async def collect(_request):
            followed["count"] += 1
            return web.json_response({})

        app = web.Application()
        app.router.add_post("/login", login)
        app.router.add_post("/collect", collect)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with OriginLockedClientSession() as session:
                # aiounifi calls session.request, not session.post. post() is the
                # inner ClientSession method and would follow the redirect.
                with pytest.raises(ControllerRedirect):
                    async with session.request(
                        "POST", f"http://127.0.0.1:{port}/login", json={"password": "secret"}
                    ) as response:
                        await response.read()
                assert followed["count"] == 0
                async with session.request(
                    "POST",
                    f"http://127.0.0.1:{port}/login",
                    json={"password": "secret"},
                    allow_redirects=False,
                ) as response:
                    assert response.status == 307
                assert followed["count"] == 0
        finally:
            await runner.cleanup()

    asyncio.run(scenario())
