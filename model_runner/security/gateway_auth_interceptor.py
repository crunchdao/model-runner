"""
gRPC server interceptor for gateway auth.

Extracts the signed token + public key from request metadata, checks the
public key hash against on-chain cert hashes, verifies the signature,
and rejects unauthorized calls with UNAUTHENTICATED.

Cert hashes are read from a JSON file at /etc/gateway-auth/certs.json
that is bind-mounted from the host. The host's background cert poller
keeps this file up-to-date, so certs rotate without container restarts.

Usage in server.py:
    interceptor = GatewayAuthServerInterceptor(coordinator_wallet="Z9NPR...")
    server = grpc.server(..., interceptors=[interceptor])

Requires environment variables:
    GATEWAY_AUTH_COORDINATOR_WALLET  — Solana wallet address
"""
from __future__ import annotations

import json
import logging
import threading
import time

import grpc

from .gateway_auth import (
    AUTH_MESSAGE_KEY,
    AUTH_PUBKEY_KEY,
    AUTH_SIGNATURE_KEY,
    GatewayAuthError,
    verify_gateway_auth,
)

logger = logging.getLogger("model_runner.gateway_auth_interceptor")

# Path to the cert file bind-mounted from the host (written by cert_poller)
CERT_FILE = "/etc/gateway-auth/certs.json"

# How long to cache the file contents in memory (seconds).
# The file is tiny, but we avoid re-reading on every single gRPC call.
FILE_CACHE_TTL = 30


def _get_metadata_value(metadata: tuple, key: str) -> str | None:
    """Extract a value from gRPC metadata (case-insensitive key lookup)."""
    for k, v in metadata:
        if k.lower() == key:
            return v
    return None


class _AbortHandler(grpc.RpcMethodHandler):
    """RPC handler that immediately returns UNAUTHENTICATED."""

    def __init__(self, details: str):
        self.request_streaming = False
        self.response_streaming = False
        self.request_deserializer = None
        self.response_serializer = None
        self._details = details
        self.unary_unary = self._abort
        self.unary_stream = self._abort
        self.stream_unary = None
        self.stream_stream = None

    def _abort(self, request, context):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, self._details)


class GatewayAuthServerInterceptor(grpc.ServerInterceptor):
    """
    Server interceptor that verifies gateway auth tokens on every call.

    Reads cert hashes from a host-mounted JSON file that is periodically
    refreshed by the host's cert poller. Results are cached in memory
    with a short TTL to avoid reading the file on every gRPC call.

    On each call:
      1. Extracts public key DER from metadata
      2. Checks SHA-256(pubkey_der) is in the cert hashes from the file
      3. Verifies the signature over the payload
      4. Checks timestamp freshness

    Args:
        coordinator_wallet: Solana wallet address of the coordinator.
        max_age_seconds: Maximum allowed token age (default 30s).
        cert_file: Path to the cert hashes JSON file (default /etc/gateway-auth/certs.json).
        skip_methods: Method names to skip auth for (e.g. health checks).
    """

    def __init__(
        self,
        coordinator_wallet: str,
        max_age_seconds: int = 30,
        cert_file: str = CERT_FILE,
        skip_methods: set[str] | None = None,
    ):
        self.coordinator_wallet = coordinator_wallet
        self.max_age_seconds = max_age_seconds
        self.cert_file = cert_file
        self.skip_methods = skip_methods or {
            "/grpc.health.v1.Health/Check",
            "/grpc.health.v1.Health/Watch",
        }

        self._cert_hashes: set[str] = set()
        self._cert_hashes_read_at: float = 0
        self._lock = threading.Lock()

        # Do an initial read so we fail fast if the file is missing at startup
        self._cert_hashes = self._read_cert_file()
        self._cert_hashes_read_at = time.time()
        logger.info(
            "Gateway auth: loaded %d cert hash(es) from %s for wallet %s",
            len(self._cert_hashes),
            self.cert_file,
            self.coordinator_wallet,
        )

    def _read_cert_file(self) -> set[str]:
        """Read cert hashes from the host-mounted JSON file."""
        try:
            with open(self.cert_file) as f:
                data = json.load(f)
        except FileNotFoundError:
            raise GatewayAuthError(
                f"Cert file not found: {self.cert_file} — "
                "the host cert poller may not have written it yet"
            )
        except (json.JSONDecodeError, OSError) as e:
            raise GatewayAuthError(f"Failed to read cert file {self.cert_file}: {e}")

        hashes = data.get("cert_hashes", [])
        if not hashes:
            raise GatewayAuthError(
                f"No cert hashes in {self.cert_file} for wallet {self.coordinator_wallet}"
            )

        return {h.lower() for h in hashes}

    def _get_cert_hashes(self) -> set[str]:
        """Get cert hashes, re-reading the file if the cache is stale."""
        now = time.time()
        if now - self._cert_hashes_read_at < FILE_CACHE_TTL and self._cert_hashes:
            return self._cert_hashes

        with self._lock:
            now = time.time()
            if now - self._cert_hashes_read_at < FILE_CACHE_TTL and self._cert_hashes:
                return self._cert_hashes

            try:
                self._cert_hashes = self._read_cert_file()
                self._cert_hashes_read_at = now
                logger.info(
                    "Refreshed %d cert hash(es) from %s",
                    len(self._cert_hashes),
                    self.cert_file,
                )
            except Exception:
                if self._cert_hashes:
                    logger.warning(
                        "Failed to re-read cert file, using cached values",
                        exc_info=True,
                    )
                    self._cert_hashes_read_at = now  # back off until next TTL
                else:
                    raise

        return self._cert_hashes

    def intercept_service(
        self,
        continuation,
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        # Skip auth for health checks
        method = handler_call_details.method
        if method in self.skip_methods:
            return continuation(handler_call_details)

        metadata = handler_call_details.invocation_metadata
        message_b64 = _get_metadata_value(metadata, AUTH_MESSAGE_KEY)
        signature_b64 = _get_metadata_value(metadata, AUTH_SIGNATURE_KEY)
        pubkey_b64 = _get_metadata_value(metadata, AUTH_PUBKEY_KEY)

        if not message_b64 or not signature_b64 or not pubkey_b64:
            logger.warning("Gateway auth: missing metadata on %s", method)
            return _AbortHandler("Gateway authentication failed")

        try:
            allowed_hashes = self._get_cert_hashes()
            verify_gateway_auth(
                message_b64=message_b64,
                signature_b64=signature_b64,
                pubkey_b64=pubkey_b64,
                allowed_cert_hashes=allowed_hashes,
                max_age_seconds=self.max_age_seconds,
            )
        except GatewayAuthError as e:
            logger.warning("Gateway auth failed on %s: %s", method, e)
            return _AbortHandler("Gateway authentication failed")

        return continuation(handler_call_details)
