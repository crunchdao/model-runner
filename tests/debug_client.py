import asyncio
from time import sleep

import grpc
import pytest
from google.protobuf import empty_pb2
from grpc_health.v1 import health_pb2_grpc, health_pb2

from model_runner.grpc.generated.train_infer_pb2_grpc import TrainInferStreamServiceStub
from model_runner.grpc.generated.dynamic_subclass_pb2_grpc import DynamicSubclassService, DynamicSubclassServiceStub

from model_runner.grpc.generated.train_infer_pb2 import InferRequest, InferResponse
from model_runner.grpc.generated.commons_pb2 import Variant, VariantType, Argument, KwArgument
from model_runner.grpc.generated.dynamic_subclass_pb2 import SetupRequest, CallRequest, CallResponse

from model_runner.utils.datatype_transformer import encode_data, decode_data

SERVER_ADDRESS = "localhost:50051"


# @pytest.mark.asyncio
# async def test_grpc_streaming_from_user_input():
#     async with grpc.aio.insecure_channel(SERVER_ADDRESS) as channel:
#         stub = ModelRunnerStub(channel)
#
#         async def generate_requests():
#             while True:
#                 user_input = await asyncio.to_thread(input, "Enter a double value: ")
#                 if user_input.lower() == "stop":
#                     break
#                 try:
#                     double_value = float(user_input)
#                     yield InferRequest(
#                         arguments=[
#                             Argument(type=DataType.DOUBLE, name="x", value=encode_data(DataType.DOUBLE, double_value)),
#                             Argument(type=DataType.STRING, name="stream", value=encode_data(DataType.STRING, "streamA")),
#                         ]
#                     )
#                 except ValueError:
#                     print("Invalid input. Please enter a valid double value.")
#
#         async for response in stub.Infer(generate_requests()):
#             print(f'prediction : {decode_data(response.prediction, response.type)}\n')
#
#
# # Todo fix
# def test_grpc_streaming():
#     with grpc.insecure_channel(SERVER_ADDRESS) as channel:
#         stub = ModelRunnerStub(channel)
#
#         def generate_requests():
#             for i in range(5):  # Example : 5 messages
#                 yield InferRequest(
#                     arguments=[
#                         Argument(type=DataType.DOUBLE, name="x", value=encode_data(DataType.DOUBLE, 0.20 * i)),
#                         Argument(type=DataType.STRING, name="stream", value=encode_data(DataType.STRING, "streamA")),
#                     ]
#                 )
#
#         for response in stub.InferStream(generate_requests()):
#             print(decode_data(response.prediction, response.type))


# def test_grpc_infer():
#     with grpc.insecure_channel(SERVER_ADDRESS) as channel:
#         stub = ModelRunnerStub(channel)
#         stub.Setup(empty_pb2.Empty())
#         print("Stepup complete.")
#
#         for i in range(5):  # Example : 5 messages
#             value = {"x": 0.20 * i, "stream": "streamA"}
#             request = InferRequest(type=DataType.JSON,
#                                    argument=encode_data(DataType.JSON, value))
#             print(f"request x:{value}")
#             response = stub.Infer(request)
#             print(f"result {decode_data(response.prediction, response.type)}")


# please launch the server before : poetry run python __main__.py --code-directory tests/models_examples/bill
def test_grpc_infer_bird():
    with grpc.insecure_channel(SERVER_ADDRESS) as channel:
        # ModelRunnerStub is class generate and abstract remote call
        stub = TrainInferStreamServiceStub(channel)
        stub.Setup(empty_pb2.Empty())
        print("Stepup complete.")

        payload = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
        # here the call happen and call function
        request = InferRequest(argument=Variant(type=VariantType.JSON, value=encode_data(VariantType.JSON, payload)))

        infer_response: InferResponse = stub.Infer(request)
        print(f"request x:{payload}")
        response = stub.Infer(request)
        print(f"result {decode_data(response.prediction.value, response.prediction.type)}")


