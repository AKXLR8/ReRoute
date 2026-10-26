"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .api import admin_router, auth_router, chat_router, users_router
from .config import get_settings
from .database import get_db
from .observability.metrics import metrics_collector
from .observability.telemetry import prometheus_endpoint, setup_telemetry, shutdown

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

# Public /status is cacheable: it is unauthenticated and must not become a free
# probe amplifier against Postgres/Redis.
_status_cache: dict[str, object] = {}
_STATUS_TTL_SECONDS = 10


async def request_size_limit_middleware(request: Request, call_next):
    settings = get_settings()
    max_size = settings.max_request_body_bytes
    content_length = request.headers.get("Content-Length")
    if content_length is not None:
        try:
            cl = int(content_length)
            if cl > max_size:
                return Response(
                    content=f"Request body too large. Max {max_size} bytes.",
                    status_code=413,
                    headers={"Retry-After": "60"},
                )
        except ValueError:
            pass
    return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: wire all dependencies. Shutdown: dispose resources."""
    settings = get_settings()
    log.info("ReRouteAI starting — %s", settings.app_name)

    from redis.asyncio import Redis as _Redis

    from .cache.dedup import RequestDeduplicator
    from .cache.semantic_cache import SemanticCache
    from .circuit_breaker.circuit_breaker import CircuitBreakerRegistry
    from .gateway.handler import GatewayHandler
    from .providers.anthropic_provider import AnthropicProvider
    from .providers.base import ProviderRegistry
    from .providers.cerebras_provider import CerebrasProvider
    from .providers.gemini_provider import GeminiProvider
    from .providers.groq_provider import GroqProvider
    from .providers.mercury_provider import MercuryProvider
    from .providers.ollama_provider import OllamaProvider
    from .providers.openai_provider import OpenAIProvider
    from .providers.together_provider import TogetherProvider
    from .rate_limit.rate_limiter import RateLimiter
    from .retry.retry import RetryEngine
    from .router.router import Router

    # Redis — health_check_interval pings pooled connections before reuse; cloud Redis
    # (Upstash etc.) closes idle sockets, and reusing a dead one kills the request.
    redis = _Redis.from_url(
        settings.redis_url,
        decode_responses=False,
        socket_connect_timeout=10,
        socket_timeout=10,
        health_check_interval=30,
        retry_on_timeout=True,
    )
    app.state.redis = redis

    # Provider registry — shared templates only. Per-user BYOK clones are built
    # per request in byok.resolve_user(); the gateway's env keys are never routed
    # to (users connect their own keys).
    registry = ProviderRegistry()
    registry.register(OpenAIProvider(api_key=settings.openai_api_key))
    registry.register(AnthropicProvider(api_key=settings.anthropic_api_key))
    registry.register(GeminiProvider(api_key=settings.gemini_api_key))
    registry.register(GroqProvider(api_key=settings.groq_api_key))
    registry.register(MercuryProvider(api_key=settings.mercury_api_key))
    registry.register(CerebrasProvider(api_key=settings.cerebras_api_key))
    registry.register(TogetherProvider(api_key=settings.together_api_key))
    registry.register(OllamaProvider(base_url=settings.ollama_base_url))
    app.state.registry = registry

    # Core components
    retry_engine = RetryEngine()
    rate_limiter = RateLimiter(redis)
    cache = SemanticCache(redis)
    circuit_breakers = CircuitBreakerRegistry(redis)
    router = Router(registry, circuit_breakers, retry_engine)

    handler = GatewayHandler(
        router=router,
        rate_limiter=rate_limiter,
        cache=cache,
        circuit_breakers=circuit_breakers,
        deduplicator=RequestDeduplicator(),
    )
    app.state.handler = handler

    # Background health checks (every 30s)
    async def health_loop() -> None:
        while True:
            for name in list(registry.all()):
                target = registry.get(name)
                if target is None or (not target.api_key and name != "ollama"):
                    continue  # probe shared/env-keyed templates; user clones keep own health
                try:
                    healthy = await target.health_check()
                    metrics_collector.set_provider_health(name, healthy)
                except Exception as exc:
                    log.debug("Health check failed for %s: %s", name, exc)
            await asyncio.sleep(30)

    health_task = asyncio.create_task(health_loop())
    log.info("Providers registered: %s", list(registry.all().keys()))

    # Run alembic migrations on startup. Portable (sys.executable, package-relative
    # cwd) so the same code works on Windows dev, Linux containers, and CI.
    # Set MIGRATE_ON_STARTUP=false when migrations run as a separate release step
    # (multi-replica deploys must not race N concurrent upgrade runs).
    if settings.migrate_on_startup:
        import subprocess
        import sys
        from pathlib import Path

        backend_dir = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            log.error("Migration failed: %s", result.stderr)
            raise RuntimeError(f"Database migration failed: {result.stderr}")
        log.info("Database migrations applied: %s", result.stdout.strip())

    # Start BYOK invalidation listener (multi-worker cache sync)
    from .database import get_session_factory
    from .providers.byok import start_invalidation_listener
    invalidation_task = asyncio.create_task(
        start_invalidation_listener(redis, registry, get_session_factory())
    )
    log.info("BYOK invalidation listener started")

    yield

    # Shutdown
    from contextlib import suppress

    from .database import dispose_engine
    health_task.cancel()
    invalidation_task.cancel()
    with suppress(asyncio.CancelledError):
        await health_task
    with suppress(asyncio.CancelledError):
        await invalidation_task
    await registry.aclose_all()
    await dispose_engine()
    await redis.aclose()
    shutdown()  # flush pending trace spans
    log.info("ReRouteAI stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    prod = settings.environment == "production"

    app = FastAPI(
        title=settings.app_name,
        description="Enterprise Multi-Provider LLM Gateway",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None if prod else "/redoc",
        openapi_url="/openapi.json",
    )

    # Request size limit (runs first to reject oversized bodies early)
    app.middleware("http")(request_size_limit_middleware)

    # CORS — browsers reject "*" combined with credentials, so only
    # send credentials for explicit origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    # Tracing (opt-in via OTEL_EXPORTER_OTLP_ENDPOINT) — request spans wrap everything above
    setup_telemetry(app)

    # Routes
    app.include_router(chat_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(users_router)

    # Prometheus metrics endpoint
    app.add_api_route(
        "/metrics", prometheus_endpoint, methods=["GET"], include_in_schema=False
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/status", include_in_schema=False)
    async def status(http_request: Request, db: AsyncSession = Depends(get_db)):
        """Public status feed. Aggregate provider health only - no keys, URLs,
        models, or user data (provider names are already on the landing page)."""
        now = time.monotonic()
        cached = _status_cache.get("body")
        cached_at = now - float(_status_cache.get("at", 0))
        if isinstance(cached, dict) and cached_at < _STATUS_TTL_SECONDS:
            return cached

        checks: dict[str, str] = {"api": "ok"}
        try:
            await db.execute(select(1))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"

        redis = getattr(http_request.app.state, "redis", None)
        if redis is None:
            checks["redis"] = "unknown"
        else:
            try:
                await redis.ping()
                checks["redis"] = "ok"
            except Exception:
                checks["redis"] = "error"

        registry = getattr(http_request.app.state, "registry", None)
        handler = getattr(http_request.app.state, "handler", None)
        breakers = getattr(handler, "circuit_breakers", None)
        circuits: dict = {}
        if breakers is not None:
            try:
                circuits = await breakers.all_status()
            except Exception:
                circuits = {}

        providers = []
        if registry is not None:
            for name, provider in sorted(registry.all().items()):
                health = provider.health
                circuit = str(circuits.get(name, {}).get("state", "closed"))
                providers.append(
                    {
                        "name": name,
                        "health": (
                            "unknown"
                            if not health.last_check
                            else ("up" if health.available else "down")
                        ),
                        "circuit": circuit,
                        "latency_ms": round(health.latency_ms, 1) if health.last_check else None,
                    }
                )

        healthy = checks["database"] == "ok" and checks["redis"] != "error"
        degraded = not healthy or any(
            p["health"] == "down" or p["circuit"] == "open" for p in providers
        )
        body = {
            "service": "degraded" if degraded else "ok",
            "checks": checks,
            "providers": providers,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        _status_cache.update(body=body, at=now)
        return body

    @app.get("/")
    async def root():
        return {"service": "reroute", "health": "/health"}

    @app.get("/readyz")
    async def ready(http_request: Request, db: AsyncSession = Depends(get_db)):
        """Readiness: Postgres + Redis reachable. Use for k8s readinessProbe."""
        try:
            await db.execute(select(1))
            await http_request.app.state.redis.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="not ready") from None
        return {"status": "ready"}

    return app
