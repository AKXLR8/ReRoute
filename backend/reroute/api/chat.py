"""Chat completions + models — OpenAI-compatible wire format."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.auth import AuthContext, get_current_user
from ..database import get_db
from ..providers import byok
from ..rate_limit.rate_limiter import RateLimitExceeded
from ..schemas.chat import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["chat"])


def _require_user(auth: AuthContext) -> str:
    """Per-user BYOK: chat/models need a signed-in account — no key-less paths."""
    if not auth.user_id:
        raise HTTPException(
            status_code=401,
            detail="Chat requires a signed-in user account (keys are per-user)",
        )
    return auth.user_id


@router.get("/models")
async def list_models(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """Models the caller can actually use — their connected keys + ollama."""
    user_id = _require_user(auth)
    redis = http_request.app.state.redis
    instances = await byok.resolve_user(redis, user_id, http_request.app.state.registry, db)
    models = {}
    for provider in instances:
        for model in provider.models():
            if model not in models:
                models[model] = {"id": model, "owned_by": provider.name, "providers": []}
            models[model]["providers"].append(provider.name)

    return {"data": list(models.values()), "object": "list"}


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completions(
    request: ChatRequest,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
) -> ChatResponse | StreamingResponse:
    # Members chat too — spend always comes from the caller's own BYOK keys
    user_id = _require_user(auth)
    redis = http_request.app.state.redis
    handler = http_request.app.state.handler
    providers = await byok.resolve_user(redis, user_id, http_request.app.state.registry, db)

    if request.stream:
        async def event_stream():
            # StreamingResponse already sent HTTP 200 by the time the generator
            # runs, so in-flight failures can only surface as an SSE error event
            # (same shape as guard violations) — never a dead socket.
            try:
                async for chunk in handler.handle_stream(request, db, auth, providers):
                    yield chunk
            except RateLimitExceeded as e:
                yield f'data: {json.dumps({"error": str(e), "status": 429})}\n\n'
            except ValueError as e:
                yield f'data: {json.dumps({"error": str(e), "status": 503})}\n\n'
            except Exception:
                log.exception("Unhandled error in stream")
                yield f'data: {json.dumps({"error": "Internal error", "status": 500})}\n\n'
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        return await handler.handle_chat(request, db, auth, providers)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail=str(e),
            headers={"Retry-After": str(int(e.retry_after))},
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception:
        log.exception("Unhandled error in chat completions")
        raise HTTPException(status_code=500, detail="Internal error") from None
