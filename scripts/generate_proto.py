import subprocess


def run():
    command = (
        "poetry run python -m grpc_tools.protoc "  # todo exec this from ./model_runner
        "-I./model_runner/grpc/protos "
        "--python_out=./model_runner/grpc/generated "
        "--pyi_out=./model_runner/grpc/generated "
        "--grpc_python_out=./model_runner/grpc/generated "
        "./model_runner/grpc/protos/*.proto "
    )

    print(f"Executing protoc: {command}")
    subprocess.run(command, shell=True, check=True)


    # fix import by adding from.
    command = (
        "poetry run protol "
        "--create-package "
        "--in-place "
        "--python-out model_runner/grpc/generated "
        "protoc --proto-path=model_runner/grpc/protos/ "
        "commons.proto dynamic_subclass.proto train_infer.proto "
    )
    print(f"Executing protol : {command}")
    subprocess.run(command, shell=True, check=True)
