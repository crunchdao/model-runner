import threading
from collections import deque

import inspect

from enum import Enum

import logging

from model_runner.grpc.generated import dynamic_subclass_pb2_grpc
from model_runner.grpc.generated.commons_pb2 import Variant, Status
from model_runner.grpc.generated.dynamic_subclass_pb2 import SetupResponse, SetupRequest, CallRequest, CallResponse, RestResponse
from model_runner.servicers.exclusive_service_mixin import ExclusiveServiceMixin
from model_runner.utils import class_resolver
from model_runner.utils.datatype_transformer import decode_data, detect_data_type, encode_data
from google.protobuf import empty_pb2

logger = logging.getLogger(f'model_runner.{__name__}')


class DynamicSubclassStatus(Enum):
    SUCCESS = 'SUCCESS'
    INVALID_ARGUMENT = 'INVALID_ARGUMENT'
    FAILED_PRECONDITION = 'FAILED_PRECONDITION'
    BAD_IMPLEMENTATION = 'BAD_IMPLEMENTATION'
    SETUP_FAILED = 'SETUP_FAILED'
    MODEL_FAILED = 'MODEL_FAILED'
    UNKNOWN = 'UNKNOWN'


class DynamicSubclassServicer(dynamic_subclass_pb2_grpc.DynamicSubclassServiceServicer, ExclusiveServiceMixin):
    def __init__(self, code_directory):
        self.code_directory = code_directory
        self.instance = None
        self.methods = dict()
        self.reported_unused = deque(maxlen=100)
        super().__init__()

    def Setup(self, request: SetupRequest, context) -> SetupResponse:
        with self._exclusive(context):
            logger.info('Setup of the model requested')
            if self.instance is not None:
                logger.debug('[Coordinator] Setup has already been called and an instance exists, setup is ignored')
                return SetupResponse(status=Status(code=DynamicSubclassStatus.SUCCESS.name, message='Instance already exists'))

            try:
                class_name = request.className.strip()
                if not class_name:
                    logger.error('[Coordinator] Invalid argument, class_name cannot be empty')
                    return SetupResponse(status=Status(code=DynamicSubclassStatus.INVALID_ARGUMENT.name, message='class_name cannot be empty'))

                args, kwargs = self.prepare_arguments(request.instanceArguments, request.instanceKwArguments)
                self.instance = class_resolver.load_instance(self.code_directory, class_name, *args, **kwargs)

                logger.info(f'Successfully created instance of class: {self.instance.__class__.__name__} with arguments: {args} and keyword arguments: {kwargs}')
                logger.info('Setup successfully complete')

                return SetupResponse(status=Status(code=DynamicSubclassStatus.SUCCESS.name, message='Instance created successfully'))
            except ImportError as e:
                logger.error('BAD_IMPLEMENTATION: Import error occurred', exc_info=True)
                return SetupResponse(status=Status(code=DynamicSubclassStatus.BAD_IMPLEMENTATION.name, message=e.msg))
            except Exception as e:
                logger.error('SETUP_FAILED: An exception occurred during setup', exc_info=True)
                return SetupResponse(status=Status(code=DynamicSubclassStatus.SETUP_FAILED.name, message=str(e)))

    def Call(self, request: CallRequest, context) -> CallResponse | None:
        with self._exclusive(context):
            if self.instance is None:
                logger.error('[Coordinator] FAILED_PRECONDITION - Setup has not been called yet')
                return CallResponse(
                    status=Status(code=DynamicSubclassStatus.FAILED_PRECONDITION.name, message='Setup has not been called yet')
                )

            method_name = request.methodName
            if method_name == '':
                logger.error('[Coordinator] INVALID_ARGUMENT - methodName cannot be empty')
                return CallResponse(
                    status=Status(code=DynamicSubclassStatus.INVALID_ARGUMENT.name, message='methodName cannot be empty')
                )

            if method_name not in self.methods:
                try:
                    method = getattr(self.instance, method_name)
                except AttributeError as e:
                    logger.error(f'BAD_IMPLEMENTATION: Method "{method_name}" not found in class "{self.instance.__class__.__name__}"')
                    return CallResponse(
                        status=Status(
                            code=DynamicSubclassStatus.BAD_IMPLEMENTATION.name,
                            message=f'Method "{method_name}" not found in class "{self.instance.__class__.__name__}"'
                        )
                    )
                self.methods[method_name] = method, inspect.signature(method).parameters.keys()

            method, signature_params = self.methods[method_name]

            try:
                args, kwargs = self.prepare_arguments(request.methodArguments, request.methodKwArguments)
                expected_kwargs = {
                    k: v for i, (k, v) in enumerate(kwargs.items()) if k in list(signature_params)[len(args):]
                }

                unused_parameters = [k for k in kwargs.keys() if k not in expected_kwargs.keys()]
                if unused_parameters and unused_parameters not in self.reported_unused:
                    logger.warning(f'The following parameters are not used: {', '.join(unused_parameters)}. You may consider utilizing them if relevant to your logic.')
                    self.reported_unused.append(unused_parameters)

                logger.debug('Call to method "%s" with positional arguments: %s, keyword arguments: %s', method_name, args, kwargs)
                method_result = method(*args, **expected_kwargs)
                logger.debug('Model response: %s', method_result)
                if method_result is None:
                    return CallResponse(status=Status(code=DynamicSubclassStatus.SUCCESS.name, message=''))

                type_of_result = detect_data_type(method_result)
                logger.debug("Detected type of result: %s", type_of_result)

                encoded_result: bytes = encode_data(type_of_result, method_result)
                return CallResponse(
                    status=Status(code=DynamicSubclassStatus.SUCCESS.name, message=''),
                    methodResponse=Variant(type=type_of_result, value=encoded_result)
                )

            except Exception as e:
                logger.error(f'INTERNAL: The model raised an exception', exc_info=True)
                return CallResponse(
                    status=Status(code=DynamicSubclassStatus.MODEL_FAILED.name, message=f'The model raised an exception: {str(e)}')
                )

    def Rest(self, request: empty_pb2.Empty, context) -> RestResponse:
        with self._exclusive(context):
            logger.info('[Coordinator] Resetting the current instance')
            if self.instance is None:
                logger.warning('[Coordinator] No existing instance to reset')
                return RestResponse(
                    status=Status(
                        code=DynamicSubclassStatus.SUCCESS.name,
                        message='No instance exists to reset'
                    )
                )

            try:
                self.instance = None
                logger.info('[Coordinator] Instance successfully reset')
                return RestResponse(
                    status=Status(
                        code=DynamicSubclassStatus.SUCCESS.name,
                        message='Instance successfully reset'
                    )
                )
            except Exception as e:
                logger.error('[Coordinator] INTERNAL: Failed to reset instance', exc_info=True)
                return RestResponse(
                    status=Status(
                        code=DynamicSubclassStatus.UNKNOWN.name,
                        message=f'Failed to reset instance: {str(e)}'
                    )
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
