# File: tests/test_dynamic_subclass_servicer.py
import os
import sys
import logging

import grpc
import pytest

from model_runner.grpc.generated.commons_pb2 import Variant, VariantType, Argument, KwArgument
from model_runner.grpc.generated.dynamic_subclass_pb2 import SetupRequest, CallRequest
from model_runner.grpc.generated.dynamic_subclass_pb2_grpc import DynamicSubclassServiceServicer
from model_runner.servicers.dynamic_subclass_servicer import DynamicSubclassServicer
from model_runner.utils.datatype_transformer import detect_data_type, decode_data
from model_runner.utils.datatype_transformer import encode_data

# Initialize logger for the test module
logger = logging.getLogger(f'model_runner.{__name__}')
logger_root = logging.getLogger('model_runner')
logger_root.setLevel(logging.DEBUG)


@pytest.fixture
def grpc_context(mocker):
    mock = mocker.Mock(spec=grpc.ServicerContext)

    def abort_side_effect(code, details):
        mock.abort_args = (code, details)
        raise grpc.RpcError(f"gRPC Aborted: {code}, {details}")

    mock.abort.side_effect = abort_side_effect

    return mock


@pytest.fixture
def example_code_path():
    return os.path.dirname(__file__) + "/models_examples/quantile_regression_river"


@pytest.mark.forked
def test_setup_and_call_success(grpc_context, example_code_path):
    logger.info("Starting test: test_setup_and_call_success")
    logger.debug(f"code_directory: {example_code_path}")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)
    response = None
    request = SetupRequest(
        className="trackerbase.TrackerBase",
        instanceArguments=[],
        instanceKwArguments=[]
    )
    response = servicer.Setup(request, grpc_context)

    assert response is not None, print(grpc_context.abort.call_args)

    payload_raw = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
    logger.debug(f'payload: {payload_raw}')
    payload: bytes = encode_data(VariantType.JSON, payload_raw)
    # Call phase
    call_request = CallRequest(
        methodName="tick",
        methodArguments=[Argument(position=1, data=Variant(type=VariantType.JSON, value=payload))],
        methodKwArguments=[]
    )
    call_response = servicer.Call(call_request, grpc_context)
    assert call_response is not None, print(grpc_context.abort.call_args)
    assert call_response.status and call_response.status.code == "SUCCESS", print(call_response.status)
    assert call_response.methodResponse.type == VariantType.NONE

    call_request = CallRequest(
        methodName="predict",
        methodArguments=[],
        methodKwArguments=[]
    )
    call_response = servicer.Call(call_request, grpc_context)
    assert call_response is not None, print(grpc_context.abort.call_args)
    assert call_response.status and call_response.status.code == "SUCCESS", print(call_response.status)
    decoded_result = decode_data(call_response.methodResponse.value, call_response.methodResponse.type)
    logger.info("Prediction result: %s", decoded_result)
    assert decoded_result and isinstance(decoded_result, dict)


@pytest.mark.forked
def test_call_without_setup_failure(grpc_context):
    logger.info("Starting test: test_call_without_setup_failure")
    # Test case for a method call before setup
    servicer = DynamicSubclassServicer(code_directory="models_examples")

    request = CallRequest(
        methodName="predict",
        methodArguments=[],
        methodKwArguments=[]
    )

    call_response = servicer.Call(request, grpc_context)
    assert call_response.status and call_response.status.code == "FAILED_PRECONDITION", print(call_response.status)
    assert call_response.status and call_response.status.message == "Setup has not been called yet", print(call_response.status)


@pytest.mark.forked
def test_setup_failure_invalid_class(grpc_context, example_code_path):
    logger.info("Starting test: test_setup_failure_invalid_class")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)

    request = SetupRequest(
        className="InvalidModel",
        instanceArguments=[],
        instanceKwArguments=[]
    )

    call_response = servicer.Setup(request, grpc_context)

    assert call_response.status and call_response.status.code == "SETUP_FAILED", print(call_response.status)
    assert call_response.status and call_response.status.message == "Invalid class name 'InvalidModel'. Use 'module.ClassName' format.", print(call_response.status)


