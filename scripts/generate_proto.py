import subprocess

def run():
    command = (
        "poetry run python -m grpc_tools.protoc " # todo exec this from ./model_runner
        "-I./model_runner/protos "
        "--python_out=./model_runner/protos "
        "--pyi_out=./model_runner/protos "
        "--grpc_python_out=./model_runner/protos "
        "./model_runner/protos/model_runner.proto"
    )
    print(f"Executing: {command}")
    subprocess.run(command, shell=True, check=True)
