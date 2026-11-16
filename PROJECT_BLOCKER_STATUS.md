# FieldOps Nexus — Project Health & Blocker Status Report

- **Repository:** `c:\f\FieldOps_Nexus_Internal`
- **Branch / HEAD:** `fix/api` @ `25bf1f8` (`Merge pull request #170 from VPDTechnologies/fix/sla`)
- **Verified Date:** `2026-11-12`

---

## Executive Summary

- **Infrastructure, Database, Migrations & Core Backend:** **Healthy (0 blockers locally)**
- **Active Project Blockers:** **3** (CSP inline JS handlers in 7 templates, stale Docker `staticfiles`, and 37 unpushed commits ahead of `origin/fix/api`)
- **Functional QA Regression Fixes (`FUNCTIONAL_TEST_VERIFICATION_REPORT.md`):** `3,502 / 3,644` completed in local code (`0` pending code bug fixes for the Round-2 Excel suite; awaiting remote push/deploy)

---

## 1. Active Blockers (3 Open Items)

### Blocker 1 — Content Security Policy (CSP) Blocks Inline Event Handlers Across 7 Templates
`src/apps/core/csp.py` enforces `script-src 'self' 'nonce-{nonce}'` (forbidding inline `onclick=`, `onchange=`, `onsubmit=` HTML attributes and requiring handlers to live in `src/static/js/app.js`). The following 15 inline attributes in 7 templates are currently blocked by browsers:

1. **Audit Evidence ZIP Download (`BUG-023`):**
   - `src/templates/audit/list.html#L400`: `<form id="evidence-form" onsubmit="...">` is blocked by CSP, causing **Download ZIP Archive** to fall back to a blank `GET` reload to `/app/audit/?` instead of navigating to `/app/audit/evidence/work-order/<id>/`.
   - Note: `#L392` placeholder shows `WO-0001` (4 digits), while seeded work orders use 6 digits (`WO-000001`, `WO-000002`). The backend endpoint `/app/audit/evidence/work-order/<id>/` works directly when visited by URL.
2. **Header Organization Switcher:**
   - `src/templates/shell.html#L46`: `<select name="organization" ... onchange="this.form.submit()">` is blocked, preventing multi-organization users from switching organizations via the dropdown.
3. **Roles & Permissions Matrix Controls:**
   - `src/templates/rbac/roles.html#L49`: Role filter dropdown `onchange="this.form.submit()"` does not auto-submit.
   - `src/templates/rbac/roles.html#L182`: `onchange="applyRolePreset('{{ m.pk }}', this)"` does not apply role presets.
   - `src/templates/rbac/roles.html#L203-L204`: `onclick="toggleAllPerms('{{ m.pk }}', true/false)"` (**Select All** / **Clear All**) does nothing.
4. **Platform Admin Organization Management Actions:**
   - `src/templates/tenancy/platform_organizations.html#L123`: `onsubmit="var r = prompt(...)"` on **Deactivate** is blocked, skipping the reason prompt before submission.
   - `src/templates/tenancy/platform_organizations.html#L107, L114, L132`: `onsubmit="return confirm(...)"` on **Cancel Deletion**, **Delete Now**, and **Activate** is blocked, causing those actions to submit without a confirmation dialog.
5. **Inventory Sort Dropdowns:**
   - `src/templates/inventory/movements.html#L17`: `onchange="this.form.submit()"` does not auto-submit on change.
   - `src/templates/inventory/reservations.html#L76`: `onchange="this.form.submit()"` does not auto-submit on change.
6. **Skipped Browser Confirmation Prompts:**
   - `src/templates/incidents/detail.html#L425`: `onsubmit="return confirm('Delete this comment?')"`
   - `src/templates/portal/request_detail.html#L212`: `onclick="return confirm(...)"` (Confirm Completion)
   - `src/templates/portal/request_detail.html#L237`: `onclick="return confirm(...)"` (Submit Reopen Request)

