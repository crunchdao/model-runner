import os
import sys
from typing import Iterator

import importlib

import grpc

from .protos.model_runner_pb2 import InferRequest, InferResponse, DataType
from .protos import model_runner_pb2_grpc
from .datatype_transformer import decode_data, encode_data, detect_data_type
from .utils import ensure_function
from google.protobuf import empty_pb2


class InferStream:
    def __init__(self):
        self.value = None

    def __iter__(self):
        return self

    def __next__(self):
        if self.value is None:
            raise StopIteration()

        return self.value


class ModelRunner(model_runner_pb2_grpc.ModelRunnerServicer):
    def __init__(self,
                 code_directory: str,
                 model_directory: str,
                 has_gpu: bool = False,
                 main_file="main.py",
                 ):

        self.main_file = main_file
        self.code_directory = code_directory
        self.model_directory = model_directory
        self.has_gpu = has_gpu
        self.module = self.import_code()

        self.infer_function = ensure_function(self.module, "infer")
        self.train_function = ensure_function(self.module, "train")

        self.infer_stream = InferStream()
        self.infer_generator = None
        self.stepup = False
        super()

    def Setup(self, request, context):
        if not self.stepup:
            self._setup_infer_generator()
            self.stepup = True

        return empty_pb2.Empty()

    def Reinitialize(self, request, context):
        self._setup_infer_generator()
        return empty_pb2.Empty()

    def Infer(self, infer_request: InferRequest, context):
        try:

            self.infer_stream.value = decode_data(infer_request.argument, infer_request.type)

            print(f"InferRequest : {self.infer_stream.value}")

            prediction = next(self.infer_generator)

            print(f"InferResponse : {prediction}")

            # Require prediction type in Setup ??
            type_of_prediction = detect_data_type(prediction)
            infer_response = InferResponse(type=type_of_prediction, prediction=encode_data(type_of_prediction, prediction))

            return infer_response

        except Exception as e:
            print(e)
            self._setup_infer_generator()
            context.abort(code=grpc.StatusCode.INTERNAL, details=e)

    def _setup_infer_generator(self):
        self.infer_generator = self.infer_function(self.infer_stream)
        next(self.infer_generator)

    def import_code(self):
        """
        Import the code from the main_file in the code_directory and return the module object.

        :return: The module object containing the code from the main_file
        """

        sys.path.insert(0, self.code_directory)

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
