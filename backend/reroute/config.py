"""Application configuration loaded from environment / .env."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    # --- Database ---
    database_url: str = "postgresql+asyncpg://forge:forge@localhost:5432/reroute"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Auth ---
    jwt_secret: str = "change-me-in-production"
    # separate BYOK encryption key; empty -> derives from jwt_secret (legacy)
    fernet_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    admin_api_key: str = "change-me-admin-key"
    # bcrypt hash of ADMIN_API_KEY; if set, takes precedence over the plaintext value
    admin_api_key_hash: str = ""
    # Accounts: short-lived access JWT + rotating refresh cookie-less tokens
    access_expire_minutes: int = 15
    refresh_expire_days: int = 14
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    login_rate_limit_per_ip: int = 10  # per minute per IP

    # --- Registration / GitHub OAuth ---
    allow_registration: bool = True
    register_rate_limit_per_hour: int = 5
    # https://github.com/settings/developers -> OAuth App -> callback URL = github_redirect_uri
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    # where the OAuth callback hands the session back to the SPA
    frontend_base_url: str = "http://localhost:5173"

    # --- Provider Keys ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    mercury_api_key: str = ""
    cerebras_api_key: str = ""
    together_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- Cache ---
    semantic_cache_threshold: float = 0.92
    semantic_cache_ttl_seconds: int = 3600
    embedding_model: str = "Xenova/all-MiniLM-L6-v2"

    # --- Rate Limits (global — single-tenant gateway) ---
    default_rate_limit_rpm: int = 60
    default_rate_limit_tpm: int = 100_000
    default_rate_limit_concurrent: int = 10

    # --- Circuit Breaker ---
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: int = 30

    # --- Retry ---
    retry_max_attempts: int = 3
    retry_base_delay: float = 0.5

    # --- Security ---
    max_request_body_bytes: int = 1_048_576  # 1 MiB default
    allow_private_base_urls: bool = False  # if false, block RFC1918 / link-local / metadata

    # --- Telemetry ---
    # Base OTLP/HTTP collector URL (port 4318) or full /v1/traces URL.
    # Empty = tracing disabled (Prometheus /metrics works regardless).
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "rerouteai"

    # --- App ---
    app_name: str = "ReRouteAI"
    debug: bool = False
    environment: Literal["development", "production"] = "development"
    # run alembic upgrade head during app startup; set false when migrations
    # are a separate release step (multi-replica deploys)
    migrate_on_startup: bool = True

    # --- CORS ---
    cors_origins: Annotated[list[str], NoDecode] = ["*"]

    # --- Hosts ---
    allowed_hosts: Annotated[list[str], NoDecode] = ["*"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _parse_hosts(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _reject_wildcard_in_production(self) -> Self:
        if self.environment != "production":
            return self
        if "*" in self.cors_origins:
            raise ValueError("CORS origins cannot contain '*' in production; set explicit origins")
        if "*" in self.allowed_hosts:
            raise ValueError("Allowed hosts cannot contain '*' in production; set explicit hosts")
        return self

    @model_validator(mode="after")
    def _reject_placeholder_secrets_in_production(self) -> Self:
        # ponytail: 32-char floor because JWT_SECRET also derives the Fernet key
        # that encrypts BYOK provider keys — a short one is offline-brute-forceable.
        if self.environment != "production":
            return self
        for name, value in (
            ("JWT_SECRET", self.jwt_secret),
            ("ADMIN_API_KEY", self.admin_api_key),
            ("FERNET_KEY", self.fernet_key),
        ):
            if value.startswith("change-me") or len(value) < 32:
                raise ValueError(
                    f"Refusing to start: {name} must be a random value of 32+ "
                    "characters in production"
                )
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
