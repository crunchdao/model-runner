import logging

import grpc
import sys

from model_runner.grpc.generated import dynamic_subclass_pb2_grpc
from model_runner.grpc.generated.commons_pb2 import Variant
from model_runner.grpc.generated.dynamic_subclass_pb2 import SetupResponse, SetupRequest, CallRequest, CallResponse
from model_runner.utils import class_resolver
from model_runner.utils.datatype_transformer import decode_data, detect_data_type, encode_data

logger = logging.getLogger(f'model_runner.{__name__}')


class DynamicSubclassServicer(dynamic_subclass_pb2_grpc.DynamicSubclassServiceServicer):
    def __init__(self, code_directory):
        self.code_directory = code_directory
        self.instance = None
        super().__init__()

    def Setup(self, request: SetupRequest, context):
        if self.instance is not None:
            logger.debug('[Coordinator] Setup has already been called and an instance exists, setup is ignored')
            return SetupResponse()

        try:
            class_name = request.className
            if class_name == '':
                print('FAILED_PRECONDITION: class_name cannot be empty', file=sys.stderr)
                context.abort(
                    code=grpc.StatusCode.FAILED_PRECONDITION,
                    details='class_name cannot be empty'
                )

            args, kwargs = self.prepare_arguments(request.instanceArguments, request.instanceKwArguments)
            self.instance = class_resolver.load_instance(self.code_directory, class_name, *args, **kwargs)

            return SetupResponse()
        except ValueError as e:
            logger.error('FAILED_PRECONDITION', exc_info=True)
            context.abort(
                code=grpc.StatusCode.FAILED_PRECONDITION,
                details=str(e)
            )
        except Exception as e:
            logger.error('INTERNAL', exc_info=True)
            context.abort(
                code=grpc.StatusCode.INTERNAL,
                details=str(e)
            )

    def Call(self, request: CallRequest, context) -> CallResponse | None:
        if self.instance is None:
            logger.error('[Coordinator] FAILED_PRECONDITION - Setup has not been called yet')
            context.abort(
                code=grpc.StatusCode.FAILED_PRECONDITION,
                details='Setup has not been called yet'
            )

        method_name = request.methodName
        if method_name == '':
            logger.error('[Coordinator] INVALID_ARGUMENT - methodName cannot be empty')
            context.abort(
                code=grpc.StatusCode.INVALID_ARGUMENT,
                details='methodName cannot be empty'
            )
        method = None
        try:
            method = getattr(self.instance, method_name)
        except AttributeError as e:
            logger.error(f'INTERNAL: Method "{method_name}" not found in class "{self.instance.__class__.__name__}"')
            context.abort(
                code=grpc.StatusCode.INTERNAL,
                details=f'Method "{method_name}" not found in class "{self.instance.__class__.__name__}"'
            )

        try:
            args, kwargs = self.prepare_arguments(request.methodArguments, request.methodKwArguments)
            method_result = method(*args, **kwargs)
            if method_result is None:
                return CallResponse()

            type_of_result = detect_data_type(method_result)
            encoded_result: bytes = encode_data(type_of_result, method_result)
            return CallResponse(methodResponse=Variant(type=type_of_result, value=encoded_result))

        except Exception as e:
            logger.error(f'INTERNAL: The model raised an exception', exc_info=True)
            context.abort(
                code=grpc.StatusCode.INTERNAL,
                details=f'The model raised an exception: {str(e)}'
            )

    @staticmethod
    def prepare_arguments(args, kwargs):
        args = [
            decode_data(arg.data.value, arg.data.type) for arg in sorted(args, key=lambda arg: arg.position)
        ]

        kwargs = {
            kwarg.keyword: decode_data(kwarg.data.value, kwarg.data.type) for kwarg in kwargs
        }

        return args, kwargs