# please launch the server before : poetry run python __main__.py --code-directory tests/models_examples/bill
def test_grpc_infer_bird_reinit():
    with grpc.insecure_channel(SERVER_ADDRESS) as channel:
        # ModelRunnerStub is class generate and abstract remote call
        stub = TrainInferStreamServiceStub(channel)
        stub.Setup(empty_pb2.Empty())

        print("Stepup complete.")
        stub.Reinitialize(empty_pb2.Empty())

        payload = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
        # here the call happen and call function
        request = InferRequest(argument=Variant(type=VariantType.JSON, value=encode_data(VariantType.JSON, payload)))

        print(f"request x:{payload}")
        response = stub.Infer(request)
        print(f"result {decode_data(response.prediction.value, response.prediction.type)}")


def test_grpc_infer_bird_2():
    with grpc.insecure_channel(SERVER_ADDRESS) as channel:
        # ModelRunnerStub is class generate and abstract remote call
        stub = DynamicSubclassServiceStub(channel)
        stub.Setup(SetupRequest(className='birdgame.trackers.trackerbase.TrackerBase', instanceKwArguments=[KwArgument(keyword="horizon", data=Variant(type=VariantType.INT, value=encode_data(VariantType.INT, 1)))]))
        print("Stepup complete.")

        payload = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1}
        payload_encoded = encode_data(VariantType.JSON, payload)
        stub.Call(CallRequest(
            methodName='tick',
            methodArguments=[
                Argument(position=1, data=Variant(type=VariantType.JSON, value=payload_encoded))
            ])
        )

        prediction = stub.Call(CallRequest(methodName='predict'))
        decoded_result = decode_data(prediction.methodResponse.value, prediction.methodResponse.type)
        print(f"result {decoded_result}")

        # Add a reset call here
        stub.Rest(empty_pb2.Empty())
        stub.Setup(SetupRequest(className='birdgame.trackers.trackerbase.TrackerBase', instanceKwArguments=[KwArgument(keyword="horizon", data=Variant(type=VariantType.INT, value=encode_data(VariantType.INT, 1)))]))

        stub.Call(CallRequest(
            methodName='tick',
            methodArguments=[
                Argument(position=1, data=Variant(type=VariantType.JSON, value=payload_encoded))
            ])
        )

        prediction = stub.Call(CallRequest(methodName='predict'))
        decoded_result = decode_data(prediction.methodResponse.value, prediction.methodResponse.type)
        print(f"result {decoded_result}")


def test_health_call():
    with grpc.insecure_channel(SERVER_ADDRESS) as channel:
        stub = health_pb2_grpc.HealthStub(channel)
        resp = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=0.5)
        assert resp.status == health_pb2.HealthCheckResponse.SERVING


def test_grpc_message_size_limit():
    with grpc.insecure_channel(SERVER_ADDRESS) as channel:
        # ModelRunnerStub is class generate and abstract remote call
        stub = DynamicSubclassServiceStub(channel)
        stub.Setup(SetupRequest(className='birdgame.trackers.trackerbase.TrackerBase', instanceKwArguments=[KwArgument(keyword="horizon", data=Variant(type=VariantType.INT, value=encode_data(VariantType.INT, 1)))]))
        print("Stepup complete.")

        slightly_smaller_message = "a" * (63 * 1024 * 1024)  # Just under 64MB
        payload = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1, 'msg_test': slightly_smaller_message}
        payload_encoded = encode_data(VariantType.JSON, payload)
        try:
            stub.Call(CallRequest(
                methodName='tick',
                methodArguments=[
                    Argument(position=1, data=Variant(type=VariantType.JSON, value=payload_encoded))
                ])
            )
        except grpc.RpcError as e:
            assert False, f"Request below limit failed unexpectedly with error: {e}"

        try:
            large_message = "a" * (64 * 1024 * 1024)
            payload = {'falcon_location': 21.179864629354732, 'time': 230.96231205799998, 'dove_location': 19.164986723324326, 'falcon_id': 1, 'msg_test': large_message}
            payload_encoded = encode_data(VariantType.JSON, payload)
            stub.Call(CallRequest(
                methodName='tick',
                methodArguments=[
                    Argument(position=1, data=Variant(type=VariantType.JSON, value=payload_encoded))
                ])
            )
            assert False, "Request above limit succeeded unexpectedly"
        except grpc.RpcError as e:
            assert e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED


