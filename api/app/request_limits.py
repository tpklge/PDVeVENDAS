"""Bound request bodies before JSON parsing, including chunked transfers."""
import json

MAX_BODY = 65536


class RequestLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def reject(status, message):
            correlation = scope.get("state", {}).get("correlation_id", "")
            data = json.dumps({"error": {"code": f"HTTP_{status}", "message": message,
                                        "correlation_id": correlation}}).encode()
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
            await send({"type": "http.response.body", "body": data})

        lengths = [value for key, value in scope.get("headers", []) if key.lower() == b"content-length"]
        if lengths:
            if any(not value.isdigit() or len(value) > 10 for value in lengths) or len(set(lengths)) != 1:
                return await reject(400, "Tamanho da solicitação inválido.")
            if int(lengths[0]) > MAX_BODY:
                return await reject(413, "Solicitação excede o limite de 64 KiB.")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY:
                return await reject(413, "Solicitação excede o limite de 64 KiB.")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
