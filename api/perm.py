from fastapi import Depends, HTTPException, Request, status

from api.deps import get_current_consumer
from api.models import ApiConsumer


def requires_perm(perm: str):
    """Dep factory. Sets request.state.required_perm for audit, raises 403 if missing.

    Declare this in the route signature BEFORE the rate_limit dep so that
    required_perm is set on request.state before the rate-limit check runs.
    FastAPI resolves independent signature deps in declaration order, which
    guarantees 429 audit rows have required_perm populated.
    """

    async def dep(
        request: Request,
        consumer: ApiConsumer = Depends(get_current_consumer),
    ) -> None:
        request.state.required_perm = perm
        if perm not in (consumer.perms or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {perm}",
            )

    return dep
