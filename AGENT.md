# FitGate — Agent Operating Instructions

This file is read automatically at the start of every session in this repo. It is the operating contract for how work gets done here — not a description of the product. For what to build, see `docs/SPEC.md`. For what to build next, see `docs/SPRINTS.md`.

`docs/SPEC.md` is the working reference for every requirement, data model field, and use case; it is checked against `docs/source/FitGate_Documentation_Full.md` (the plain-text conversion of the project documentation), which wins if the two disagree unless the difference is listed in SPEC §11. If a request conflicts with either, say so — do not silently pick a side. If `docs/SPEC.md` itself is ambiguous or internally inconsistent on a point (see "Known conflicts" at its end), do not resolve it unilaterally; ask.

## Confirmed technical stack

Backend: Django + Django REST Framework. Django 5.2 LTS specifically (supported until April 2028; Django 5.1 is a non-LTS release that reached end-of-life Dec 31, 2025 — do not use it). Python 3.11.16 specifically, in both the local Docker image and anywhere else Python is invoked — this exact version is pinned (not just "3.11.x" or "latest 3.11") because it matches the ceiling Yegara's cPanel Python App Manager accepts in production; local dev running a newer Python than production can silently use syntax/stdlib features that break on deploy.

- Frontend: React SPA (Vite) — React Router, TanStack Query (no Redux), Workbox service worker for offline-first PWA
- Database: PostgreSQL, multi-tenant via `gym_id` row-level scoping (not schema-per-tenant — see Known Conflicts in docs/SPEC.md)
- Environment: Docker Compose (Django, Postgres, Redis, **pgAdmin**) for **local development only**. pgAdmin is a dev convenience connected to the same `postgres` container — it must never be part of the production setup. Production does not use Docker — see Deployment below. Local and production are not the same environment; parity between them (especially around scheduled/async jobs) must be deliberately maintained, not assumed.
- Testing: pytest-django
- Deployment: **Yegara Host Premium — shared/managed cPanel hosting, no root or SSH access.** This reverses an earlier assumption (unmanaged VPS + Docker + Caddy); do not design against that old assumption anywhere. Concretely:
  - Django runs via cPanel's Python App Manager (Passenger WSGI), not a container.
  - PostgreSQL is provided directly by cPanel — confirmed available.
  - TLS is handled by cPanel AutoSSL, not Caddy. AutoSSL runs on a periodic scan (not instant on creation), so a freshly created subdomain can exist over HTTP before it has a valid certificate — see the Sprint 4 acceptance criteria in `docs/SPRINTS.md` for the required safeguard (no forced HTTPS redirect and no login allowed until the cert is confirmed valid).
  - Gym subdomains are provisioned by calling cPanel's UAPI (API token access is confirmed available on this plan) at approval time — not via wildcard DNS, which isn't available without root.
  - No persistent background worker process (Celery's model) is assumed viable on shared hosting. Scheduled jobs (e.g., nightly expiry sweep) use cPanel Cron Jobs calling a Django management command. Jobs that need to run outside the request/response cycle (e.g., AI plan generation, if it risks the WSGI request timeout) use a DB-backed job table polled by a cron-triggered management command, not a live task queue.
  - Redis's availability in production (as opposed to local dev, where it's confirmed via Docker Compose) is **unconfirmed** — check whether cPanel offers it as an add-on before assuming production can use it for caching or anything else.
