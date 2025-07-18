import logging
from concurrent.futures import ThreadPoolExecutor

import click
import grpc

from .grpc.generated import dynamic_subclass_pb2_grpc, train_infer_pb2_grpc
from .servicers.dynamic_subclass_servicer import DynamicSubclassServicer
from .servicers.train_infer_servicer import TrainInferStreamServicer

logger = logging.getLogger('model_runner')
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s - %(message)s")


@click.command()
@click.option('--address', default='[::]:50051', envvar='GRPC_ADDRESS', help='IP + Port of server GRPC.')
@click.option('--code-directory', type=click.Path(exists=True, file_okay=False), envvar='CODE_DIRECTORY', default='/workspace/submission/code')
@click.option('--resource-directory', type=click.Path(file_okay=False), envvar='RESOURCE_DIRECTORY', default='/workspace/resources')
@click.option('--has-gpu', type=bool, envvar='HAS_GPU', default=False, help='Information if GPU is available')
@click.option('--main-file', envvar='MAIN_FILE', default='main.py', help="main file's name of model")
@click.option('--log-level', type=click.Choice(["debug", "info", "warning", "error", "critical"], case_sensitive=False), default='info', envvar='LOG_LEVEL', help='Logging level')
def cli(
    address: str,
    code_directory: str,
    resource_directory: str,
    has_gpu: str,
    main_file: str,
    log_level: str
):
    """Program giving access remotely to model via RPC"""

    logger.setLevel(logging.getLevelName(log_level.upper()))

    server = grpc.server(ThreadPoolExecutor(max_workers=1))

    train_infer_pb2_grpc.add_TrainInferStreamServiceServicer_to_server(
        TrainInferStreamServicer(
            code_directory=code_directory,
            resource_directory=resource_directory,
            has_gpu=has_gpu,
            main_file=main_file
        ),
        server
    )

    dynamic_subclass_pb2_grpc.add_DynamicSubclassServiceServicer_to_server(
        DynamicSubclassServicer(
            code_directory=code_directory
        ),
        server
    )

    server.add_insecure_port(address)

    logger.info(f'ModelRunner started and ready to serve on {address}')

    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    cli()
