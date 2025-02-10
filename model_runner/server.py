from concurrent import futures
import grpc
from .protos import model_runner_pb2_grpc
from .model_runner import ModelRunner
import click


@click.command()
@click.option('--address', default="[::]:50051", envvar="GRPC_ADDRESS", help='IP + Port of server GRPC.')
@click.option("--code-directory", envvar="CODE_DIRECTORY", default="/workspace/submission/code/")
@click.option("--resource-directory", envvar="RESOURCE_DIRECTORY", default="/workspace/resources")
@click.option("--has-gpu", envvar="HAS_GPU", type=bool, default=False, help='Information if GPU is available')
@click.option("--main-file", envvar="MAIN_FILE", default="main.py", help="main file's name of model")
def serve(address, code_directory, resource_directory, has_gpu, main_file):
    """Program giving access remotely to model via RPC"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    model_runner_pb2_grpc.add_ModelRunnerServicer_to_server(ModelRunner(code_directory=code_directory,
                                                                        resouce_directory=resource_directory,
                                                                        has_gpu=has_gpu,
                                                                        main_file=main_file),
                                                            server)
    server.add_insecure_port(address)
    print(f"Server started on port {address}...")
    server.start()
    server.wait_for_termination()
