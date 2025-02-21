# File: tests/test_dynamic_subclass_servicer.py
import os
import sys

import grpc
import pytest

from model_runner.grpc.generated.commons_pb2 import Variant, VariantType, Argument, KwArgument
from model_runner.grpc.generated.dynamic_subclass_pb2 import SetupRequest, CallRequest
from model_runner.grpc.generated.dynamic_subclass_pb2_grpc import DynamicSubclassServiceServicer
from model_runner.servicers.dynamic_subclass_servicer import DynamicSubclassServicer
from model_runner.utils.datatype_transformer import detect_data_type, decode_data
from model_runner.utils.datatype_transformer import encode_data


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


def test_setup_and_call_success(grpc_context, example_code_path):
    print(f"code_directory: {example_code_path}")
    servicer = DynamicSubclassServicer(code_directory=example_code_path)
    response = None
    request = SetupRequest(
        className="birdgame.trackers.trackerbase.TrackerBase",
        instanceArguments=[],
        instanceKwArguments=[]
    )
    response = servicer.Setup(request, grpc_context)

    assert response is not None, print(grpc_context.abort.call_args)

    payload_raw = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
    print(f'payload: {payload_raw}')
    payload: bytes = encode_data(VariantType.JSON, payload_raw)
    # Call phase
    call_request = CallRequest(
        methodName="tick",
        methodArguments=[Argument(position=1, data=Variant(type=VariantType.JSON, value=payload))],
        methodKwArguments=[]
    )
    call_response = servicer.Call(call_request, grpc_context)
    assert call_response is not None, print(grpc_context.abort.call_args)

    call_request = CallRequest(
        methodName="predict",
        methodArguments=[],
        methodKwArguments=[]
    )
    call_response = servicer.Call(call_request, grpc_context)
    assert call_response is not None, print(grpc_context.abort.call_args)
    decoded_result = decode_data(call_response.methodResponse.value, call_response.methodResponse.type)
    print("prediction:", decoded_result)
    assert decoded_result and isinstance(decoded_result, dict)


def test_call_without_setup_failure(grpc_context):
    # Test case for a method call before setup
    servicer = DynamicSubclassServicer(code_directory="models_examples")

    request = CallRequest(
        methodName="predict",
        methodArguments=[],
        methodKwArguments=[]
    )

    with pytest.raises(grpc.RpcError):
        servicer.Call(request, grpc_context)

    assert grpc_context.abort_args[0] == grpc.StatusCode.FAILED_PRECONDITION
    assert grpc_context.abort_args[1] == 'Setup has not been called yet'


def test_setup_failure_invalid_class(grpc_context, example_code_path):
    servicer = DynamicSubclassServicer(code_directory=example_code_path)

    request = SetupRequest(
        className="InvalidModel",
        instanceArguments=[],
        instanceKwArguments=[]
    )

    with pytest.raises(grpc.RpcError):
        servicer.Setup(request, grpc_context)

    assert grpc_context.abort_args[0] == grpc.StatusCode.FAILED_PRECONDITION
    assert grpc_context.abort_args[1] == "Invalid class name 'InvalidModel'. Use 'module.ClassName' format."


def test_call_invalid_method_failure(grpc_context, example_code_path):
    servicer = DynamicSubclassServicer(code_directory=example_code_path)
    request = SetupRequest(
        className="birdgame.trackers.trackerbase.TrackerBase",
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

    with pytest.raises(grpc.RpcError):
        servicer.Call(call_request, grpc_context)

    assert grpc_context.abort_args[0] == grpc.StatusCode.INTERNAL
    assert grpc_context.abort_args[1] == f'Method "non_existent_method" not found in class "QuantileRegressionRiverTracker"'