- Payments: Chapa, **one merchant account per gym**. Each gym's Chapa secret key and webhook secret are stored encrypted (see rule 14's exception) and never returned by any API. Gyms pay the platform by bank transfer recorded by Super Admin — the platform has no Chapa account of its own.
- File storage: Cloudinary (Free plan) behind Django's storage interface. Member photos are private (`authenticated`) assets served only through the backend after a permission check; gym logos are public. Local development and tests use a local folder through the same interface.
- Onboarding: gyms are created by Super Admin after payment (assisted onboarding); there is no public gym self-registration in this version.
- Domain: not finalized (candidates: fitgate.org, a tebebtech.com subdomain for interim/demo) — always a `DOMAIN` env var, never hardcoded anywhere
- Team: solo-committer. Full feature-branch/PR discipline is still enforced as a practice, but review and merge of a PR is done by the same person who authored it
- AI Personal Training Engine integration layer: **LiteLLM**, self-hosted inside the Django backend (not a hosted gateway service — it's an open-source Python library you call directly, so it carries no markup fee). It sits behind the swappable-provider interface the spec already calls for, so the actual underlying model(s) it routes to can change via config, not code.

Items below are proposed but not yet confirmed by the project owner — do not treat as settled, flag if a sprint depends on one:

- Which underlying model(s) LiteLLM routes to — plan is to evaluate candidates via OpenRouter's free tier first (cheap to compare output quality across model families, especially for Ethiopian-context nutrition content), then configure LiteLLM to call the winner directly once chosen. Not yet run.
- File/image storage backend (local Docker volume vs S3-compatible object storage) for profile photos and gym branding assets — resolve with the added constraint that shared hosting may not support S3-compatible self-hosted storage (e.g., MinIO) the way a Docker-based VPS would have.
- Whether Redis (and therefore any caching built around it) is available at all in production — see Deployment above.

## Workflow rules

1. Work in sprints, one sprint per session, matching the scope defined in `docs/SPRINTS.md`. Do not blend two sprints into one session.
2. Never rewrite existing code unless there is no reasonable way to avoid it. Prefer the smallest diff that correctly implements the sprint's scope.
3. When modifying an existing file, show and apply only the exact lines that must change.
4. Maintain clean architecture from the start — no shortcuts that create technical debt without flagging them explicitly to the project owner first.
5. Every sprint that adds real logic (not pure scaffolding) includes automated tests for that logic, in the same PR. Not deferred.
6. Explain what the code does and why in prose (PR description / chat response), not as inline comments explaining basics — the project owner is learning the codebase, not just accepting output.
7. Recap the previous sprint's outcome briefly before starting a new one.
8. Keep backend and frontend contracts mechanically aligned: regenerate the OpenAPI schema (drf-spectacular) and the generated TypeScript types whenever a serializer or endpoint changes. Do not let the frontend hand-maintain types that duplicate the backend contract.
9. One feature branch per sprint, branched from `develop`, named `feature/sprint-N-short-name`.
10. Never commit directly to `main`. `main` = production only. `develop` = integration branch.
11. Open a PR with a written description (what changed, why, what was tested) at the end of every sprint. The project owner reviews and merges their own PRs — do not merge automatically, and do not treat "tests pass" as equivalent to "reviewed and approved."
12. If less than 90% sure how a requirement should be implemented, stop and ask rather than guessing.
13. If a better or more optimal approach exists than what was asked for, say so and recommend it — don't silently comply with a suboptimal request.
14. Secrets and environment-specific values (Chapa keys, JWT signing secret, `DOMAIN`, AI provider key, DB credentials) are environment variables only, sourced from `.env` (gitignored). Never hardcoded, never committed, never placed in a default in code. **One exception:** credentials a gym itself supplies (its own Chapa keys) are tenant data, not platform secrets — they are stored encrypted in the database (never plaintext, never returned by an API, never logged) using an encryption key that itself comes from the environment (`TENANT_CREDENTIALS_KEY`).
15. When a task needs something the agent cannot do itself — creating an external account, obtaining an API key or credential, configuring DNS, installing software on the host machine or configuring the shared cPanel host, anything requiring a browser or a service's own dashboard — stop and give the project owner explicit, numbered, step-by-step instructions for that manual action, including exactly what to do with the result (e.g., "paste the key into `.env` as `CHAPA_SECRET_KEY`"). Do not guess, stub around it silently, or describe the need vaguely and move on.

## Before writing any code in a sprint

- Read the relevant section(s) of `docs/SPEC.md` for the feature in scope.
- Read the current sprint's entry in `docs/SPRINTS.md`, including its stated dependencies on earlier sprints.
- Run the existing test suite to confirm a clean baseline before making changes.

## Definition of done, per sprint

- [ ] Migrations included, and apply cleanly against a fresh database
- [ ] Tests written and passing for all new logic
- [ ] Lint/format clean (ruff + black on the backend, eslint + prettier on the frontend)
- [ ] OpenAPI schema and generated TS types regenerated if any endpoint or serializer changed
- [ ] PR description written, covering what changed, why, and what was tested
- [ ] No secrets, and no hardcoded domain or environment-specific values, introduced
- [ ] `docs/SPRINTS.md` updated to mark the sprint complete

## Before reporting a sprint as ready

Keep the report short. Do not paste whole files or re-paste old output.

1. Criteria table: each criterion in the sprint entry -> test name(s) from the collected
   tests -> pass/fail. A criterion with no test gets one.
2. The pytest summary line for the FULL suite, and one-line results for ruff, black and
   `makemigrations --check` (plus eslint/prettier if the frontend changed).
3. The diff (not whole files) of any risky file you touched: authentication, permissions,
   tenancy/managers, payments, secrets/settings. Add the code of any test that proves a
   security property.
4. Settings audit, one line: any `default=` on env reads, "*" in ALLOWED_HOSTS or CORS,
   hardcoded hosts/domains/keys. "None" or explain.
5. File list, one line per file. No duplicate files, nothing outside the sprint's scope.
6. Deviations and uncertainties, stated explicitly even if "none".
7. Never mark the sprint complete; the owner does that after merging.
   When the owner says a sprint is "strict" (security, money, tenancy), also include, for
   each new write/access path, every other path that reaches the same data (bulk operations,
   generators, admin, serializers, management commands, all_objects) and whether it is
   covered, plus the full code of the risky files.

## Common commands

```bash
# Start all local development services (Django, Postgres, Redis, pgAdmin, React)
docker compose up -d

# Stop local development services
docker compose down

# Run backend tests
docker compose exec backend pytest

# Apply database migrations
docker compose exec backend python manage.py migrate

# Generate OpenAPI schema and mechanical TypeScript contract
docker compose exec backend python manage.py spectacular --file schema.yaml
npm --prefix frontend run generate:types

# Frontend lint and format checks
npm --prefix frontend run lint
npm --prefix frontend run format:check

# Backend lint and format checks
.venv\Scripts\ruff.exe check backend
.venv\Scripts\black.exe --check backend

# Pre-commit hook manual trigger
.venv\Scripts\pre-commit.exe run --all-files
```
