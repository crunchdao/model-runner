"""
Tests for the gateway auth interceptor's file-based cert loading.
"""
import json
import os
import time

import pytest

from model_runner.security.gateway_auth import GatewayAuthError
from model_runner.security.gateway_auth_interceptor import GatewayAuthServerInterceptor


def _write_cert_file(path, cert_hashes):
    """Write a cert file matching the format produced by the host cert poller."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(
            {
                "cert_hashes": cert_hashes,
                "updated_at": "2026-01-01T00:00:00Z",
            },
            f,
        )


class TestCertFileLoading:
    """Test that the interceptor reads cert hashes from the mounted file."""

    def test_loads_hashes_from_file(self, tmp_path):
        cert_file = str(tmp_path / "certs.json")
        _write_cert_file(cert_file, ["aabb1122", "ccdd3344"])

        interceptor = GatewayAuthServerInterceptor(
            cert_file=cert_file,
        )
        hashes = interceptor._get_cert_hashes()
        assert hashes == {"aabb1122", "ccdd3344"}

    def test_missing_file_raises(self, tmp_path):
        cert_file = str(tmp_path / "nonexistent.json")

        with pytest.raises(GatewayAuthError, match="not found"):
            GatewayAuthServerInterceptor(
                cert_file=cert_file,
            )

    def test_empty_hashes_raises(self, tmp_path):
        cert_file = str(tmp_path / "certs.json")
        _write_cert_file(cert_file, [])

        with pytest.raises(GatewayAuthError, match="No cert hashes"):
            GatewayAuthServerInterceptor(
                cert_file=cert_file,
            )

    def test_refreshes_after_ttl(self, tmp_path):
        cert_file = str(tmp_path / "certs.json")
        _write_cert_file(cert_file, ["aabb1122"])

        interceptor = GatewayAuthServerInterceptor(
            cert_file=cert_file,
        )
        assert interceptor._get_cert_hashes() == {"aabb1122"}

        # Update the file with a new hash
        _write_cert_file(cert_file, ["aabb1122", "newcert99"])

        # Should still return cached value (TTL not expired)
        assert interceptor._get_cert_hashes() == {"aabb1122"}

        # Force TTL expiry
        interceptor._cert_hashes_read_at = 0
        assert interceptor._get_cert_hashes() == {"aabb1122", "newcert99"}

    def test_lowercases_hashes(self, tmp_path):
        cert_file = str(tmp_path / "certs.json")
        _write_cert_file(cert_file, ["AABB1122", "CcDd3344"])

        interceptor = GatewayAuthServerInterceptor(
            cert_file=cert_file,
        )
        assert interceptor._get_cert_hashes() == {"aabb1122", "ccdd3344"}

    def test_uses_cached_on_file_read_error(self, tmp_path):
        cert_file = str(tmp_path / "certs.json")
        _write_cert_file(cert_file, ["aabb1122"])

        interceptor = GatewayAuthServerInterceptor(
            cert_file=cert_file,
        )
        assert interceptor._get_cert_hashes() == {"aabb1122"}

        # Delete the file and force TTL expiry
        os.unlink(cert_file)
        interceptor._cert_hashes_read_at = 0

        # Should still return the cached value
        assert interceptor._get_cert_hashes() == {"aabb1122"}
