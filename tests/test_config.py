import argparse

import pytest

from app.config import AppConfig, default_device_name, default_port


class TestDefaultDeviceName:
    def test_fqdn_is_truncated_at_the_first_dot(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "box.local")
        assert default_device_name() == "box"

    def test_bare_hostname_passes_through(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "box")
        assert default_device_name() == "box"


class TestDefaultPort:
    def test_reads_the_env_var(self, monkeypatch):
        monkeypatch.setenv("NETWORK_PORT", "1234")
        assert default_port() == 1234

    def test_falls_back_to_9999(self, monkeypatch):
        monkeypatch.delenv("NETWORK_PORT", raising=False)
        assert default_port() == 9999


class TestCreate:
    def test_resolves_defaults(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "box.local")
        monkeypatch.delenv("NETWORK_PORT", raising=False)
        config = AppConfig.create()
        assert config.device_name == "box"
        assert config.port == 9999
        assert config.poll_interval == 0.25
        assert config.discovery_interval == 30.0
        assert config.use_redis is True

    def test_explicit_values_win(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "box")
        monkeypatch.setenv("NETWORK_PORT", "1234")
        config = AppConfig.create(port=5555, device_name="laptop")
        assert config.port == 5555
        assert config.device_name == "laptop"

    def test_is_frozen(self):
        config = AppConfig.create(port=1, device_name="a")
        with pytest.raises(Exception):
            config.port = 2


class TestFromArgs:
    def _args(self, **overrides):
        base = dict(port=9999, name=None, poll_interval=0.25,
                    discovery_interval=30.0, no_redis=False,
                    approval_ui=False, approval_api_host="127.0.0.1",
                    approval_api_port=8787,
                    approval_cors_origin="http://localhost:3000")
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_no_redis_inverts_to_use_redis(self):
        assert AppConfig.from_args(self._args(no_redis=True)).use_redis is False
        assert AppConfig.from_args(
            self._args(no_redis=False)).use_redis is True

    def test_maps_the_remaining_fields(self):
        config = AppConfig.from_args(self._args(
            port=1234, name="laptop", poll_interval=0.5, discovery_interval=10.0))
        assert (config.port, config.device_name) == (1234, "laptop")
        assert (config.poll_interval, config.discovery_interval) == (0.5, 10.0)

    def test_missing_name_resolves_the_default(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "box.local")
        assert AppConfig.from_args(self._args()).device_name == "box"


class TestApprovalUiFlag:
    def test_defaults_to_off(self):
        config = AppConfig.create(port=1, device_name="a")
        assert config.approval_ui is False
        assert config.approval_api_host == "127.0.0.1"
        assert config.approval_api_port == 8787
        assert config.approval_cors_origin == "http://localhost:3000"

    def test_from_args_maps_approval_fields(self):
        args = TestFromArgs()._args(
            approval_ui=True, approval_api_host="0.0.0.0",
            approval_api_port=9001,
            approval_cors_origin="http://localhost:5173")
        config = AppConfig.from_args(args)
        assert config.approval_ui is True
        assert config.approval_api_host == "0.0.0.0"
        assert config.approval_api_port == 9001
        assert config.approval_cors_origin == "http://localhost:5173"

    def test_from_args_defaults_match_create_defaults(self):
        config = AppConfig.from_args(TestFromArgs()._args())
        assert config.approval_ui is False
        assert config.approval_api_host == "127.0.0.1"
        assert config.approval_api_port == 8787
        assert config.approval_cors_origin == "http://localhost:3000"
