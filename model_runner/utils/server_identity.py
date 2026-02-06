def build_server_headers(
    message_b64: str,
    signature_b64: str,
    wallet_pubkey_b58: str
):
    """
    Build headers that the server will send on each RPC:
      x-server-auth-message, x-server-auth-signature, x-server-wallet-pubkey
    """
    headers = (
        ("x-server-auth-message", message_b64),
        ("x-server-auth-signature", signature_b64),
        ("x-server-wallet-pubkey", wallet_pubkey_b58),
    )
    return headers
