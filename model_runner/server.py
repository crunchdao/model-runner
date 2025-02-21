from concurrent import futures
import grpc
from model_runner.grpc.generated import dynamic_subclass_pb2_grpc, train_infer_pb2_grpc
from model_runner.servicers.train_infer_servicer import TrainInferStreamServicer
from model_runner.servicers.dynamic_subclass_servicer import DynamicSubclassServicer
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
    train_infer_pb2_grpc.add_TrainInferStreamServiceServicer_to_server(
        TrainInferStreamServicer(
            code_directory=code_directory,
            resource_directory=resource_directory,
            has_gpu=has_gpu,
            main_file=main_file),
        server)
    dynamic_subclass_pb2_grpc.add_DynamicSubclassServiceServicer_to_server(
        DynamicSubclassServicer(
            code_directory=code_directory
        ),
        server
    )

    server.add_insecure_port(address)
    print(f"Server started on port {address}...")
    server.start()
    server.wait_for_termination()
