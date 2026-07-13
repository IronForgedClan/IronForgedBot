from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
PATH_MAX_LENGTH = 512
ERROR_MAX_LENGTH = 512
USER_AGENT_MAX_LENGTH = 512
IP_MAX_LENGTH = 64


def get_client_ip(request: Request) -> str | None:
    if request.client is not None:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return None
