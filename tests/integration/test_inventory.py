"""Exercise Ansible and aiounifi over HTTPS without access to a real controller."""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import json
import os
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pyotp
import pytest
import yaml
from aiohttp import web
from ansible.module_utils.common.json import get_decoder
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def controller(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    state = SimpleNamespace(
        requests=[],
        logins=0,
        status=200,
        transient_reads=0,
        malformed=False,
        response_mode="",
        require_totp=False,
        secret="JBSWY3DPEHPK3PXP",
        token="fixture-session",
        runner=None,
    )

    async def handle(request):
        state.requests.append((request.method, request.path, request.cookies.get("TOKEN")))
        if request.path == "/":
            return web.Response(text="UniFi OS")
        if request.path == "/api/auth/login":
            state.logins += 1
            payload = await request.json()
            if state.status == 429:
                return web.json_response({"code": "AUTHENTICATION_FAILED_LIMIT_REACHED"}, status=429)
            if payload.get("username") != "test-admin" or payload.get("password") != "test-password":
                return web.json_response({}, status=401)
            if state.require_totp and not pyotp.TOTP(state.secret).verify(
                payload.get("ubic_2fa_token", ""), valid_window=1
            ):
                return web.json_response({"meta": {"rc": "error", "msg": "api.err.Ubic2faTokenRequired"}})
            response = web.json_response({"meta": {"rc": "ok"}})
            response.set_cookie("TOKEN", state.token, secure=True, httponly=True)
            return response
        if not request.path.startswith("/proxy/network/api/s/default/"):
            return web.json_response({}, status=404)
        if request.cookies.get("TOKEN") != state.token:
            return web.json_response({}, status=401)
        if state.status != 200:
            return web.json_response({}, status=state.status)
        if state.transient_reads:
            state.transient_reads -= 1
            return web.json_response({}, status=503)
        if request.path.endswith("/stat/sta"):
            if state.response_mode == "missing_data":
                return web.json_response({"meta": {"rc": "ok"}})
            if state.response_mode == "html":
                return web.Response(text="Login required")
            clients = [
                {
                    "mac": "00:11:22:33:44:55",
                    "name": "NAS",
                    "ip": "192.0.2.10",
                    "last_seen": int(time.time()),
                    "is_wired": True,
                    "sw_mac": "00:11:22:33:44:88",
                    "sw_port": 8,
                    "vlan": 10,
                },
                {
                    "mac": "00:11:22:33:44:66",
                    "name": "NAS",
                    "ip": "192.0.2.11",
                    "last_seen": int(time.time()),
                    "is_wired": True,
                    "vlan": 10,
                },
            ]
            if state.malformed:
                clients[1]["ipv6_addresses"] = [None]
            if state.response_mode == "missing_mac":
                clients[1].pop("mac")
            if state.response_mode == "duplicate_mac":
                clients[1]["mac"] = clients[0]["mac"]
            return web.json_response({"meta": {"rc": "ok"}, "data": clients})
        if request.path.endswith("/stat/device"):
            return web.json_response(
                {
                    "meta": {"rc": "ok"},
                    "data": [
                        {
                            "_id": "test-ap",
                            "mac": "00:11:22:33:44:77",
                            "name": "Office AP",
                            "ip": "192.0.2.12",
                            "type": "uap",
                            "model": "U6",
                            "version": "1.0",
                            "state": 1,
                            "uplink": {},
                        },
                    ],
                }
            )
        if request.path.endswith("/rest/networkconf"):
            return web.json_response({"meta": {"rc": "ok"}, "data": [{"vlan": 10, "name": "Servers"}]})
        return web.json_response({}, status=404)

    loop = asyncio.new_event_loop()
    ready = threading.Event()

    async def start():
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", handle)
        state.runner = web.AppRunner(app)
        await state.runner.setup()
        site = web.TCPSite(state.runner, "127.0.0.1", 0, ssl_context=context)
        await site.start()
        state.url = f"https://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        ready.set()

    def serve():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start())
        loop.run_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(10), "HTTPS fixture failed to start"
    yield state
    asyncio.run_coroutine_threadsafe(state.runner.cleanup(), loop).result(timeout=10)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=10)
    assert not thread.is_alive()
    loop.close()


