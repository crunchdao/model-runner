import grpc


class ServerIdentityInterceptor(grpc.ServerInterceptor):
    def __init__(self, server_headers: tuple[tuple[str, str], ...]):
        """
        server_headers = tuple of (key, value) strings to send on each RPC.
        Ex:
          (
            ("x-server-auth-message", "..."),
            ("x-server-auth-signature", "..."),
            ("x-server-wallet-pubkey", "..."),
          )
        """
        self._server_headers = server_headers

    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        if handler.unary_unary is None:
            return handler

        original_unary_unary = handler.unary_unary

        def new_unary_unary(request, context: grpc.ServicerContext):
            context.send_initial_metadata(self._server_headers)

            return original_unary_unary(request, context)

        return grpc.unary_unary_rpc_method_handler(
            new_unary_unary,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
