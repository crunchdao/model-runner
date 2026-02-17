"""
Server-side gateway auth: verify signed tokens from gRPC metadata.

Verification chain:
  1. Client sends: signed payload + signature + DER public key
  2. Server computes SHA-256(public_key_der)
  3. Server checks the hash matches on-chain cert hashes for the
     coordinator's wallet (fetched from cpi.crunchdao.io/certificates)
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
from typing import Optional

import requests

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
from cryptography.hazmat.primitives.serialization import load_der_public_key

logger = logging.getLogger("model_runner.gateway_auth")

# Must match model_runner_client.security.gateway_auth_interceptor
AUTH_MESSAGE_KEY = "x-gateway-auth-message"
AUTH_SIGNATURE_KEY = "x-gateway-auth-signature"
AUTH_PUBKEY_KEY = "x-gateway-auth-pubkey"

CPI_CERTIFICATES_URL = "https://cpi.crunchdao.io/certificates"


class GatewayAuthError(Exception):
    """Raised when gateway auth verification fails."""


# ---------------------------------------------------------------------------
# On-chain cert hash lookup
# ---------------------------------------------------------------------------

def fetch_cert_hashes(coordinator_wallet: str, timeout: float = 5) -> set[str]:
    """
    Fetch the on-chain cert hashes for a coordinator wallet.

    Returns a set of hex-encoded SHA-256 hashes (primary + secondary).
    """
    try:
        resp = requests.get(
            CPI_CERTIFICATES_URL,
            params={"wallet": coordinator_wallet},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise GatewayAuthError(
            f"Failed to fetch cert hashes for wallet {coordinator_wallet}: {e}"
        ) from e

    hashes_set = set()
    for key in ("certHash", "certHashSecondary"):
        h = data.get(key)
        if h and h != "0" * 64:  # skip zero hashes (empty slots)
            hashes_set.add(h.lower())

    if not hashes_set:
        raise GatewayAuthError(
            f"No certificate hashes registered on-chain for wallet {coordinator_wallet}"
        )

    return hashes_set


def compute_pubkey_hash(pubkey_der: bytes) -> str:
    """Compute SHA-256 of DER-encoded SubjectPublicKeyInfo, return hex."""
    return hashlib.sha256(pubkey_der).hexdigest()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _verify_signature(public_key: object, data: bytes, signature: bytes) -> None:
    """Verify *signature* over *data*. Raises on failure."""
    if isinstance(public_key, rsa.RSAPublicKey):
        public_key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
    elif isinstance(public_key, ed25519.Ed25519PublicKey):
        public_key.verify(signature, data)
    else:
        raise TypeError(f"Unsupported public key type: {type(public_key)}")


# ---------------------------------------------------------------------------
# Full verification
# ---------------------------------------------------------------------------

def verify_gateway_auth(
    *,
    message_b64: str,
    signature_b64: str,
    pubkey_b64: str,
    allowed_cert_hashes: set[str],
    expected_model_id: str | None = None,
    max_age_seconds: int = 30,
) -> dict:
    """
    Verify gateway auth metadata from a gRPC request.

    Args:
        message_b64: base64-encoded JSON payload
        signature_b64: base64-encoded signature
        pubkey_b64: base64-encoded DER SubjectPublicKeyInfo
        allowed_cert_hashes: set of hex SHA-256 hashes (from on-chain)
        expected_model_id: if set, verify model_id in payload
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

    # Check timestamp freshness
    ts = payload.get("timestamp")
    if ts is None:
        raise GatewayAuthError("Missing 'timestamp' in payload")
    age = abs(time.time() - float(ts))
    if age > max_age_seconds:
        raise GatewayAuthError(
            f"Token expired: age={age:.0f}s exceeds max_age={max_age_seconds}s"
        )

    # Check model_id
    if expected_model_id is not None:
        if payload.get("model_id") != expected_model_id:
            raise GatewayAuthError(
                f"model_id mismatch: got {payload.get('model_id')!r}, "
                f"expected {expected_model_id!r}"
            )

    return payload
