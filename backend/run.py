"""Entry point — uvicorn reroute.app:create_app"""

import os

import uvicorn


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes"}


if __name__ == "__main__":
    uvicorn.run(
        "reroute.app:create_app",
        factory=True,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=int(os.getenv("UVICORN_WORKERS", "1")),
        # ponytail: dev-only; set UVICORN_RELOAD=1 locally, never in containers
        reload=_flag("UVICORN_RELOAD", ""),
        log_level=os.getenv("LOG_LEVEL", "info"),
        # Behind nginx/ALB/Cloudflare: honor X-Forwarded-For so the login
        # throttle and audit rows see the real client IP, not the proxy's.
        # forwarded_allow_ips defaults to loopback (same-host proxy). Set
        # FORWARDED_ALLOW_IPS only when the proxy strips client-supplied
        # X-Forwarded-For — otherwise IPs are spoofable.
        proxy_headers=_flag("UVICORN_PROXY_HEADERS", "true"),
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )
