import grpc
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from model_runner.utils.wallet_gelegation import verify_wallet_delegation, AuthError


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
    def __init__(self, wallet_pub_b58: str, protected_prefix: str = ""):
        self._wallet_pub_b58 = wallet_pub_b58
        self._protected_prefix = protected_prefix

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
            # 1) Extract metadata
            md = {k: v for k, v in context.invocation_metadata()}
            message_b64 = md.get("x-auth-message")
            signature_b64 = md.get("x-auth-signature")
            wallet_pubkey_b58 = md.get("x-auth-wallet-pubkey")

            if not message_b64 or not signature_b64 or not wallet_pubkey_b58:
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED,
                    "Missing auth metadata (x-auth-message/signature/wallet-pubkey)",
                )

            # 2) Extract TLS client pubkey from mTLS
            try:
                tls_client_pub = extract_client_transport_pub_from_tls(context)
            except grpc.RpcError:
                raise  # already aborted

            # 3) Call generic verifier
            try:
                delegation = verify_wallet_delegation(
                    message_b64=message_b64,
                    signature_b64=signature_b64,
                    wallet_pub_b58=wallet_pubkey_b58,
                    expected_wallet_pub_b58=self._wallet_pub_b58,
                    tls_pub=tls_client_pub,
                )
            except AuthError as e:
                context.abort(grpc.StatusCode.UNAUTHENTICATED, str(e))


            return original_unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            new_unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )