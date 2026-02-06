import json
import logging
import os.path
from concurrent.futures import ThreadPoolExecutor

import click
import grpc

from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from model_runner.interceptors.auth_interceptor import WalletTlsAuthInterceptor
from model_runner.interceptors.server_identity_interceptor import ServerIdentityInterceptor
from model_runner.utils.server_identity import build_server_headers
from model_runner.utils.wallet_gelegation import load_pubkey_from_pem_cert, verify_wallet_delegation
from .grpc.generated import dynamic_subclass_pb2_grpc
from .servicers.dynamic_subclass_servicer import DynamicSubclassServicer

logger = logging.getLogger('model_runner')
logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s - %(message)s")


@click.command()
@click.option('--secure', is_flag=True, envvar="SECURE", help='Enable secure communication using mTLS and wallet signature verification')
@click.option('--address', default='[::]:50051', envvar='GRPC_ADDRESS', help='IP + Port of server GRPC.')
@click.option('--code-directory', type=click.Path(exists=True, file_okay=False), envvar='CODE_DIRECTORY', default='/workspace/submission/code')
@click.option('--resource-directory', type=click.Path(file_okay=False), envvar='RESOURCE_DIRECTORY', default='/workspace/resources')
@click.option('--certificates-directory', type=click.Path(file_okay=False), envvar='CERTIFICATES_DIRECTORY', default='/workspace/certificates', help='Directory containing TLS certificates for the server')
@click.option('--has-gpu', type=bool, envvar='HAS_GPU', default=False, help='Information if GPU is available')
@click.option('--main-file', envvar='MAIN_FILE', default='main.py', help="main file's name of model")
@click.option('--log-level', type=click.Choice(["debug", "info", "warning", "error", "critical"], case_sensitive=False), default='info', envvar='LOG_LEVEL', help='Logging level')
@click.option('--max-send-message-length', type=int, envvar='GRPC_MAX_SEND_MESSAGE_LENGTH', default=64 * 1024 * 1024, help='Maximum send message length in bytes for gRPC server')
@click.option('--max-receive-message-length', type=int, envvar='GRPC_MAX_RECEIVE_MESSAGE_LENGTH', default=64 * 1024 * 1024, help='Maximum receive message length in bytes for gRPC server')
@click.option('--model-id', envvar='MODEL_ID', help='Identifier for the model.')
# could be fetched from Solana later with crunch-address + model-id
@click.option('--crunch-onchain-address', envvar='CRUNCH_ONCHAIN_ADDRESS', help='Address of the crunch on Solana')
@click.option('--cruncher-wallet-pubkey', envvar='CRUNCHER_WALLET_PUBKEY', help='Cruncher wallet public key.')
@click.option('--cruncher-hotkey', envvar='CRUNCHER_HOTKEY', help='Cruncher wallet public key.')
@click.option('--coordinator-wallet-pubkey', envvar='COORDINATOR_WALLET_PUBKEY', help='Coordinator wallet public key.')
@click.option('--coordinator-cert-hash', envvar='COORDINATOR_CERT_HASH', help='Expected SHA256 hash of coordinator TLS certificate public key.')
@click.option('--coordinator-cert-hash-secondary', envvar='COORDINATOR_CERT_HASH_SECONDARY', default=None, help='Secondary expected SHA256 hash of coordinator TLS certificate public key (optional).')
def cli(
    secure: bool,
    address: str,
    code_directory: str,
    resource_directory: str,
    certificates_directory: str,
    has_gpu: str,
    main_file: str,
    log_level: str,
    max_send_message_length: int,
    max_receive_message_length: int,
    model_id: str,
    crunch_onchain_address: str,
    cruncher_hotkey: str,
    cruncher_wallet_pubkey: str,
    coordinator_wallet_pubkey: str,
    coordinator_cert_hash: str,
    coordinator_cert_hash_secondary: str,
):
    """Program giving access remotely to model via RPC"""

    logger.setLevel(logging.getLevelName(log_level.upper()))

    if secure:
        with open(os.path.join(certificates_directory, "tls.crt"), "rb") as f:
            server_cert = f.read()
        with open(os.path.join(certificates_directory, "tls.key"), "rb") as f:
            server_key = f.read()
        with open(os.path.join(certificates_directory, "ca.crt"), "rb") as f:
            ca_cert_for_clients = f.read()  # CA that signed coordinator client certs

        server_credentials = grpc.ssl_server_credentials(
            [(server_key, server_cert)],
            root_certificates=ca_cert_for_clients,
            require_client_auth=True,
        )

        ## Validate the certificates and wallet signature
        with open(os.path.join(certificates_directory, "cruncher_msg.json"), "rb") as f:
            signed_message = json.load(f)

        message_b64 = signed_message.get("message_b64")
        signature_b64 = signed_message.get("signature_b64")
        wallet_pubkey_b58 = signed_message.get("wallet_pubkey_b58")
        tls_pub = load_pubkey_from_pem_cert(server_cert)

        # raise AuthError
        verify_wallet_delegation(
            message_b64=message_b64,
            signature_b64=signature_b64,
            wallet_pub_b58=wallet_pubkey_b58,
            expected_wallet_pub_b58=cruncher_wallet_pubkey,
            tls_pub=tls_pub,
            expected_model_id=model_id,
            expected_hotkey=cruncher_hotkey
        )

        server_headers = build_server_headers(message_b64, signature_b64, wallet_pubkey_b58)

    # Use at least 2 workers to ensure Health checks are always responsive,
    # since the other service methods are restricted to one concurrent call
    server = grpc.server(
        ThreadPoolExecutor(max_workers=2),
        options=[
            ('grpc.max_send_message_length', max_send_message_length),
            ('grpc.max_receive_message_length', max_receive_message_length)
        ],
        interceptors=[
            WalletTlsAuthInterceptor(
                coordinator_cert_hash=coordinator_cert_hash,
                coordinator_cert_hash_secondary=coordinator_cert_hash_secondary,
            ),
            ServerIdentityInterceptor(server_headers),
        ] if secure else []
    )

    health_servicer = health.HealthServicer(
        experimental_non_blocking=True,
        experimental_thread_pool=ThreadPoolExecutor(max_workers=2)
    )
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    dynamic_subclass_pb2_grpc.add_DynamicSubclassServiceServicer_to_server(
        DynamicSubclassServicer(
            code_directory=code_directory
        ),
        server
    )

    if secure:
        server.add_secure_port(address, server_credentials)
    else:
        server.add_insecure_port(address)

    logger.info(f'ModelRunner started and ready to serve on {address} in mode {"secure" if secure else "insecure"}.')

    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    cli()