def test_secure_channel():
    # python -m model_runner.server
    # --secure
    # --code-directory docker/submission/code
    # --certificates-directory tests/certs/cruncher-nkxooffy
    # --cruncher-wallet-pubkey GKgkFy6ewf1j2oFtjAs8KNjoZMzwUiEf8Qt3MJba2hdD
    # --coordinator-wallet-pubkey 6a46qszZbLX6WCLoQb8nfwxQCYKj2yC4xXEBTwHKXy5u

    import json
    path = "tests/certs/coordinator-npxhxkph/"
    # with open(f"{path}/ca.crt", "rb") as f:
    with open(f"{path}/ca.crt", "rb") as f:
        ca_cert_for_servers = f.read()

    with open(f"{path}/tls.crt", "rb") as f:
        coord_cert = f.read()

    with open(f"{path}/tls.key", "rb") as f:
        coord_key = f.read()

    client_creds = grpc.ssl_channel_credentials(
        root_certificates=ca_cert_for_servers,  # trust runner CA / cert
        private_key=coord_key,  # coordinator private key
        certificate_chain=coord_cert,  # coordinator cert
    )

    options = (("grpc.default_authority", "model-node-13367.crunchdao.internal"),("grpc.ssl_target_name_override", "model-node-13367.crunchdao.internal"))

    with grpc.secure_channel(SERVER_ADDRESS, credentials=client_creds, options=options) as channel:
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = health_pb2_grpc.HealthStub(channel)
        resp = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=0.5)
        assert resp.status == health_pb2.HealthCheckResponse.SERVING



def test_signature_verification():
    import json
    from model_runner.utils.wallet_gelegation import verify_wallet_delegation

    JSON = """
    {
        "message_b64": "eyJjZXJ0X3B1YiI6ICJNSUlCSWpBTkJna3Foa2lHOXcwQkFRRUZBQU9DQVE4QU1JSUJDZ0tDQVFFQXdqNTRKMnJNd0NXY1JEVmsxZURQdms5QW5Zd2J5UVVXRnBnWUVqZDQ0MTZxb3dwWFJxSHYxNlRLRmg4UGxFUzJyR2NMT1JQS0ltQ1BrYTFNUkkzUnVMVzl6dkhsc2NDYmZUMDZSOCtJVHVtWUNpVE1FbTNoemRlY01hajFvaXZETVpIaHNmVWdBbzlUcTlQUzlMbGd4cTcrOGZrK05SajVTQVhpRi9iOGR1VTNKT01BbDhUWUpadlIyZVhKWENKODhoMXVoRVVmelhsMGxLMFBaZE9uUURaMXI1WU8wdnllNGIyNzNuMWs0UWhWZXpXQy9xa2hFOEVzczd6eHJxa0lnbHJlU29tQ1J0QXdlb211RnVZSFhHUGZCK0Z1VGY1ckZGQ1BkMFY5aHF3TUhRcU4zM25jVGRPUmNXMHRpaFNnV2FXQUllbjlzZERMM3JCam1RZk9ud0lEQVFBQiIsICJob3Rfa2V5IjogIkRlZGZKbXhEbUFCeHRyZVJBMlZqb1I5c3NvVGtpcGZoNDVGOW1NOEg1VWk5In0=",
        "wallet_pubkey_b58": "2VfSphzsSWQxSP29JMXUwqsbkbLdqqRPY5unziVkCko2",
        "signature_b64": "gi9KdH77azdSEKhQlVlufDJov5TQCsvEm6q2XudMmSmST6aekwvL4a8AKgAyBjVTcI1dFD3ztEeaXKZZHVSnCw=="
    }
    """

    signed_message = json.loads(JSON)
    message_b64 = signed_message.get("message_b64")
    signature_b64 = signed_message.get("signature_b64")
    wallet_pubkey_b58 = signed_message.get("wallet_pubkey_b58")

    try:
        verify_wallet_delegation(
            message_b64=message_b64,
            signature_b64=signature_b64,
            wallet_pub_b58=wallet_pubkey_b58,
            expected_wallet_pub_b58="6N5vZrrCosLZfKe6yJ5SSsurNKrdJKQrd4qhocABP1rJ",
            tls_pub=b"None",
            expected_model_id='13048',
            expected_hotkey="DNPr3bLsTMRfswkgsJLDb4Kj1fkrWE4JxjwWtPH4bAEa"
        )
        print("Verification succeeded, no exceptions raised.")
    except Exception as e:
        pytest.fail(f"Verification failed with exception: {e}")
