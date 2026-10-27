# ReRouteAI

<p align="center">
  <img src="assets/logo.png" width="120" alt="ReRouteAI logo">
</p>

A self-hosted gateway between your applications and LLM providers. Accounts sign in,
connect **their own** provider keys, and call an OpenAI-compatible API. A React
dashboard shows spend, logs, and per-user analytics.

One deployment = one organization. This is not a multi-tenant SaaS: there are no
teams, tenants, billing, or per-plan quotas.

Live deployment: [app](https://re-route-nzdy.vercel.app) ·
[API reference](https://re-route-pi.vercel.app/docs) ·
[status](https://re-route-nzdy.vercel.app/status)

## Honest status

Working and covered by tests:

- Chat + SSE streaming through `/v1/chat/completions`, with fallback across a user's providers
- Per-user BYOK — each account owns its keys; no global key routes traffic
- Per-user gateway API keys (`rr_live_…`): SHA-256 hashed, shown once, revocable,
  managed only from a signed-in session
- Per-user rate limits (RPM / TPM / concurrent), semantic cache, request dedup
- Retry with backoff, per-provider circuit breaker
- Accounts: self-service sign-up (email+password, 7+ chars), GitHub OAuth, roles, refresh-token rotation, user management
- Audit log, admin-only Prometheus metrics, analytics/breakdown/activity queries
- Stream observability: TTFT (time-to-first-token), output tokens/sec,
  finish_reason, and semantic-cache $-saved, on the audit rows, admin endpoints,
  dashboard, and Prometheus
- OpenTelemetry tracing: request spans + per-provider `llm.chat` spans over
  OTLP/HTTP (opt-in, see [Telemetry](#telemetry))
- Public status feed (`/status`, 10s cache) with API/Postgres/Redis checks plus
  provider health, circuit state and latency — no keys, URLs or user data
- React app: landing, model registry and docs (`/`, `/models`, `/docs`), public
  status page (`/status`), dashboard (analytics with KPI strip and TTFT/tok-per-sec
  chart, logs with a request drawer + copy-as-cURL + CSV export, models, settings,
  users), live price-compare modal, rate-limit toasts with retry countdown,
  dismissible onboarding checklist

Not built (don't plan around it):

- Multi-tenancy, teams, billing, per-plan rate limits — rate limits are global
  config values applied to every account equally
- Frontend unit/e2e tests — the frontend gate is `tsc` + `oxlint` + build only

Known rough edges:

- Prompt guardrails are regex rules (`prompt/guardrails.py`), not an ML classifier.
  They catch the obvious cases and are documented as approximate
- The legacy `X-API-Key` header still authenticates break-glass admin paths
  (`/admin/users` CRUD and `/metrics`) only; chat requires a signed-in account or
  a per-user `rr_live_` key, so a stolen admin key cannot spend
- `/metrics` is admin-only. On Vercel each serverless instance keeps its own
  in-process metrics and resets on cold start, so treat it as a debug view, not a
  durable Prometheus target
- Environment `OPENAI_API_KEY`-style values are registered for health probes but
  are **not** routed; if a user has not connected a key, that provider is simply
  unavailable to them
- The frontend API base URL is hardcoded in `frontend/src/lib/api.ts` and
  `frontend/src/lib/auth.ts` (this deployment points at
  `https://re-route-pi.vercel.app`); edit both constants before self-hosting
- Rate-limit state for login is Redis-backed per-IP (works across workers); it
  degrades to in-process memory if Redis is briefly unreachable. Chat RPM/TPM
  counters are per-process, so `UVICORN_WORKERS=1` is still the safe default

## Architecture

```mermaid
flowchart LR
    Client["Client App<br/>(OpenAI SDK)"] -->|Bearer JWT or rr_live_ key| Auth

    subgraph GW["ReRouteAI gateway (FastAPI)"]
        direction LR
        Auth["Auth"] --> Dedup["Dedup"]
        Dedup --> RL["Rate limit<br/>RPM · TPM · concurrent"]
        RL --> Guard["Input<br/>guardrails"]
        Guard --> Cache{"Semantic<br/>cache"}
        Cache -->|"hit (0 tokens)"| Return["Return"]
        Cache -->|miss| Router["Route<br/>breaker · retry · fallback"]
        Router --> Prov["Provider call"]
        Prov --> OutGuard["Output<br/>guardrails"]
        OutGuard --> Audit["Audit + metrics"]
        Audit --> Store["Cache store"]
        Store --> Return
    end

    subgraph PROVS["Providers — BYOK per user (ollama keyless)"]
        direction TB
        P1["OpenAI"] --- P2["Anthropic"] --- P3["Gemini"] --- P4["Groq"]
        P5["Mercury"] --- P6["Cerebras"] --- P7["Together"] --- P8["Ollama"]
    end

    Prov --> PROVS

    GW <--> PG[("Postgres<br/>users · audit_logs<br/>provider_keys · api_keys")]
    GW <--> RD[("Redis<br/>rate limits · cache<br/>dedup · throttle")]
    GW --> PROM["Prometheus → Grafana<br/>15 forge_* metrics<br/>(admin-only /metrics)"]
    GW --> STAT["Public /status<br/>aggregate health · 10s cache"]

    NOTE["SSE stream path: rate limit → guard → provider only<br/>(no dedup, no cache)"]
    NOTE -.-> GW
```

Request pipeline (non-stream): **dedup → rate limit → input guardrails →
semantic cache → route (circuit breaker + retry + fallback) → provider →
output guardrails → audit → metrics → cache store**. Streams run rate limit →
guard → provider and skip dedup + cache (an answer is never replayed). The public
`/status` feed is a separate read path — it reports aggregate checks only.

## Quick Start

Prerequisites: Docker + Compose, Python 3.12+ for the backend, Node 22+ for the frontend.

### Docker Compose (backend stack)

```bash
git clone https://github.com/AKXLR8/ReRoute.git
cd ReRoute
cp backend/.env.example backend/.env
# Edit .env — at minimum JWT_SECRET and ADMIN_API_KEY

docker compose up
```

Services (note: the frontend is **not** in compose — run it separately):

| Service    | URL                          |
|------------|------------------------------|
| Gateway    | http://localhost:8000        |
| API docs   | http://localhost:8000/docs   |
| Prometheus | http://localhost:9090        |
| Grafana    | http://localhost:3001 (admin/admin) |
| Postgres   | 127.0.0.1:5432               |
| Redis      | 127.0.0.1:6379               |

The compose command runs `alembic upgrade head` on boot, so migrations are applied
automatically. Prometheus loads `backend/.env` and sends `ADMIN_API_KEY` as
`X-API-Key` when scraping `/metrics` (the endpoint is admin-only).

### Local development

```bash
# Infra
docker compose up postgres redis -d

# Backend
cd backend
pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python run.py                      # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173, proxies /v1 /auth /admin to :8000
```

### First run

Open the dashboard and click **Create one** — the first account created becomes the
admin. No setup key needed. (The gated `POST /auth/setup` endpoint still exists for
scripted installs.)

## Accounts and roles

| Role   | Can do |
|--------|--------|
| admin  | Everything below **plus** user management (create/edit/delete accounts) and org-wide analytics |
| member | Chat, connect own keys, create/revoke own gateway API keys, change own password, view **own** logs and analytics only |

Chat and models require either a signed-in account or a per-user gateway API key.
There is no key-less request path.

## Per-user BYOK

Keys live in `provider_keys`, encrypted at rest (Fernet) and never returned in
plaintext — the API only reports a mask. Each request resolves the caller's own
keys, so users cannot see or spend each other's.

```
PUT    /auth/providers/openai      {"api_key": "sk-...", "base_url": "..."}
GET    /auth/providers             # masked
DELETE /auth/providers/openai
```

Connecting validates the key against the provider before storing it. `ollama` is
keyless and always available. Settings page → Providers manages this in the UI.

## Gateway API keys

For API clients (SDKs, CI, scripts) create a per-user gateway key. It is shown
once, stored only as a SHA-256 hash, and used as a bearer token:

```
POST   /auth/api-keys          {"name": "ci"}   # returns the raw rr_live_... once
GET    /auth/api-keys                            # prefix, created/last-used/revoked
DELETE /auth/api-keys/{key_id}                   # immediate revocation
```

```bash
curl http://localhost:8000/v1/models -H "Authorization: Bearer rr_live_..."
```

Key management is session-only — a gateway key cannot create or revoke other
keys. Revoking a key kills it on the next request; no cache flush needed.

## API

Base URL `http://localhost:8000`. Authenticate with `Authorization: Bearer
<access token>` from `/auth/login`, or with a gateway key `rr_live_…` for API
clients.

```bash
# Create an account (first account becomes admin)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "your-password"}'

# Sign in
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "..."}'

# Chat (OpenAI-compatible wire format)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}], "stream": false}'

# Models you can actually use (your keys + ollama)
curl http://localhost:8000/v1/models -H "Authorization: Bearer $TOKEN"
```

Endpoint map:

| Endpoint | Auth | Scope |
|----------|------|-------|
| `GET /health`, `GET /readyz` | none | liveness / readiness |
| `GET /status` | none | public aggregate status (API, Postgres, Redis, provider health); 10s cache |
| `GET /metrics` | admin | Prometheus text format; admin JWT or `X-API-Key` |
| `GET /docs`, `GET /openapi.json` | none | API reference; `/redoc` is development-only |
| `GET/POST /auth/setup` | `ADMIN_API_KEY` | one-shot scripted setup, zero users only |
| `POST /auth/register` | — | self-service sign-up; first account = admin; rate-limited per IP |
| `GET /auth/github/authorize`, `GET /auth/github/callback`, `POST /auth/github/exchange` | — | GitHub OAuth (needs `GITHUB_CLIENT_ID`/`SECRET`) |
| `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me` | — / token | account |
| `POST /auth/change-password` | token | self |
| `GET/POST /auth/api-keys`, `DELETE /auth/api-keys/{key_id}` | session | own gateway keys; raw key shown once |
| `GET/PUT/DELETE /auth/providers[/{provider}]` | token | own keys |
| `GET /v1/models`, `POST /v1/chat/completions` | token or gateway key | own keys |
| `GET /admin/logs`, `/admin/analytics`, `/admin/activity`, `/admin/breakdown`, `/admin/health` | token | member = own rows, admin = all |
| `GET/POST /admin/users`, `PATCH/DELETE /admin/users/{id}`, `POST /admin/users/{id}/password` | admin | — |

`/docs` and `/openapi.json` stay enabled in production (the dashboard's API
reference links to them); they expose the route surface, not data. `/redoc` is
development-only.

## Configuration

All via environment variables or `backend/.env` (see `backend/.env.example`).
`ENVIRONMENT=production` refuses to boot on placeholder secrets, wildcard CORS, or
wildcard allowed hosts.

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://forge:forge@localhost:5432/reroute` | |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | `20` / `10` | asyncpg pool sizing |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `JWT_SECRET` | `change-me-in-production` | signs account tokens; 32+ chars required in prod |
| `FERNET_KEY` | — | BYOK key encryption. Falls back to `JWT_SECRET` if unset (legacy) |
| `ADMIN_API_KEY` | `change-me-admin-key` | setup, legacy `X-API-Key`, and admin `/metrics` scraping |
| `ADMIN_API_KEY_HASH` | — | bcrypt hash; if set, takes precedence over the plaintext key |
| `ACCESS_EXPIRE_MINUTES` | `15` | access JWT lifetime |
| `REFRESH_EXPIRE_DAYS` | `14` | rotating refresh token lifetime |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES` | `5` / `15` | per-account lockout |
| `LOGIN_RATE_LIMIT_PER_IP` | `10` | per minute, per IP, on login/setup |
| `ALLOW_REGISTRATION` | `true` | self-service `POST /auth/register` |
| `REGISTER_RATE_LIMIT_PER_HOUR` | `5` | per IP, on register |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | — | empty = GitHub sign-in returns 501 |
| `GITHUB_REDIRECT_URI` | `http://localhost:8000/auth/github/callback` | must match the OAuth App settings on GitHub |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | where the OAuth callback hands the session back |
| `OPENAI_API_KEY` etc. | — | health probes only; **not routed** |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | keyless, available to every account |
| `DEFAULT_RATE_LIMIT_RPM` / `_TPM` / `_CONCURRENT` | `60` / `100000` / `10` | applied per user, not per plan |
| `SEMANTIC_CACHE_THRESHOLD` / `_TTL_SECONDS` | `0.92` / `3600` | cache is scoped per user |
| `EMBEDDING_MODEL` | `Xenova/all-MiniLM-L6-v2` | ONNX model behind semantic-cache matching |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` / `_RECOVERY_SECONDS` | `5` / `30` | |
| `RETRY_MAX_ATTEMPTS` / `RETRY_BASE_DELAY` | `3` / `0.5` | |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | 413 above this |
| `ALLOW_PRIVATE_BASE_URLS` | `false` | blocks RFC1918/link-local/metadata in `base_url` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP/HTTP collector URL (port 4318). Empty = tracing off |
| `OTEL_SERVICE_NAME` | `rerouteai` | `service.name` on exported spans |
| `CORS_ORIGINS` / `ALLOWED_HOSTS` | `*` | `*` rejected in production |
| `ENVIRONMENT` | `development` | `production` enables the checks above |
| `MIGRATE_ON_STARTUP` | `true` | runs `alembic upgrade head` at boot; set `false` to migrate manually |
| `UVICORN_WORKERS` | `1` | login throttle is Redis-backed, so >1 is safe; rate-limit state is per-process |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | bind address for `run.py` |
| `LOG_LEVEL` | `info` | uvicorn log level |
| `UVICORN_PROXY_HEADERS` | `true` | trust `X-Forwarded-*` from a reverse proxy |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | proxy IPs to trust; set to your LB's address/IP in production so per-IP limits see real client IPs |
| `UVICORN_RELOAD` | off | dev-only auto-reload (`run.py`) |

The frontend API base URL is not an env var today: set it in
`frontend/src/lib/api.ts` and `frontend/src/lib/auth.ts` before building.

## Deployment

The backend ships as a container — no secrets are baked into the image; everything
comes from env at runtime. Migrations run automatically at boot
(`MIGRATE_ON_STARTUP=true`).

```bash
docker build -t reroute backend/
docker run -p 8000:8000 --env-file backend/.env reroute   # gateway only
# or: docker compose up   # gateway + postgres + redis + prometheus + grafana
```

Production checklist (`backend/.env`):

- `ENVIRONMENT=production` — refuses to boot on placeholder secrets, wildcard
  CORS, or wildcard allowed hosts
- `JWT_SECRET`, `ADMIN_API_KEY` — random 32+ chars each
- `FERNET_KEY` — set **before any user connects a key**; it encrypts BYOK keys
  at rest, and rotating it later makes already-stored keys unreadable
- `CORS_ORIGINS` / `ALLOWED_HOSTS` — your real origins/hosts (no `*`)
- `GITHUB_REDIRECT_URI` / `FRONTEND_BASE_URL` — must match your public domain
  if you use GitHub sign-in
- `FORWARDED_ALLOW_IPS` — your reverse proxy's IP so login rate limits see real
  client IPs instead of the proxy's
- Put TLS in front (Caddy/nginx); the app itself serves plain HTTP

The frontend is a static bundle, not part of compose — build it, then serve
`frontend/dist/` anywhere. Point it at your API first by editing `API_URL` in
`frontend/src/lib/api.ts` **and** `frontend/src/lib/auth.ts`:

```bash
cd frontend
npm run build        # tsc -b && vite build
# serve dist/ (Vercel/Netlify/nginx); SPA fallback to index.html
```

### Vercel

Git-based deploy as two projects: backend (Root Directory `backend/` — loads
`main.py`, installs from `uv.lock`, build hook prefetches the embedding model
into `.hf/`) and frontend (Root Directory `frontend/`).

Backend env requirements beyond the checklist above:

- No Large Functions flag needed — onnxruntime instead of torch keeps the
  Python bundle ~460 MB, under the 500 MB default cap (quantized model baked
  in); revisit `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` if dependencies grow
- `MIGRATE_ON_STARTUP=false` — run alembic from a release step instead
  (already-applied migrations don't re-run; concurrent instances would race)
- `ENVIRONMENT=production`, plus real `CORS_ORIGINS` / `ALLOWED_HOSTS`
  after the frontend project's URL is known

## Security

- **Sessions** — 15-minute access JWT + 14-day rotating refresh token. Logout
  revokes the refresh token; password changes/resets and account suspension bump
  `token_version` and revoke all refresh tokens, so access tokens die on the next
  request. Deleted users fail the live lookup. Login failures return one generic
  401, with per-account lockout (5 tries / 15 min) and a Redis-backed per-IP
  throttle.
- **Gateway keys** — raw `rr_live_…` value is shown once and stored as SHA-256;
  the list exposes only prefix/timestamps; revocation is immediate. Key
  management is session-only, so a leaked key cannot mint more keys.
- **BYOK** — provider keys are Fernet-encrypted at rest, masked in responses,
  and resolved per user. Provider `base_url` rejects private, link-local and
  cloud-metadata addresses unless `ALLOW_PRIVATE_BASE_URLS=true`.
- **Isolation** — read/admin routes filter to the caller unless the role is
  admin. `/metrics` is admin-only (its labels include user UUIDs and spend).
- **Public by design** — `/health`, `/readyz`, `/status` (aggregate, 10s cache),
  `/docs`, `/openapi.json`. None return user rows, keys, prompts or completions.
- **Production checks** — `ENVIRONMENT=production` refuses placeholder secrets,
  wildcard CORS and wildcard hosts; trust only your proxy via
  `FORWARDED_ALLOW_IPS`; request bodies cap at 1 MiB. The deployment adds HSTS
  and `frame-ancestors`, the SPA ships a CSP, and builds contain no source maps
  or secrets.
- **Known limitations** — session tokens live in `localStorage`, so an XSS would
  steal them (CSP + React escaping are the mitigations; httpOnly cookies with
  CSRF protection are future work). Registration is open unless
  `ALLOW_REGISTRATION=false`, and chat rate-limit counters are per worker.
  There is no formal vulnerability-disclosure process yet.

## Telemetry

Two independent layers:

**Metrics (on, admin-only).** Prometheus counters/histograms/gauges for requests,
tokens, cost, retries, fallbacks, cache hits + $-savings, circuit-breaker state
and provider health — 15 `forge_*` families at `GET /metrics`. The endpoint
requires an admin session token or the admin `X-API-Key`: it used to be public,
but the `team_id` labels contain user UUIDs and per-user spend. Token counts are
provider-reported (including streams); cost is estimated from the
per-model list prices in `providers/*_provider.py`. Streamed requests also
record TTFT (`forge_ttft_seconds`), output tokens/sec
(`forge_output_tokens_per_second`), and finish_reason
(`forge_finish_reasons_total`) — useful for spotting truncation
(`finish_reason=length`) and slow providers.

```bash
curl https://api.yourdomain/metrics -H "X-API-Key: $ADMIN_API_KEY"
```

Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: reroute
    scheme: https
    static_configs: [{ targets: ["api.yourdomain"] }]
    headers:
      X-API-Key:
        values: ["<ADMIN_API_KEY>"]
```

Metrics live in process memory. A long-running container is a fine scrape
target; on Vercel's per-request/serverless model each instance has its own
counters and cold starts reset them, so treat `/metrics` there as a debug view.
For a public status signal use `/status` (aggregate only, no user data).

**Tracing (opt-in).** Point `OTEL_EXPORTER_OTLP_ENDPOINT` at an OTLP/HTTP
collector (e.g. Grafana Alloy, otel-collector, Jaeger — port `4318`) and the
gateway exports:

- one server span per HTTP request (FastAPI instrumentation)
- one `llm.chat` span per provider call, nested under it, with
  `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`,
  `gen_ai.response.model`, `gen_ai.usage.input_tokens` /
  `gen_ai.usage.output_tokens` (when the provider reports usage),
  `gen_ai.server.time_to_first_token` /
  `gen_ai.response.finish_reasons` (streams), and
  `reroute.stream` / `reroute.fallback_from` when relevant

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318   # or .../v1/traces
OTEL_SERVICE_NAME=rerouteai
```

Both a collector base URL and a full `/v1/traces` URL are accepted. Unset =
no tracing code runs and spans are dropped (metrics still work). Span
attributes carry no user ids, prompts, or completions.

```bash
docker run -p 4318:4318 jaegertracing/opentelemetry-collector:latest  # quick local collector
```

## Project structure

```
backend/
├── reroute/
│   ├── api/            # route handlers: chat, auth, admin reads, users
│   ├── auth/           # passwords (stdlib PBKDF2), JWT, account/refresh logic
│   ├── cache/          # semantic cache (sentence-transformers) + request dedup
│   ├── circuit_breaker/
│   ├── gateway/        # request handler: rate limit → guard → cache → route → audit
│   ├── models/         # SQLAlchemy: User, AuditLog, ProviderKey, ApiKey, RefreshToken
│   ├── observability/  # Prometheus metrics + OpenTelemetry setup
│   ├── prompt/         # regex guardrails (input injection/secret/PII, output secret)
│   ├── providers/      # one file per provider + per-user BYOK resolution
│   ├── rate_limit/     # Redis RPM / TPM / concurrent limiter
│   ├── retry/          # exponential backoff with jitter
│   ├── router/         # health + model-support based selection (emits llm.chat spans)
│   └── schemas/        # Pydantic request/response models
├── alembic/versions/   # 001 → 009
└── tests/              # 227 tests (unit + integration + load)
frontend/
├── scripts/            # node --experimental-strip-types checks (CSV, timeago)
└── src/
    ├── pages/          # Landing, AnalyticsDashboard, Logs, Models, Settings, Users, Docs, Status
    ├── components/     # TopNav, dashboard charts, RequestDrawer, landing, motion primitives
    └── lib/            # api client, auth, toast, pricing, csv, nav
docker/                 # Prometheus + alert rules
docker-compose.yml      # postgres, redis, gateway, prometheus, grafana
```

## Tests and gates

```bash
# Backend — 227 tests, must be green
cd backend
python -m pytest tests/ -q
ruff check reroute tests run.py

# Frontend — type check + lint + build
cd frontend
npx tsc -b
npm run lint
npm run build          # tsc -b && vite build
node --experimental-strip-types scripts/check-csv.mjs
node --experimental-strip-types scripts/check-timeago.mjs
```

Load tests live in `backend/tests/load/locustfile.py` (`locust -f ...`).

## Future scope

Candidate work, not commitments or dates. Ordered roughly by leverage:

**Accounts and access**

- Organizations/teams with per-team isolation, roles and budgets (the current
  model is one org per deployment)
- Per-plan quotas and billing; prepaid credits and spend caps per key/user
- SSO/OIDC and SAML, SCIM provisioning, MFA, session listing/revocation
- httpOnly cookie sessions with CSRF protection to move tokens out of
  `localStorage`; security.txt and a public disclosure process

**Gateway**

- More providers (Azure OpenAI, AWS Bedrock, Mistral, xAI, vLLM) and
  OpenAI-compatible passthroughs
- Cost/latency-aware routing (not just model support), per-request budgets,
  hard spend kill-switch, richer fallback policies
- Distributed RPM/TPM counters in Redis so multi-worker/concurrent limits are
  exact; per-IP edge limiting
- Streaming improvements: resumable streams, partial-response caching, cache
  invalidation controls

**Observability and operations**

- Durable metrics: ship to an external TSDB instead of per-instance memory, plus
  alerting/webhooks on error rate, spend and breaker trips
- Admin observability UI (metrics, provider health history, spend forecasts) so
  raw `/metrics` is only for operators
- Saved log filters/views, audit-log export, request replay/eval harness
- ML guardrails and PII redaction beyond the current regex rules
- Terraform/Helm, backup/restore runbooks, staging environment, CI gates for
  migrations and security scans

**Frontend**

- Component and end-to-end tests (Vitest + Playwright), accessibility audit, and
  mobile polish for the dashboard
- Deeper model comparison, usage alerts, and per-key analytics

## Adding a provider

Create `backend/reroute/providers/my_provider.py`:

```python
from .base import Provider
from ..schemas.chat import ChatRequest, ChatResponse, StreamingChunk

class MyProvider(Provider):
    name = "my_provider"

    def models(self) -> list[str]:
        return ["my-model-1"]

    async def chat(self, request: ChatRequest) -> ChatResponse: ...
    async def stream(self, request: ChatRequest): ...
    async def health_check(self) -> bool: ...
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        return 0.0
```

Register it in `backend/reroute/app.py` (`registry.register(...)`), add a
`my_provider_api_key` field to `config.py`, and it becomes connectable per user —
users add their own key through Settings → Providers. Nothing else changes: routing,
rate limiting, audit, and analytics pick it up automatically.

## License

MIT
