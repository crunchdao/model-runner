"""
Tests for gateway auth: generate signed messages the same way the
model-runner-client does, then verify them on the server side.
"""
import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from model_runner.security.gateway_auth import (
    GatewayAuthError,
    compute_pubkey_hash,
    verify_gateway_auth,
)


# ---------------------------------------------------------------------------
# Helpers — replicate exactly what model_runner_client does
# ---------------------------------------------------------------------------

def _generate_rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _public_key_der(private_key: rsa.RSAPrivateKey) -> bytes:
    """Same as model_runner_client.security.gateway_auth_interceptor._public_key_der"""
    return private_key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)


def _sign(private_key: rsa.RSAPrivateKey, data: bytes) -> bytes:
    """Same as model_runner_client.security.gateway_auth_interceptor._sign"""
    return private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())


def _build_auth_metadata(
    private_key: rsa.RSAPrivateKey,
    model_id: str,
    timestamp: int | None = None,
) -> tuple[str, str, str]:
    """
    Build (message_b64, signature_b64, pubkey_b64) the exact same way
    GatewayAuthClientInterceptor._build_auth_metadata does.
    """
    if timestamp is None:
        timestamp = int(time.time())

    payload = json.dumps(
        {"model_id": model_id, "timestamp": timestamp},
        separators=(",", ":"),
    ).encode()
    signature = _sign(private_key, payload)
    pubkey_der = _public_key_der(private_key)

    return (
        base64.b64encode(payload).decode(),
        base64.b64encode(signature).decode(),
        base64.b64encode(pubkey_der).decode(),
    )


def _cert_hash(private_key: rsa.RSAPrivateKey) -> str:
    """Compute the on-chain cert hash for a key."""
    return compute_pubkey_hash(_public_key_der(private_key))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVerifyGatewayAuth:
    """Verify that server-side verification accepts/rejects tokens correctly."""

    def test_valid_signature(self):
        """A freshly signed token with matching cert hash passes."""
        key = _generate_rsa_key()
        allowed = {_cert_hash(key)}
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(key, "model-42")

        result = verify_gateway_auth(
            message_b64=msg_b64,
            signature_b64=sig_b64,
            pubkey_b64=pub_b64,
            allowed_cert_hashes=allowed,
        )

        assert "timestamp" in result

    def test_expired_token(self):
        """A correctly signed token that is too old is rejected."""
        key = _generate_rsa_key()
        allowed = {_cert_hash(key)}
        old_timestamp = int(time.time()) - 60  # 60 seconds ago
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(
            key, "model-42", timestamp=old_timestamp
        )

        with pytest.raises(GatewayAuthError, match="Token expired"):
            verify_gateway_auth(
                message_b64=msg_b64,
                signature_b64=sig_b64,
                pubkey_b64=pub_b64,
                allowed_cert_hashes=allowed,
                max_age_seconds=30,
            )

    def test_wrong_key_rejected(self):
        """A token signed by a different key (not in allowed hashes) is rejected."""
        signing_key = _generate_rsa_key()
        other_key = _generate_rsa_key()
        allowed = {_cert_hash(other_key)}  # only the other key is allowed
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(signing_key, "model-42")

        with pytest.raises(GatewayAuthError, match="not found in on-chain cert hashes"):
            verify_gateway_auth(
                message_b64=msg_b64,
                signature_b64=sig_b64,
                pubkey_b64=pub_b64,
                allowed_cert_hashes=allowed,
            )

    def test_tampered_payload_rejected(self):
        """A valid signature over a tampered payload is rejected."""
        key = _generate_rsa_key()
        allowed = {_cert_hash(key)}
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(key, "model-42")

        # Tamper with the payload
        tampered = json.dumps(
            {"model_id": "model-HACKED", "timestamp": int(time.time())},
            separators=(",", ":"),
        ).encode()
        tampered_b64 = base64.b64encode(tampered).decode()

        with pytest.raises(GatewayAuthError, match="Signature verification failed"):
            verify_gateway_auth(
                message_b64=tampered_b64,
                signature_b64=sig_b64,
                pubkey_b64=pub_b64,
                allowed_cert_hashes=allowed,
            )

    def test_future_timestamp_rejected(self):
        """A token with a timestamp far in the future is rejected."""
        key = _generate_rsa_key()
        allowed = {_cert_hash(key)}
        future_timestamp = int(time.time()) + 120  # 2 minutes in the future
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(
            key, "model-42", timestamp=future_timestamp
        )

        with pytest.raises(GatewayAuthError, match="future"):
            verify_gateway_auth(
                message_b64=msg_b64,
                signature_b64=sig_b64,
                pubkey_b64=pub_b64,
                allowed_cert_hashes=allowed,
            )

    def test_primary_and_secondary_cert_rotation(self):
        """Both primary and secondary cert hashes are accepted (rotation)."""
        old_key = _generate_rsa_key()
        new_key = _generate_rsa_key()
        allowed = {_cert_hash(old_key), _cert_hash(new_key)}

        # Old key still works
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(old_key, "model-42")
        result = verify_gateway_auth(
            message_b64=msg_b64,
            signature_b64=sig_b64,
            pubkey_b64=pub_b64,
            allowed_cert_hashes=allowed,
        )
        assert result["model_id"] == "model-42"

        # New key also works
        msg_b64, sig_b64, pub_b64 = _build_auth_metadata(new_key, "model-42")
        result = verify_gateway_auth(
            message_b64=msg_b64,
            signature_b64=sig_b64,
            pubkey_b64=pub_b64,
            allowed_cert_hashes=allowed,
        )
        assert result["model_id"] == "model-42"