@pytest.fixture
def inventory_cli(tmp_path, controller):
    config = tmp_path / "ansible.cfg"
    config.write_text("[inventory]\nany_unparsed_is_failed=true\n")
    source = tmp_path / "test.unifi.yml"
    env = {key: value for key, value in os.environ.items() if not key.startswith(("UNIFI_", "ANSIBLE_"))}
    collections = os.environ.get("UNIFI_TEST_COLLECTIONS_PATH", str(ROOT / "tests/_ansible_collections"))
    env.update(ANSIBLE_CONFIG=str(config), ANSIBLE_COLLECTIONS_PATH=collections)

    def run(**options):
        settings = dict(
            plugin="aioue.network.unifi",
            url=controller.url,
            username="test-admin",
            password="test-password",
            validate_certs=False,
        )
        settings.update(options)
        source.write_text(yaml.safe_dump(settings))
        result = subprocess.run(
            [sys.executable, "-m", "ansible.cli.inventory", "-i", str(source), "--list"],
            cwd=tmp_path,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        hosts = {}
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Inventory JSON carries a serialization profile for unsafe strings.
            data = json.loads(result.stdout, cls=get_decoder(data["_meta"]["profile"]))
            hosts = data["_meta"]["hostvars"]
        return result, hosts

    return run


def test_password_inventory_collision_and_constructed_options(controller, inventory_cli):
    result, hosts = inventory_cli(
        include_devices=True,
        compose={"derived": "ip"},
        keyed_groups=[{"key": "vlan | string", "prefix": "vlan"}],
        groups={"servers": "vlan == 10"},
    )
    assert result.returncode == 0, result.stderr
    assert set(hosts) == {"NAS__001122334455", "NAS__001122334466", "Office_AP"}
    assert hosts["NAS__001122334455"]["ansible_host"] == "192.0.2.10"
    assert hosts["NAS__001122334455"]["derived"] == "192.0.2.10"
    assert hosts["NAS__001122334455"]["sw_mac"] == "00:11:22:33:44:88"
    assert hosts["NAS__001122334455"]["switch_port"] == 8
    assert "port" not in hosts["NAS__001122334455"]
    assert "reserved name" not in result.stderr
    assert "UniFi hostname collision" in result.stderr
    groups = json.loads(result.stdout)
    assert set(groups["servers"]["hosts"]) == {"NAS__001122334455", "NAS__001122334466"}
    assert "NAS__001122334455" in groups["vlan_servers"]["hosts"]
    assert controller.logins == 1
    assert all(
        path == "/" or path == "/api/auth/login" or path.startswith("/proxy/network/")
        for _method, path, _cookie in controller.requests
    )


def test_session_token_uses_cookie_without_password_login(controller, inventory_cli):
    result, hosts = inventory_cli(
        token=controller.token, username="{{ missing_variable }}", password="{{ missing_variable }}"
    )
    assert result.returncode == 0, result.stderr
    assert len(hosts) == 2
    assert controller.logins == 0
    assert any(path.endswith("/stat/sta") and token == controller.token for _method, path, token in controller.requests)


def test_password_with_totp(controller, inventory_cli):
    controller.require_totp = True
    result, hosts = inventory_cli(totp_secret=controller.secret)
    assert result.returncode == 0, result.stderr
    assert len(hosts) == 2
    assert controller.logins == 2


def test_collision_fail_and_filters(controller, inventory_cli):
    result, _hosts = inventory_cli(hostname_collision="fail")
    assert result.returncode != 0
    assert "hostname collision" in result.stderr
    result, hosts = inventory_cli(filters=[{"exclude": "ip == '192.0.2.11'"}], hostname_collision="fail")
    assert result.returncode == 0, result.stderr
    assert set(hosts) == {"NAS"}


def test_malformed_record_policy(controller, inventory_cli):
    controller.malformed = True
    result, _hosts = inventory_cli()
    assert result.returncode != 0
    assert "Malformed UniFi record" in result.stderr
    result, hosts = inventory_cli(strict_records=False)
    assert result.returncode == 0, result.stderr
    assert set(hosts) == {"NAS"}
    assert "skipping" in result.stderr


@pytest.mark.parametrize(
    ("status", "expected"), [(401, "Authentication failed"), (403, "not authorized"), (429, "rate limit")]
)
def test_auth_failures_do_not_retry_login(controller, inventory_cli, status, expected):
    controller.status = status
    result, _hosts = inventory_cli(password="wrong" if status == 401 else "test-password")
    assert result.returncode != 0
    assert expected in result.stderr
    assert controller.logins == 1


def test_read_retries_preserve_login(controller, inventory_cli):
    controller.transient_reads = 1
    result, hosts = inventory_cli()
    assert result.returncode == 0, result.stderr
    assert len(hosts) == 2
    assert controller.logins == 1
    assert sum(path.endswith("/stat/sta") for _method, path, _cookie in controller.requests) == 2


def test_read_unauthorized_does_not_reauthenticate(controller, inventory_cli):
    controller.status = 401
    result, _hosts = inventory_cli()
    assert result.returncode != 0
    assert "Authentication failed" in result.stderr
    assert controller.logins == 1
    assert sum(path.endswith("/stat/sta") for _method, path, _cookie in controller.requests) == 1


@pytest.mark.parametrize("mode", ["missing_data", "html", "duplicate_mac"])
def test_invalid_response_cannot_silently_empty_or_overwrite_inventory(controller, inventory_cli, mode):
    controller.response_mode = mode
    result, _hosts = inventory_cli(strict_records=False)
    assert result.returncode != 0
    assert "Invalid UniFi inventory response" in result.stderr or "Conflicting UniFi records" in result.stderr


def test_missing_mac_obeys_record_policy(controller, inventory_cli):
    controller.response_mode = "missing_mac"
    result, _hosts = inventory_cli()
    assert result.returncode != 0
    assert "missing or invalid MAC" in result.stderr
    result, hosts = inventory_cli(strict_records=False)
    assert result.returncode == 0, result.stderr
    assert set(hosts) == {"NAS"}
    assert "skipping" in result.stderr


def test_invalid_session_and_tls_validation(controller, inventory_cli):
    result, _hosts = inventory_cli(token="invalid-session")
    assert result.returncode != 0
    assert "Session token expired or invalid" in result.stderr
    result, _hosts = inventory_cli(validate_certs=True)
    assert result.returncode != 0
    assert controller.logins == 0


def test_persistent_cache_reuses_then_refreshes(controller, inventory_cli, tmp_path):
    options = dict(
        cache=True,
        cache_plugin="ansible.builtin.jsonfile",
        cache_connection=str(tmp_path / "cache"),
        cache_timeout=3600,
    )
    result, hosts = inventory_cli(**options)
    assert result.returncode == 0, result.stderr
    request_count = len(controller.requests)
    result, cached = inventory_cli(**options)
    assert result.returncode == 0, result.stderr
    assert hosts == cached
    assert len(controller.requests) == request_count
    result, renamed = inventory_cli(**options, hostname="mac")
    assert result.returncode == 0, result.stderr
    assert set(renamed) == {"00-11-22-33-44-55", "00-11-22-33-44-66"}
    assert len(controller.requests) > request_count
