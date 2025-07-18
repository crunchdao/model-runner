import os
import sys

import importlib

import grpc

from model_runner.grpc.generated import train_infer_pb2_grpc
from model_runner.grpc.generated.train_infer_pb2 import InferRequest, InferResponse
from model_runner.grpc.generated.commons_pb2 import Argument, Variant
from model_runner.utils.checkers import ensure_function
from model_runner.utils.datatype_transformer import decode_data, encode_data, detect_data_type
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


class TrainInferStreamServicer(train_infer_pb2_grpc.TrainInferStreamServiceServicer):

    def __init__(
        self,
        code_directory: str,
        resource_directory: str,
        has_gpu: bool = False,
        main_file="main.py",
    ):
        super().__init__()

        self.main_file = main_file
        self.code_directory = code_directory
        self.resource_directory = resource_directory
        self.has_gpu = has_gpu

        self.module = None
        self.infer_function = None
        self.train_function = None

        self.infer_stream = None
        self.infer_generator = None
        self._setup_called = False

    def Setup(self, request, context):
        if not self._setup_called:

            # TODO The resource directory should NOT be blank, but a test requires it.
            # What happen if the user wants to store things AFTER his code has started?
            if self.resource_directory:
                os.makedirs(self.resource_directory, exist_ok=True)

            self.module = self.import_code()
            self.infer_function = ensure_function(self.module, "infer")
            self.train_function = ensure_function(self.module, "train")
            self.infer_stream = InferStream()

            self._setup_infer_generator()
            self._setup_called = True

        return empty_pb2.Empty()

    def Reinitialize(self, request, context):
        self._setup_infer_generator()
        return empty_pb2.Empty()

    def Infer(self, infer_request: InferRequest, context):
        if self._setup_called is None:
            context.abort(code=grpc.StatusCode.FAILED_PRECONDITION, details="Call Setup first")

        try:

            self.infer_stream.value = decode_data(infer_request.argument.value, infer_request.argument.type)

            print(f"InferRequest : {self.infer_stream.value}")

            prediction = next(self.infer_generator)

            print(f"InferResponse : {prediction}")

            # Require prediction type in Setup ??
            type_of_prediction = detect_data_type(prediction)
            infer_response = InferResponse(prediction=Variant(type=type_of_prediction, value=encode_data(type_of_prediction, prediction)))

            return infer_response

        except Exception as e:
            print(str(e))
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
