"""
Server-side gateway auth: verify signed tokens from gRPC metadata.

Verification chain:
  1. Client sends: signed payload + signature + DER public key
  2. Server computes SHA-256(public_key_der)
  3. Server checks the hash matches allowed cert hashes (read from
     a host-mounted file kept fresh by the cert poller)
  4. Server verifies the signature against the presented public key
  5. Server checks timestamp freshness

Metadata keys (must match the client interceptor in model_runner_client):
  - x-gateway-auth-message   : base64(JSON payload)
  - x-gateway-auth-signature : base64(signature)
  - x-gateway-auth-pubkey    : base64(DER SubjectPublicKeyInfo)
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key

logger = logging.getLogger("model_runner.gateway_auth")

# Must match model_runner_client.security.gateway_auth_interceptor
AUTH_MESSAGE_KEY = "x-gateway-auth-message"
AUTH_SIGNATURE_KEY = "x-gateway-auth-signature"
AUTH_PUBKEY_KEY = "x-gateway-auth-pubkey"


class GatewayAuthError(Exception):
    """Raised when gateway auth verification fails."""


def compute_pubkey_hash(pubkey_der: bytes) -> str:
    """Compute SHA-256 of DER-encoded SubjectPublicKeyInfo, return hex."""
    return hashlib.sha256(pubkey_der).hexdigest()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(public_key: rsa.RSAPublicKey, data: bytes, signature: bytes) -> None:
    """Verify RSA PKCS#1 v1.5 + SHA-256 *signature* over *data*. Raises on failure."""
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise GatewayAuthError(f"Expected RSA public key, got {type(public_key).__name__}")
    public_key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())


# ---------------------------------------------------------------------------
# Full verification
# ---------------------------------------------------------------------------

def verify_gateway_auth(
    *,
    message_b64: str,
    signature_b64: str,
    pubkey_b64: str,
    allowed_cert_hashes: set[str],
    max_age_seconds: int = 30,
) -> dict:
    """
    Verify gateway auth metadata from a gRPC request.

    Args:
        message_b64: base64-encoded JSON payload
        signature_b64: base64-encoded signature
        pubkey_b64: base64-encoded DER SubjectPublicKeyInfo
        allowed_cert_hashes: set of hex SHA-256 hashes (from on-chain)
        max_age_seconds: max allowed token age

    Returns the decoded payload dict on success.
    Raises GatewayAuthError on any problem.
    """
    # Decode
    try:
        message_bytes = base64.b64decode(message_b64)
        signature = base64.b64decode(signature_b64)
        pubkey_der = base64.b64decode(pubkey_b64)
    except Exception as e:
        raise GatewayAuthError(f"Invalid base64 encoding: {e}") from e

    # Check cert hash against on-chain registry
    presented_hash = compute_pubkey_hash(pubkey_der)
    logger.debug(
        "Gateway auth: pubkey_der=%d bytes, hash=%s, allowed=%s",
        len(pubkey_der), presented_hash, allowed_cert_hashes,
    )
    if presented_hash not in allowed_cert_hashes:
        raise GatewayAuthError(
            f"Public key hash {presented_hash} not found in on-chain cert hashes"
        )

    # Load key and verify signature
    try:
        public_key = load_der_public_key(pubkey_der)
        _verify_signature(public_key, message_bytes, signature)
    except GatewayAuthError:
        raise
    except Exception as e:
        raise GatewayAuthError(f"Signature verification failed: {e}") from e

    # Decode payload
    try:
        payload = json.loads(message_bytes)
    except Exception as e:
        raise GatewayAuthError(f"Invalid JSON payload: {e}") from e

    # Check timestamp freshness (reject future timestamps too)
    ts = payload.get("timestamp")
    if ts is None:
        raise GatewayAuthError("Missing 'timestamp' in payload")
    now = time.time()
    token_time = float(ts)
    if token_time > now + 5:  # allow 5s clock skew
        raise GatewayAuthError("Token timestamp is in the future")
    if now - token_time > max_age_seconds:
        raise GatewayAuthError(
            f"Token expired: age={now - token_time:.0f}s exceeds max_age={max_age_seconds}s"
        )

    return payload
