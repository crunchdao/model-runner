import hashlib
from typing import Optional

import grpc
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def extract_client_transport_pub_from_tls(context: grpc.ServicerContext) -> bytes:
    """
    Get the TLS client public key (coordinator TLS cert) from mTLS.

    Returns the public key encoded as DER SubjectPublicKeyInfo, which works
    for RSA / ECDSA (and aussi Ed25519 si tu en as encore quelque part).
    """
    auth_ctx = context.auth_context()
    pem_list = auth_ctx.get("x509_pem_cert")
    if not pem_list:
        context.abort(
            grpc.StatusCode.UNAUTHENTICATED,
            "No client certificate (mTLS required)",
        )

    pem_cert = pem_list[0]
    cert = x509.load_pem_x509_certificate(pem_cert)

    pub = cert.public_key()

    return pub.public_bytes(
        encoding=Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo,
    )


class WalletTlsAuthInterceptor(grpc.ServerInterceptor):
    def __init__(
        self,
        coordinator_cert_hash: str,
        coordinator_cert_hash_secondary: Optional[str] = None,
        protected_prefix: str = "",
    ):
        self._coordinator_cert_hash = coordinator_cert_hash
        self._coordinator_cert_hash_secondary = coordinator_cert_hash_secondary
        self._protected_prefix = protected_prefix

    @staticmethod
    def _hash_tls_pubkey(tls_pub: bytes) -> str:
        """Hash the TLS public key using SHA256."""
        return hashlib.sha256(tls_pub).hexdigest()

    def _verify_tls_cert_hash(self, tls_pub: bytes, context: grpc.ServicerContext) -> None:
        """Verify that the TLS client cert hash matches the registered cert hashes."""
        tls_pub_hash = self._hash_tls_pubkey(tls_pub)

        if tls_pub_hash != self._coordinator_cert_hash and tls_pub_hash != self._coordinator_cert_hash_secondary:
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                "TLS certificate hash does not match registered certificate",
            )

    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        method_name = handler_call_details.method
        if self._protected_prefix and not method_name.startswith(self._protected_prefix):
            return handler

        if handler.unary_unary is None:
            return handler

        original_unary_unary = handler.unary_unary

        def new_unary_unary(request, context: grpc.ServicerContext):
            # 1) Extract TLS client pubkey from mTLS
            try:
                tls_client_pub = extract_client_transport_pub_from_tls(context)
            except grpc.RpcError:
                raise  # already aborted

            # 2) Verify TLS cert hash matches registered coordinator cert
            self._verify_tls_cert_hash(tls_client_pub, context)

            return original_unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            new_unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
