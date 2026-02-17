"""
gRPC server interceptor for gateway auth.

Extracts the signed token + public key from request metadata, checks the
public key hash against on-chain cert hashes (fetched from the CPI indexer),
verifies the signature, and rejects unauthorized calls with UNAUTHENTICATED.

Usage in server.py:
    interceptor = GatewayAuthServerInterceptor(coordinator_wallet="Z9NPR...")
    server = grpc.server(..., interceptors=[interceptor])
"""
from __future__ import annotations

import logging
import threading
import time

import grpc

from .gateway_auth import (
    AUTH_MESSAGE_KEY,
    AUTH_PUBKEY_KEY,
    AUTH_SIGNATURE_KEY,
    GatewayAuthError,
    fetch_cert_hashes,
    verify_gateway_auth,
)

logger = logging.getLogger("model_runner.gateway_auth_interceptor")


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
        self.unary_unary = None
        self.unary_stream = None
        self.stream_unary = None
        self.stream_stream = None
        self._details = details

    def _abort(self, request, context):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, self._details)


class GatewayAuthServerInterceptor(grpc.ServerInterceptor):
    """
    Server interceptor that verifies gateway auth tokens on every call.

    Fetches on-chain cert hashes for the coordinator wallet and caches them.
    On each call:
      1. Extracts public key DER from metadata
      2. Checks SHA-256(pubkey_der) is in the on-chain cert hashes
      3. Verifies the signature over the payload
      4. Checks timestamp freshness

    Args:
        coordinator_wallet: Solana wallet address of the coordinator.
        max_age_seconds: Maximum allowed token age (default 30s).
        cache_ttl_seconds: How long to cache cert hashes (default 300s / 5min).
        skip_methods: Method names to skip auth for (e.g. health checks).
    """

    def __init__(
        self,
        coordinator_wallet: str,
        max_age_seconds: int = 30,
        cache_ttl_seconds: int = 300,
        skip_methods: set[str] | None = None,
    ):
        self.coordinator_wallet = coordinator_wallet
        self.max_age_seconds = max_age_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.skip_methods = skip_methods or {
            "/grpc.health.v1.Health/Check",
            "/grpc.health.v1.Health/Watch",
        }

        self._cert_hashes: set[str] = set()
        self._cert_hashes_fetched_at: float = 0
        self._lock = threading.Lock()

    def _get_cert_hashes(self) -> set[str]:
        """Get on-chain cert hashes, refreshing the cache if stale."""
        now = time.time()
        if now - self._cert_hashes_fetched_at < self.cache_ttl_seconds and self._cert_hashes:
            return self._cert_hashes

        with self._lock:
            # Double-check after acquiring lock
            if now - self._cert_hashes_fetched_at < self.cache_ttl_seconds and self._cert_hashes:
                return self._cert_hashes

            try:
                self._cert_hashes = fetch_cert_hashes(self.coordinator_wallet)
                self._cert_hashes_fetched_at = time.time()
                logger.info(
                    "Fetched %d cert hash(es) for wallet %s",
                    len(self._cert_hashes),
                    self.coordinator_wallet,
                )
            except GatewayAuthError:
                if self._cert_hashes:
                    logger.warning(
                        "Failed to refresh cert hashes, using cached values"
                    )
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
            return _AbortHandler("Missing gateway auth metadata")

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
            return _AbortHandler(str(e))

        return continuation(handler_call_details)
