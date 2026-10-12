"""Admin endpoints — audit logs, analytics, health.

Route split: reads (logs/analytics/activity/breakdown/health) allow any signed-in
account — scoped to their own rows unless admin (who sees everything).
Provider keys live at /auth/providers (per-user BYOK); user management stays admin-only."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.auth import AuthContext, get_current_user
from ..circuit_breaker.circuit_breaker import CircuitBreakerRegistry
from ..database import get_db
from ..models.audit_log import AuditLog
from ..timeutil import utc_today

router = APIRouter(prefix="/admin", tags=["admin"])


def _scope(auth: AuthContext):
    """Rows the caller may see: admin/legacy key -> everything; member -> own only."""
    if auth.role == "admin":
        return None
    if not auth.user_id:  # defensive: non-admin without a user row sees nothing
        return false()
    return AuditLog.user_id == uuid.UUID(auth.user_id)


def _filter(auth: AuthContext) -> list:
    cond = _scope(auth)
    return [cond] if cond is not None else []


@router.get("/logs")
async def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    stmt = (
        select(AuditLog)
        .where(*_filter(auth))
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": str(lg.id), "timestamp": lg.timestamp.isoformat(),
            "provider": lg.provider, "model_requested": lg.model_requested,
            "model_served": lg.model_served, "input_tokens": lg.input_tokens,
            "output_tokens": lg.output_tokens, "cost_usd": lg.cost_usd,
            "latency_ms": lg.latency_ms, "status_code": lg.status_code,
            "ttft_ms": lg.ttft_ms, "tokens_per_sec": lg.tokens_per_sec,
            "finish_reason": lg.finish_reason, "is_cached": lg.is_cached,
            "cache_saved_usd": lg.cache_saved_usd, "trace_id": lg.trace_id,
        }
        for lg in result.scalars().all()
    ]


@router.get("/health")
async def admin_health(http_request: Request, auth: AuthContext = Depends(get_current_user)):
    circuit_breakers: CircuitBreakerRegistry = http_request.app.state.handler.circuit_breakers
    return {"circuit_breakers": await circuit_breakers.all_status()}


@router.get("/analytics")
async def analytics(
    days: int = Query(default=7, ge=1, le=366),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    since = utc_today() - timedelta(days=days)
    stmt = (
        select(
            AuditLog.provider,
            func.count(AuditLog.id).label("total"),
            func.sum(AuditLog.input_tokens).label("input_tokens"),
            func.sum(AuditLog.output_tokens).label("output_tokens"),
            func.sum(AuditLog.cost_usd).label("cost"),
            func.avg(AuditLog.latency_ms).label("avg_latency"),
            func.avg(AuditLog.ttft_ms).label("avg_ttft"),
            func.avg(AuditLog.tokens_per_sec).label("avg_tps"),
            # length-trimmed responses: a silent quality signal
            func.sum(case((AuditLog.finish_reason == "length", 1), else_=0)).label("truncated"),
            func.sum(AuditLog.cache_saved_usd).label("cache_saved"),
        )
        .where(AuditLog.timestamp >= since)
        .where(*_filter(auth))
        .group_by(AuditLog.provider)
    )
    return [
        {
            "provider": r.provider, "total_requests": r.total,
            "total_input_tokens": r.input_tokens or 0,
            "total_output_tokens": r.output_tokens or 0,
            "total_cost_usd": float(r.cost or 0),
            "avg_latency_ms": float(r.avg_latency or 0),
            "avg_ttft_ms": float(r.avg_ttft) if r.avg_ttft is not None else None,
            "avg_tokens_per_sec": float(r.avg_tps) if r.avg_tps is not None else None,
            "truncated": r.truncated or 0,
            "cache_saved_usd": float(r.cache_saved or 0),
        }
        for r in (await db.execute(stmt)).all()
    ]


@router.get("/activity")
async def activity(
    days: int = Query(default=7, ge=1, le=366),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    """Per-day totals for activity charts. Days with no traffic are omitted."""
    since = utc_today() - timedelta(days=days)
    stmt = (
        select(
            func.date(AuditLog.timestamp).label("day"),
            func.count(AuditLog.id).label("requests"),
            func.sum(AuditLog.input_tokens).label("input_tokens"),
            func.sum(AuditLog.output_tokens).label("output_tokens"),
            func.sum(AuditLog.cost_usd).label("cost"),
            func.avg(AuditLog.latency_ms).label("avg_latency"),
            func.sum(case((AuditLog.is_cached, 1), else_=0)).label("cached"),
            func.avg(AuditLog.ttft_ms).label("avg_ttft"),
            func.avg(AuditLog.tokens_per_sec).label("avg_tps"),
            func.sum(AuditLog.cache_saved_usd).label("cache_saved"),
        )
        .where(AuditLog.timestamp >= since)
        .where(*_filter(auth))
        .group_by(func.date(AuditLog.timestamp))
        .order_by("day")
    )
    return [
        {
            "date": r.day.isoformat(),
            "requests": r.requests or 0,
            "input_tokens": r.input_tokens or 0,
            "output_tokens": r.output_tokens or 0,
            "cost_usd": float(r.cost or 0),
            "avg_latency_ms": float(r.avg_latency or 0),
            "cached": r.cached or 0,
            "avg_ttft_ms": float(r.avg_ttft) if r.avg_ttft is not None else None,
            "avg_tokens_per_sec": float(r.avg_tps) if r.avg_tps is not None else None,
            "cache_saved_usd": float(r.cache_saved or 0),
        }
        for r in (await db.execute(stmt)).all()
    ]


@router.get("/breakdown")
async def breakdown(
    days: int = Query(default=7, ge=1, le=366),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
):
    """Top providers and models by spend — served requests only (503s from
    unroutable models are not "usage")."""
    since = utc_today() - timedelta(days=days)
    served = (AuditLog.timestamp >= since, AuditLog.status_code == 200, *_filter(auth))

    provider_rows = (
        await db.execute(
            select(
                AuditLog.provider.label("name"),
                func.count(AuditLog.id).label("requests"),
                func.sum(AuditLog.cost_usd).label("cost"),
            )
            .where(*served)
            .group_by(AuditLog.provider)
            .order_by(func.sum(AuditLog.cost_usd).desc())
            .limit(8)
        )
    ).all()

    model_rows = (
        await db.execute(
            select(
                AuditLog.model_served.label("model"),
                func.count(AuditLog.id).label("requests"),
                func.sum(AuditLog.cost_usd).label("cost"),
                func.avg(AuditLog.latency_ms).label("avg_latency"),
                func.avg(AuditLog.ttft_ms).label("avg_ttft"),
                func.avg(AuditLog.tokens_per_sec).label("avg_tps"),
                func.sum(case((AuditLog.finish_reason == "length", 1), else_=0)).label("truncated"),
            )
            .where(*served)
            .group_by(AuditLog.model_served)
            .order_by(func.count(AuditLog.id).desc())
            .limit(8)
        )
    ).all()

    finish_rows = (
        await db.execute(
            select(AuditLog.finish_reason.label("reason"), func.count(AuditLog.id).label("n"))
            .where(AuditLog.timestamp >= since, AuditLog.finish_reason.is_not(None), *_filter(auth))
            .group_by(AuditLog.finish_reason)
            .order_by(func.count(AuditLog.id).desc())
        )
    ).all()

    return {
        "by_provider": [
            {"name": r.name, "requests": r.requests or 0, "cost_usd": float(r.cost or 0)}
            for r in provider_rows
        ],
        "by_model": [
            {"model": r.model, "requests": r.requests or 0,
             "cost_usd": float(r.cost or 0), "avg_latency_ms": float(r.avg_latency or 0),
             "avg_ttft_ms": float(r.avg_ttft) if r.avg_ttft is not None else None,
             "avg_tokens_per_sec": float(r.avg_tps) if r.avg_tps is not None else None,
             "truncated": r.truncated or 0}
            for r in model_rows
        ],
        "by_finish_reason": [
            {"reason": r.reason, "count": r.n or 0} for r in finish_rows
        ],
    }