**Required Fix:** Replace these inline `on*` attributes with `data-*` attributes handled via delegated event listeners in `src/static/js/app.js` (and increment the static asset version query parameter in `src/templates/base.html`).

---

### Blocker 2 — Docker `/app/staticfiles/` Is Out of Sync with `./src/static/`
- `docker-compose.yml` mounts `./src:/app/src` into the `web` container so Python and template changes apply immediately, **but** `Dockerfile` runs `python manage.py collectstatic --noinput` only during image build (`RUN` layer), and `config.settings.prod` serves static assets from `/app/staticfiles/`.
- Verified inside the running `web` container:
  - `/app/src/static/js/app.js` SHA-256 prefix: `743ae29d99d0`
  - `/app/staticfiles/js/app.js` SHA-256 prefix: `fb6e80d0f076` (`match = False`)
- Any JavaScript or CSS edits under `src/static/` will **not** be served by the running Docker stack until static files are re-collected or the `web` image is rebuilt.

**Required Fix:** Run `docker compose exec web python manage.py collectstatic --noinput` (or rebuild with `docker compose up -d --build web`) whenever `src/static/` files change.

---

### Blocker 3 — Branch & Deployment Sync Lag (`37` Unpushed Commits)
- Local `fix/api` is **37 commits ahead of `origin/fix/api`** (`120` files changed, `+2,409` / `-276` lines).
- Staging/Render environments built from remote `origin/fix/api` or `dev` do not yet include these local fixes.
- Per `FUNCTIONAL_TEST_VERIFICATION_REPORT.md`, remote deployment still requires:
  1. Pushing/deploying `fix/api`.
  2. Running `python manage.py migrate` on Render (`dashboards/0003_fix_snapshot_schema`, `core/0006_create_login_throttle_cache`).
  3. Ensuring `REDIS_URL` is configured (or database login-throttle fallback table is migrated) and clean QA fixtures are used.

---

## 2. Verified Healthy / Unblocked Areas

| Area | Check Executed | Result |
|---|---|---|
| **Docker Stack** | `docker compose ps` | All 6 containers up (`db`, `redis`, `web`, `worker`, `beat`, `nginx`; `db`/`redis`/`web`/`worker` healthy) |
| **Health & Auth Routes** | Django test client (`localhost:8080`) | `GET /health/live/` -> `200`, `GET /health/ready/` -> `200`, `GET /accounts/login/` -> `200` |
| **Django System Check** | `python manage.py check` | `0` issues (`1 silenced`) |
| **Deployment Error Check** | `python manage.py check --deploy --fail-level ERROR` | Exit code `0` (`0` errors; only expected local HTTP `security.W*` warnings and `drf_spectacular` OpenAPI schema hints) |
| **Model / Migration Parity** | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| **Unapplied Migrations** | `python manage.py showmigrations --plan` | `0` unapplied migrations |
| **Owner Analytics Access** | Live check (`owner@demo.local`, `admin@apexindustrial.com`) | Both have `is_owner=True`, `report.view=True`; `/app/dashboards/` and `/app/dashboards/?section=operations` return `200`; `/app/roles/` returns `200` |
| **Contract Providers** | DB check across orgs | `demo-organization` (`2` active providers), `apex-industrial` (`2` active providers); `GET /app/contracts/agreements/new/` returns `200` |
| **Public Landing Page** | Asset existence + CSP scan (`src/templates/public/landing.html`) | Video/image assets exist on disk; `0` CSP-violating inline scripts or `on*` handlers |

---

## 3. Non-Blocking Open Items (Minor / Medium UX & Schema Warnings)
- Open minor/medium UX items from manual QA (e.g., Asset Hierarchy `relationship_type` visibility in `src/templates/assets/form.html#L93-L101`, selected missing back links/breadcrumbs, mobile responsive CSS adjustments).
- Non-fatal `drf_spectacular.W001` / `W002` OpenAPI schema generation warnings reported by `manage.py check --deploy`.

