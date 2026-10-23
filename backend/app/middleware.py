import json

from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.rate_limits import consume


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = get_settings()
        request = Request(scope)

        async def protected_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                    ]
                )
                if settings.environment == "production":
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                message["headers"] = headers
            await send(message)

        async def reject(status, detail, headers=None):
            await JSONResponse({"detail": detail}, status_code=status, headers=headers)(
                scope, receive, protected_send
            )

        is_api = scope["path"].startswith("/api/")
        if not is_api or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, protected_send)
        ip = request.client.host if request.client else "unknown"

        async def check(identity, limit):
            allowed, retry = await run_in_threadpool(consume, identity, limit)
            if not allowed:
                await reject(
                    429,
                    "Too many requests. Please wait before trying again.",
                    {"Retry-After": str(retry)},
                )
            return allowed

        try:
            if not await check(f"api:{ip}", settings.api_limit):
                return
            if scope["path"] == "/api/csrf" and not await check(f"csrf:{ip}", settings.csrf_limit):
                return
            if scope["path"] == "/api/login" and scope["method"] == "POST":
                if not await check(f"login:{ip}", settings.login_ip_limit):
                    return
            data = bytearray()
            more = True
            while more:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                data.extend(message.get("body", b""))
                if len(data) > settings.body_limit_bytes:
                    return await reject(413, "Request body too large.")
                more = message.get("more_body", False)
            if scope["path"] == "/api/login" and scope["method"] == "POST":
                try:
                    body = json.loads(data)
                    email = body.get("email", "") if isinstance(body, dict) else ""
                    email = email.strip().lower() if isinstance(email, str) else ""
                except (ValueError, UnicodeDecodeError):
                    email = ""
                if not await check(f"account:{ip}:{email}", settings.login_account_limit):
                    return
        except RedisError:
            return await reject(503, "Sign-in service temporarily unavailable.")
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        await self.app(scope, replay, protected_send)
