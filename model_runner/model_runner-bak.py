import os
from typing import Iterator

import importlib

from .protos.model_runner_pb2 import InferRequest, InferResponse, DataType
from .protos import model_runner_pb2_grpc
from .datatype_transformer import decode_data, encode_data
from .utils import ensure_function


class ModelRunner(model_runner_pb2_grpc.ModelRunnerServicer):
    def __init__(self,
                 code_directory: str,
                 model_directory_path: str,
                 has_gpu: bool = False,
                 main_file="main.py",
                 ):

        self.main_file = main_file
        self.code_directory = code_directory
        self.model_directory_path = model_directory_path
        self.has_gpu = has_gpu
        self.module = self.import_code()
        self.infer_function = ensure_function(self.module, "infer")
        self.train_function = ensure_function(self.module, "train")

        super()

    def Infer(self, request_iterator, context):
        try:
            print("new Infer call....")
            # add check if argument is used and set it (data_directory_path: str, model_directory_path: str, has_gpu)
            # reuse smart_call function in crunch-cli
            infer_generator = self.infer_function(self.stream_to_dict(request_iterator))

            next(infer_generator)  # Start the generator

            # Process predictions from the inference generator
            for prediction in infer_generator:
                # todo try catch invalid data format
                # todo getting type of model response from context or Init function ?
                # todo add in InferResponse status (enum SUCCUES, FAILES) and error fom message Error {string code=1; sting message=2}
                # Yield the response as long as the generator produces predictions
                yield InferResponse(type=DataType.DOUBLE, prediction=encode_data(DataType.DOUBLE, prediction))

        except Exception as e:
            print(e)
            # todo abort with err msg

    def stream_to_dict(self, stream: Iterator[InferRequest]) -> Iterator[dict]:
        """Reads a gRPC stream and transforms each message into a dictionary."""
        for message in stream:
            print("stream_to_dict", message)
            # todo try catch invalid data input
            yield {
                arg.name: decode_data(arg.value, arg.type)
                for arg in message.arguments
            }

    def import_code(self):
        """
        Import the code from the main_file in the code_directory and return the module object.

        :return: The module object containing the code from the main_file
        """
        file_path = os.path.join(self.code_directory, self.main_file)
        module_name = 'submission code'
        # Create a module specification from the file path
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            raise ImportError(f"Cannot create a spec for module {module_name} from {file_path}", file_path)

        # Create the module from the spec
        module = importlib.util.module_from_spec(spec)

        # Execute the module to load it
        spec.loader.exec_module(module)

        return module
