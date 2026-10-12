"""Tests for config."""

import pytest
from pydantic import ValidationError

from reroute.config import Settings, get_settings


def test_settings_defaults():
    s = Settings()
    assert s.app_name == "ReRouteAI"
    assert s.jwt_algorithm == "HS256"
    assert s.retry_max_attempts == 3
    assert s.circuit_breaker_failure_threshold == 5


def test_settings_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


@pytest.mark.parametrize("secret", ["123", "change-me-in-production", "a" * 31])
def test_production_rejects_weak_secrets(secret):
    """A weak JWT_SECRET also weakens the Fernet key that encrypts BYOK keys."""
    with pytest.raises(ValidationError, match="Refusing to start"):
        Settings(
            environment="production",
            jwt_secret=secret,
            admin_api_key="b" * 40,
            fernet_key="c" * 40,
            cors_origins=["https://example.com"],
            allowed_hosts=["example.com"],
            _env_file=None,
        )


def test_production_accepts_strong_secrets():
    s = Settings(
        environment="production",
        jwt_secret="a" * 40,
        admin_api_key="b" * 40,
        fernet_key="c" * 40,
        cors_origins=["https://example.com"],
        allowed_hosts=["example.com"],
        _env_file=None,
    )
    assert s.admin_api_key == "b" * 40


def test_development_tolerates_weak_secrets():
    assert Settings(jwt_secret="123", admin_api_key="123", _env_file=None).admin_api_key == "123"
