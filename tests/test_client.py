import grpc
from google.protobuf import empty_pb2

from model_runner.grpc.generated.train_infer_pb2_grpc import TrainInferStreamServiceStub
from model_runner.grpc.generated.dynamic_subclass_pb2_grpc import DynamicSubclassService, DynamicSubclassServiceStub

from model_runner.grpc.generated.train_infer_pb2 import InferRequest, InferResponse
from model_runner.grpc.generated.commons_pb2 import Variant, VariantType, Argument
from model_runner.grpc.generated.dynamic_subclass_pb2 import SetupRequest, CallRequest, CallResponse

from model_runner.utils.datatype_transformer import encode_data, decode_data

SERVER_ADDRESS = "54.229.63.5:50051"


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
        stub.Setup(SetupRequest(className='birdgame.trackers.trackerbase.TrackerBase'))
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