@pytest.mark.forked
def test_call_invalid_method_failure(grpc_context, example_code_path):
    logger.info("Starting test: test_call_invalid_method_failure")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)
    request = SetupRequest(
        className="trackerbase.TrackerBase",
        instanceArguments=[],
        instanceKwArguments=[]
    )
    response = servicer.Setup(request, grpc_context)
    assert response is not None, print(grpc_context.abort.call_args)

    # Now, attempt to call a nonexistent method
    call_request = CallRequest(
        methodName="non_existent_method",
        methodArguments=[],
        methodKwArguments=[]
    )

    call_response = servicer.Call(call_request, grpc_context)

    assert call_response.status and call_response.status.code == "BAD_IMPLEMENTATION", print(call_response.status)
    assert call_response.status and call_response.status.message == 'Method "non_existent_method" not found in class "QuantileRegressionRiverTracker"', print(call_response.status)


@pytest.mark.forked
def test_rest(grpc_context, example_code_path):
    logger.info("Starting test: test_rest")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)

    # Test Rest without setup
    rest_response = servicer.Rest(request=None, context=grpc_context)
    assert rest_response.status and rest_response.status.code == "SUCCESS", print(rest_response.status)
    assert rest_response.status and rest_response.status.message == "No instance exists to reset", print(rest_response.status)

    # Test Rest after setup
    setup_request = SetupRequest(
        className="trackerbase.TrackerBase",
        instanceArguments=[],
        instanceKwArguments=[]
    )
    setup_response = servicer.Setup(setup_request, grpc_context)
    assert setup_response.status and setup_response.status.code == "SUCCESS", print(setup_response.status)

    rest_response = servicer.Rest(request=None, context=grpc_context)
    assert rest_response.status and rest_response.status.code == "SUCCESS", print(rest_response.status)
    assert rest_response.status and rest_response.status.message == "Instance successfully reset", print(rest_response.status)


@pytest.mark.forked
def test_setup_and_call_failed(grpc_context, example_code_path):
    logger.info("Starting test: test_setup_and_call_success")
    logger.debug(f"code_directory: {example_code_path}")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)
    response = None
    request = SetupRequest(
        className="trackerbase.TrackerBase",
        instanceArguments=[],
        instanceKwArguments=[]
    )
    response = servicer.Setup(request, grpc_context)

    assert response is not None, print(grpc_context.abort.call_args)

    payload_raw = {}
    payload: bytes = encode_data(VariantType.JSON, payload_raw)
    # Call phase
    call_request = CallRequest(
        methodName="tick",
        methodArguments=[Argument(position=1, data=Variant(type=VariantType.JSON, value=payload))],
        methodKwArguments=[]
    )

    call_response = servicer.Call(call_request, grpc_context)

    assert call_response.status and call_response.status.code == "MODEL_FAILED", print(call_response.status)
    assert call_response.status and call_response.status.message is not None


@pytest.mark.forked
def test_call_with_optional_args(grpc_context, example_code_path):
    logger.info("Starting test: test_setup_and_call_success")
    logger.debug(f"code_directory: {example_code_path}")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)
    response = None
    request = SetupRequest(
        className="trackerbase.TrackerBase",
        instanceArguments=[],
        instanceKwArguments=[]
    )
    response = servicer.Setup(request, grpc_context)

    assert response is not None, print(grpc_context.abort.call_args)

    payload_raw = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
    payload: bytes = encode_data(VariantType.JSON, payload_raw)
    # Call phase
    call_request = CallRequest(
        methodName="tick",
        methodArguments=[Argument(position=1, data=Variant(type=VariantType.JSON, value=payload))],
        methodKwArguments=[KwArgument(keyword="optional", data=Variant(type=VariantType.INT, value=encode_data(VariantType.INT, 1)))]
    )

    call_response = servicer.Call(call_request, grpc_context)
    assert call_response is not None, print(grpc_context.abort.call_args)
    assert call_response.status and call_response.status.code == "SUCCESS", print(call_response.status)
    assert call_response.methodResponse.type == VariantType.NONE



@pytest.fixture
def dummy_with_benchmark_code_path():
    return os.path.dirname(__file__) + "/models_examples/dummy_with_benchmark"


@pytest.mark.forked
def test_skip_classes_in_same_package(dummy_with_benchmark_code_path):
    from model_runner.utils.class_resolver import load_instance

    instance = load_instance(
        code_path=dummy_with_benchmark_code_path,
        base_class_name="trackerbase.TrackerBase",
    )

    assert type(instance).__name__ != "BenchmarkTracker", "Instance should not be in the same package"


if __name__ == '__main__':
    pytest.main()
