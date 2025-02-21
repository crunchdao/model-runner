# File: tests/test_dynamic_subclass_servicer.py
import os
import sys

import grpc
import pytest
from google.protobuf import empty_pb2

from model_runner.grpc.generated.commons_pb2 import Variant, VariantType, Argument, KwArgument

from model_runner.grpc.generated.train_infer_pb2 import InferRequest, InferResponse
from model_runner.servicers.train_infer_servicer import TrainInferStreamServicer

from model_runner.utils.datatype_transformer import detect_data_type, decode_data
from model_runner.utils.datatype_transformer import encode_data


@pytest.fixture
def grpc_context(mocker):
    mock = mocker.Mock(spec=grpc.ServicerContext)

    def abort_side_effect(code, details):
        grpc_context.abort_args = (code, details)
        raise grpc.RpcError(f"gRPC Aborted: {code}, {details}")

    mock.abort.side_effect = abort_side_effect

    return mock


@pytest.fixture
def example_code_path():
    return os.path.dirname(__file__) + "/models_examples/bill"


def test_setup_and_predict_success(grpc_context, example_code_path):
    print(f"model_directory: {example_code_path}")

    servicer = TrainInferStreamServicer(code_directory=example_code_path, resource_directory="", has_gpu=False)
    response = servicer.Setup(empty_pb2.Empty(), grpc_context)
    assert response is not None, print(grpc_context.abort.call_args)

    payload_raw = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
    print(f'payload: {payload_raw}')
    payload: bytes = encode_data(VariantType.JSON, payload_raw)
    # Call phase
    infer_request = InferRequest(
        argument=Variant(type=VariantType.JSON, value=payload),
    )
    infer_response: InferResponse = servicer.Infer(infer_request, grpc_context)
    assert infer_response is not None, print(grpc_context.abort.call_args)

    decoded_result = decode_data(infer_response.prediction.value, infer_response.prediction.type)
    print("prediction:", decoded_result)
    assert decoded_result and isinstance(decoded_result, dict)
