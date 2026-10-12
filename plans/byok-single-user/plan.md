# Switch to BYOK-only (remove key creation + teams) & remove Life tracking

Decisions (user-confirmed): **admin key + global BYOK**, **remove teams/budgets entirely**, **remove life tracking entirely**.

## End state
- Auth: single admin key from `.env` (plus existing JWT branch). No minted `fgw_` keys — the `api_keys` model/endpoints/UI all go.
- BYOK: connected provider keys are **global** — used for every request; `.env` provider keys are fallback. Settings page = connect/disconnect providers.
- Teams, budgets, per-team rate limits, team policies, team enrichment: gone.
- Rate limiting stays **global** (rpm/tpm/concurrent from `config.py` defaults: 60 / 100k / 10, scopes `global:*`), enforced on every request — this keeps a real feature for the "Rate Limits" landing panel.
- Tracking stays global: `/admin/analytics`, `/admin/activity`, `/admin/breakdown` (by_provider + by_model), `/admin/logs`.

## Backend

### Migration `004_single_user.py`
- drop `life_entries`, `budget_usage`, `api_keys`
- `team_provider_keys` → new `provider_keys` (drop `team_id`, unique on `provider`), `INSERT … SELECT DISTINCT ON (provider)` to carry over the 1 live mercury row
- drop `teams`
- `audit_logs`: drop columns `team_id`, `api_key_id` + index `ix_audit_logs_team_id` (**rows preserved**)
- keep migration `003` in history (it's applied to live DB; deleting breaks revision lookup) — 004 drops the table it created
- run `alembic upgrade head` on dev DB; sanity-check: audit rows still 23, provider_keys 1, other tables gone

### Delete
- modules: `api/life.py`, `budgets/`, `policies/`, `api/teams.py` (except `/v1/models`, moved into `api/chat.py`), `schemas/api_key.py`, `configs/policies.yaml`
- models: `team.py`, `api_key.py`, `budget_usage.py`, `life_entry.py`

### Rewrite
- `auth/auth.py`: `AuthContext` → `{is_admin}`; `get_current_user` = admin key or JWT only (drop APIKey lookup, `hash_key`)
- `providers/base.py`: registry stores global overrides `provider → (plain_key, base_url, fingerprint)`; `_override_provider` replaces `_team_provider` (cache keyed by provider name); `for_model(model)` loses team param; `has_override(name)` for models-list/health
- `providers/byok.py`: `connect(db, provider, …)` / `disconnect(db, provider)` upsert by provider (no team); rest (encrypt/mask/SSRF/clone) unchanged
- `models/provider_key.py`: `TeamProviderKey` → `ProviderKey` (table `provider_keys`, unique `provider`)
- `models/audit_log.py`: drop the two columns
- `gateway/handler.py`: drop `auth` param, budget, policy, enricher; global rate limits computed once in `__init__` from `get_settings()` (delete `rate_limits()` helper); dedup/cache scope `"global"`; metrics `team_id="global"`; audit rows without team cols
- `api/chat.py`: auth `Depends` stays (gating) but no longer passed to handler; drop `BudgetExceeded`/`PolicyDenied` handlers (keep RateLimit→429, ValueError→503); gains `GET /v1/models` (global: `api_key or has_override or ollama`)
- `router/router.py`: drop team + policy branches (`route(request)` / `route_stream(request)`)
- `api/admin.py`: drop teams/keys/budgets CRUD; add global `GET /admin/providers`, `PUT /admin/providers/{p}`, `DELETE /admin/providers/{p}` (updates registry override on write); `/admin/logs` loses `team_id` filter; `/admin/breakdown` → `by_provider` + `by_model`
- `schemas/team.py` → `schemas/provider.py` (`ProviderConnect`, `ProviderRead`); update `schemas/__init__`
- `app.py`: no budget/policy/life wiring; lifespan loads `ProviderKey` rows → registry overrides (decrypt, log-and-continue on failure); health loop checks override providers too
- `config.py`: drop `default_monthly_budget_usd` / `default_daily_budget_usd`; rate-limit fields get a "global" comment

### Tests
- delete: `test_life.py`, `test_policies.py`, `test_budgets.py`, `test_enrichment.py`, `test_admin_keys.py`
- update: `test_auth.py` (admin/JWT only), `test_byok.py` (global), `test_router.py`/`test_router_pref.py` (no team), `test_security_fixes.py` (fixture slimmed, key-scoped-rate-limit test removed), `test_admin_breakdown.py` (by_provider/by_model), `test_handler_guards.py` (budget tests gone), `test_failure_audit.py`, `test_handler_dedup.py` (auth args), `test_models.py` (drop Team/APIKey defaults), `test_config.py`/`test_schemas.py` if they touch removed settings/schemas; fix whatever the run surfaces (`test_provider_mapping`, `test_gateway`, metrics, etc.)
- handler tests already mock the rate limiter → global enforcement won't flake the suite

## Frontend
- delete `pages/Life.tsx`; remove route/import in `App.tsx` (fix "create your first API key" modal copy), Life tab in `Header.tsx`, Life + fake workspace switcher in `Sidebar.tsx`, label `API Keys` → `Settings`
- `lib/api.ts`: drop `Team`, `APIKeyCreated`, life types/fns, budgets fns, `team_id` on `AuditLog`; `listLogs` loses team param; team-provider fns → global `listProviders`/`connectProvider`/`disconnectProvider` (`/admin/providers…`); `verifyAdminKey` → `GET /admin/health` (drop 403 branch); `Breakdown` → `{by_provider, by_model}`
- `Settings.tsx`: rewrite → one global **Providers** panel (reuse current connect UI minus teamId) + General card; header title "Settings" / "Provider keys, masked & encrypted"
- `AnalyticsDashboard.tsx`: "Top API Keys" card → "Top Providers" (`by_provider`); `listLogs(15)`
- `TopNav.tsx`: "Get API Key" → "Open Dashboard" (×2); menu item `Teams / RBAC & budgets` → `Providers / BYOK spend tracking`
- `Landing.tsx`: panels `API Key Tracking` → `Usage Analytics` (per-model cost rows visual), `Team Budgets` → `Rate Limits` (rpm/tpm/concurrent bars at 60/100k/10); features intro "Keys, budgets…" → "Usage, rate limits…"; hero subtitle + FAQ "One API key" phrasing; WhySection "tied to the API key" → request-log phrasing
- `README.md`: feature bullets + curl examples drop teams/keys/budgets/life; add global providers BYOK example

## Verification
1. backend: `ruff check forgegateway tests`, `mypy forgegateway` (no new errors vs 81 baseline; report new baseline), `pytest` (report count — will drop from 171 with deleted tests)
2. `alembic upgrade head` + psql sanity check (tables/rows above)
3. frontend: `npm run build`, `npm run lint`
4. no manual smoke — you said you'll test yourself

## Skipped / notes
- JWT admin-token branch left in place (unused by UI but covered by tests)
- semantic cache & dedup keep their `scope` params, just called with `"global"` — no API churn
- destructive on dev DB: 9 teams, 7 keys, budget + life rows are dropped by 004 (intended); audit history survives minus the two columns
- existing 7 `fgw_` keys stop working — sign in with the admin key (`123`)
