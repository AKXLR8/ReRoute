from __future__ import annotations

from pydantic import BaseModel


class ProviderConnect(BaseModel):
    """BYOK — a provider credential. Key is write-only."""

    api_key: str = ""
    base_url: str | None = None


class ProviderRead(BaseModel):
    provider: str
    base_url: str | None
    key_masked: str
    created_at: str | None = None
