# FitGate Local Development Setup Guide (Windows)

This guide provides step-by-step instructions to set up and run the entire FitGate platform on a clean Windows machine using Docker Desktop and Git. No Python or Node.js installation is required on the host machine.

---

## 1. What You Need

Before starting, ensure your Windows machine meets the following prerequisites:

- **Operating System:** Windows 10 (Build 19041 or higher) or Windows 11 (64-bit).
- **WSL2 (Windows Subsystem for Linux 2):** Installed and set as the default WSL architecture (`wsl --set-default-version 2`).
- **Docker Desktop:** Installed with the WSL2 backend enabled.
  - _Recommended Resource Setting:_ Allocate at least 6 GB of RAM to WSL2. You can configure this by creating or editing `%USERPROFILE%\.wslconfig`:
    ```ini
    [wsl2]
    memory=6GB
    processors=4
    ```
- **Git for Windows:** Installed from [git-scm.com](https://git-scm.com/).
- **Code Editor:** VS Code, Cursor, or any modern editor.
- **Web Browser:** Google Chrome, Microsoft Edge, or Mozilla Firefox (modern browsers natively resolve `*.localhost` without hosts file modification per RFC 6761).
- **Free Local Ports:** Ensure the following host ports are not occupied by other services:
  - `5173`: Frontend Vite dev server (and tenant subdomains `*.localhost:5173`)
  - `8000`: Backend Django REST API and OpenAPI docs
  - `5432`: PostgreSQL database (`fitgate_postgres`)
  - `6379`: Redis cache (`fitgate_redis`)
  - `5050`: pgAdmin 4 local database management UI (`fitgate_pgadmin`)
- **Host Tools Notice:** Neither Python nor Node.js is required on the host system. The entire application stack (backend, frontend, database, cache, admin UI) runs inside Docker containers. Python or Node on the host is only necessary if you run standalone editor linters outside Docker.

---

## 2. Get the Code

Open PowerShell and clone the repository:

```powershell
# Clone the repository (replace <repo-url> with the repository address)
git clone <repo-url> fitgate
cd fitgate

# Switch to the integration branch
git checkout develop
```

### Windows Line Endings Configuration

To prevent Windows CRLF line endings from corrupting Linux shell scripts inside Docker containers, configure Git to use standard LF line endings:

```powershell
git config --global core.autocrlf false
git config --global core.eol lf
```

### Human Contributor Branch Rules

- **Integration Branch:** All work branches from and merges into `develop`.
- **Production Branch:** `main` is strictly reserved for production deployments. Never push or merge directly into `main`.
- **Feature Branches:** Create dedicated feature branches named `feature/sprint-N-short-name` or `fix/short-name` branched from `develop`.
- **No Force Pushing:** Never force push (`git push --force`) to shared branches.
- **Merge Commits Only:** Always use merge commits (`git merge --no-ff`). Never squash merge, as squashing destroys linear sprint history.
- **Preserve Branches:** Never delete sprint or feature branches, locally or remotely.
- **Security Rule:** Never commit `.env`, private keys, API tokens, or credentials.

---

## 3. The Environment File

Create your local `.env` file by copying the provided template:

```powershell
Copy-Item .env.example .env
```

### Complete Environment Variable Reference

| Variable Name                    | Required / Optional | Purpose                                                   | Safe Local Value / Generation Command                                                       | Behavior if Left Empty                               |
| :------------------------------- | :------------------ | :-------------------------------------------------------- | :------------------------------------------------------------------------------------------ | :--------------------------------------------------- |
| `DJANGO_SETTINGS_MODULE`         | Required            | Active Django settings module                             | `fitgate.settings.local`                                                                    | Defaults to production settings                      |
| `DJANGO_SECRET_KEY`              | Required            | Cryptographic signing secret                              | `django-insecure-dev-secret-key-fitgate-sprint0-change-in-production`                       | Django fails to start                                |
| `DEBUG`                          | Required            | Enables debug mode and tracebacks                         | `True`                                                                                      | Defaults to False                                    |
| `DOMAIN`                         | Required            | Platform apex domain                                      | `localhost`                                                                                 | Subdomain routing fails                              |
| `PUBLIC_PORT`                    | Required            | Public frontend port                                      | `5173`                                                                                      | Subdomain URL generation omits port                  |
| `ALLOWED_HOSTS`                  | Optional            | Additional allowed HTTP hosts                             | Leave empty                                                                                 | Defaults to `localhost`, `127.0.0.1`, and subdomains |
| `CORS_ALLOWED_ORIGINS`           | Required            | Allowed CORS origins for browser                          | `http://localhost:5173,http://127.0.0.1:5173`                                               | Browser blocks cross-origin API calls                |
| `CSRF_TRUSTED_ORIGINS`           | Required            | Trusted origins for CSRF checks                           | `http://localhost:5173,http://localhost:8000,http://127.0.0.1:8000`                         | POST/PUT requests fail with 403 CSRF                 |
| `JWT_SIGNING_KEY`                | Optional            | HMAC key for JWT auth tokens                              | Leave empty                                                                                 | Falls back to `DJANGO_SECRET_KEY`                    |
| `SUPERADMIN_EMAIL`               | Required            | Initial Super Admin bootstrap email                       | `admin@fitgate.localhost`                                                                   | `create_super_admin` command fails                   |
| `SUPERADMIN_PASSWORD`            | Required            | Initial Super Admin bootstrap password                    | `AdminLocalPassword123!`                                                                    | `create_super_admin` command fails                   |
| `POSTGRES_DB`                    | Required            | PostgreSQL database name                                  | `fitgate_dev`                                                                               | Container uses default `postgres`                    |
| `POSTGRES_USER`                  | Required            | PostgreSQL username                                       | `postgres`                                                                                  | Connection fails                                     |
| `POSTGRES_PASSWORD`              | Required            | PostgreSQL password                                       | `postgres`                                                                                  | Connection fails                                     |
| `POSTGRES_PORT`                  | Required            | Host port mapped to PostgreSQL                            | `5432`                                                                                      | Uses 5432                                            |
| `DATABASE_URL`                   | Required            | Full database connection string                           | `postgres://postgres:postgres@postgres:5432/fitgate_dev`                                    | Backend cannot reach database                        |
| `REDIS_URL`                      | Required            | Redis connection string for cache                         | `redis://redis:6379/1`                                                                      | Cache and token blocklist fail                       |
| `PGADMIN_DEFAULT_EMAIL`          | Required            | Login email for pgAdmin UI                                | `admin@fitgate.localhost`                                                                   | pgAdmin container fails to start                     |
| `PGADMIN_DEFAULT_PASSWORD`       | Required            | Login password for pgAdmin UI                             | `admin`                                                                                     | pgAdmin container fails to start                     |
| `PGADMIN_PORT`                   | Required            | Host port mapped to pgAdmin                               | `5050`                                                                                      | Uses 5050                                            |
| `VITE_API_URL`                   | Required            | Backend API URL for frontend                              | `http://localhost:8000`                                                                     | Frontend API calls fail                              |
| `TENANT_CREDENTIALS_KEY`         | Required            | 32-byte Fernet key for encrypting gym payment credentials | Generate via `docker compose exec backend python manage.py generate_tenant_credentials_key` | Gym creation or credentials save fails               |
| `QR_JWT_PRIVATE_KEY`             | Optional            | Ed25519 private key for signing member QR codes           | Leave empty (uses built-in dev keypair)                                                     | Uses built-in development keypair                    |
| `QR_JWT_PUBLIC_KEY`              | Optional            | Ed25519 public key for verifying member QR codes          | Leave empty (uses built-in dev keypair)                                                     | Uses built-in development keypair                    |
| `EMAIL_BACKEND`                  | Required            | Outbound email routing backend                            | `django.core.mail.backends.console.EmailBackend`                                            | Emails attempt SMTP delivery                         |
| `DEFAULT_FROM_EMAIL`             | Required            | Default sender email header                               | `noreply@fitgate.localhost`                                                                 | Uses webmaster@localhost                             |
| `EMAIL_HOST`                     | Optional            | SMTP server hostname                                      | Leave empty                                                                                 | Ignored when using console backend                   |
| `EMAIL_PORT`                     | Optional            | SMTP server port                                          | `587`                                                                                       | Ignored when using console backend                   |
| `EMAIL_HOST_USER`                | Optional            | SMTP username                                             | Leave empty                                                                                 | Ignored when using console backend                   |
| `EMAIL_HOST_PASSWORD`            | Optional            | SMTP password                                             | Leave empty                                                                                 | Ignored when using console backend                   |
| `EMAIL_USE_TLS`                  | Optional            | Enable TLS for SMTP                                       | `False`                                                                                     | Ignored when using console backend                   |
| `EMAIL_USE_SSL`                  | Optional            | Enable SSL for SMTP                                       | `False`                                                                                     | Ignored when using console backend                   |
| `EMAIL_STRICT_MODE`              | Optional            | Restrict email recipients                                 | `False`                                                                                     | Inactive in dev                                      |
| `BREVO_WEBHOOK_SECRET`           | Optional            | Secret for inbound Brevo webhooks                         | Leave empty                                                                                 | Brevo webhook verification disabled                  |
| `CPANEL_USE_MOCK`                | Required            | Simulates cPanel UAPI and TLS checks locally              | `True`                                                                                      | Attempts network calls to live cPanel host           |
| `CPANEL_HOST`                    | Optional            | Live cPanel hostname                                      | Leave empty                                                                                 | Ignored when `CPANEL_USE_MOCK=True`                  |
| `CPANEL_USERNAME`                | Optional            | Live cPanel account username                              | Leave empty                                                                                 | Ignored when `CPANEL_USE_MOCK=True`                  |
| `CPANEL_API_TOKEN`               | Optional            | Live cPanel UAPI authentication token                     | Leave empty                                                                                 | Ignored when `CPANEL_USE_MOCK=True`                  |
| `CPANEL_ROOT_DOMAIN`             | Optional            | Root domain configured in cPanel                          | `localhost`                                                                                 | Defaults to localhost                                |
| `CPANEL_SUBDOMAIN_DOCROOT`       | Optional            | Document root path on cPanel                              | `public_html/fitgate`                                                                       | Defaults to public_html/fitgate                      |
| `OPENROUTER_API_KEY`             | Optional            | OpenRouter API key for live AI plans                      | Leave empty (uses built-in mock AI engine)                                                  | Uses rule-based Ethiopian AI generator               |
| `GEMINI_API_KEY`                 | Optional            | Google Gemini API key for live AI                         | Leave empty (uses built-in mock AI engine)                                                  | Uses rule-based Ethiopian AI generator               |
| `TELEGRAM_USE_MOCK`              | Required            | Simulates Telegram bot broadcasts                         | `True`                                                                                      | Attempts calls to live Telegram API                  |
| `TELEGRAM_BOT_TOKEN`             | Optional            | Bot token from @BotFather                                 | Leave empty                                                                                 | Ignored when `TELEGRAM_USE_MOCK=True`                |
| `RECEIPT_VERIFICATION_ENABLED`   | Optional            | Enable bank receipt OCR checks                            | `False`                                                                                     | Receipts accepted without OCR gating                 |
| `BANK_RECEIPT_VERIFIER_USE_MOCK` | Required            | Simulates bank transfer OCR verification                  | `True`                                                                                      | Uses real OCR engine if enabled                      |
| `DEV_TUNNEL_HOST`                | Optional            | ngrok tunnel domain for webhooks                          | Leave empty                                                                                 | Webhooks only accepted from localhost                |
| `ALLOW_DEMO_SEED`                | Required            | Guard flag allowing demo gym seeding                      | `False` (set `True` when seeding demo gym)                                                  | `seed_demo_gym` refuses to run                       |
| `DEMO_PASSWORD`                  | Optional            | Password for seeded demo accounts                         | Leave empty (defaults to `DemoPass123!`)                                                    | Seeded accounts use default password                 |
| `ALLOW_POSTGRES_13`              | Optional            | Compatibility override for PostgreSQL 13                  | `False`                                                                                     | Standard Django version check applies                |

### What is Mocked Locally

FitGate runs completely standalone out of the box with zero external accounts or credit cards required:

- **AI Workout & Nutrition Engine:** Built-in rule-based mock engine generates culturally appropriate Ethiopian meal and training plans without calling OpenAI or Gemini.
- **Telegram Notice Bridge:** Simulated broadcaster logs outbound announcements to container stdout without connecting to Telegram servers.
- **Chapa Payment Gateway:** Payment transactions and webhook verifications are simulated locally.
- **cPanel Subdomain Provisioning:** Subdomain creation and AutoSSL certificate gates are simulated instantaneously in database state.
- **Console Email Backend:** Verification emails, welcome messages, and password reset links are printed directly to `fitgate_backend` container logs.
- **Local Media Storage:** Uploaded receipts, profile photos, and gym logos are saved to local Docker volumes.
- **Receipt Verifier:** Mock OCR validator automatically approves test transfer slips.

### Collaborator-Specific Keys Rule

If you wish to test real external services (Chapa test account, Google Gemini API, Telegram bot, or live cPanel), obtain your own personal developer keys. Add them exclusively to your local `.env` file. Never commit keys or push them to any branch.

---

## 4. Start the System

Run Docker Compose to build images and launch the stack:

```powershell
docker compose up -d --build
```

### Running Containers and Ports

| Container Name     | Service    | Image / Base                | Host Port | Verification Command                       |
| :----------------- | :--------- | :-------------------------- | :-------- | :----------------------------------------- |
| `fitgate_postgres` | `postgres` | `postgres:16-alpine`        | `5432`    | `docker compose exec postgres pg_isready`  |
| `fitgate_redis`    | `redis`    | `redis:7-alpine`            | `6379`    | `docker compose exec redis redis-cli ping` |
| `fitgate_backend`  | `backend`  | Python 3.11.17 / Django 5.2 | `8000`    | `docker compose logs backend`              |
| `fitgate_frontend` | `frontend` | Node.js / Vite React SPA    | `5173`    | Open `http://localhost:5173`               |
| `fitgate_pgadmin`  | `pgadmin`  | `dpage/pgadmin4:latest`     | `5050`    | Open `http://localhost:5050`               |

### Inspect Container Status and Logs

```powershell
# Check running status and health of all containers
docker compose ps

# Follow backend logs (to see API requests, email prints, and errors)
docker compose logs -f backend

# Follow frontend dev server logs
docker compose logs -f frontend

# Follow all container logs simultaneously
docker compose logs -f
```

### Stopping the System Without Data Loss

To stop containers while safely preserving database tables, uploaded files, and state:

```powershell
docker compose stop
# or
docker compose down
```

> [!CAUTION]
> **DANGER: NEVER RUN `docker compose down -v`**
> The `-v` flag deletes all Docker volumes (`postgres_data`, `redis_data`, `pgadmin_data`). This permanently destroys your local database, provisioned tenants, members, check-in history, and audit logs.

### Executing Commands Inside Containers

To run management commands or interact with container shells:

```powershell
docker compose exec backend python manage.py <command>
docker compose exec frontend <command>
```

---

## 5. First-Time Setup

Once containers are running, perform initial database migrations and create the platform Super Admin account.

### Step 1: Run Migrations

```powershell
docker compose exec backend python manage.py migrate
```

### Step 2: Generate Tenant Credentials Encryption Key

If you have not already set `TENANT_CREDENTIALS_KEY` in your `.env`:

```powershell
docker compose exec backend python manage.py generate_tenant_credentials_key
```

Copy the printed 32-byte key, paste it into `TENANT_CREDENTIALS_KEY=` inside `.env`, and restart the backend:

```powershell
docker compose restart backend
```

### Step 3: Bootstrap Initial Super Admin

```powershell
docker compose exec backend python manage.py create_super_admin
```

This command reads `SUPERADMIN_EMAIL` (`admin@fitgate.localhost`) and `SUPERADMIN_PASSWORD` (`AdminLocalPassword123!`) from `.env`. It is completely idempotent; if a Super Admin already exists, it safely exits.

### Local Addresses Reference Table

| Service / Interface       | Local URL                         | Credentials / Notes                                                             |
| :------------------------ | :-------------------------------- | :------------------------------------------------------------------------------ |
| **Platform Apex**         | `http://localhost:5173`           | Platform landing page & Super Admin sign-in                                     |
| **Gym Tenant Subdomain**  | `http://<gym>.localhost:5173`     | e.g. `http://demo.localhost:5173` or `http://bole-power.localhost:5173`         |
| **Backend REST API**      | `http://localhost:8000/api/`      | Django REST Framework endpoints                                                 |
| **OpenAPI Documentation** | `http://localhost:8000/api/docs/` | Interactive Swagger UI API documentation                                        |
| **pgAdmin 4 Database UI** | `http://localhost:5050`           | Email: `admin@fitgate.localhost`, Password: `admin` (auto-connects to database) |

### The RFC 6761 `*.localhost` Explanation

RFC 6761 designates `.localhost` as a special-use top-level domain. Modern browsers (Google Chrome, Microsoft Edge, Mozilla Firefox) automatically resolve any subdomain matching `*.localhost` (such as `demo.localhost` or `gymname.localhost`) directly to loopback IP `127.0.0.1` entirely in-memory. **You do not need to edit `C:\Windows\System32\drivers\etc\hosts`.**

_Fallback Notice:_ If using a corporate VPN or custom DNS resolver that overrides localhost resolution, add entries to `C:\Windows\System32\drivers\etc\hosts`:

```text
127.0.0.1 demo.localhost
127.0.0.1 bole-power.localhost
```

---

## 6. Create the First Gym Through Super Admin Screen

Follow these steps to provision a tenant gym through the user interface:

1. Open your browser and go to `http://localhost:5173/login`.
2. Sign in with Super Admin credentials:
   - **Email:** `admin@fitgate.localhost`
   - **Password:** `AdminLocalPassword123!`
3. Navigate to **Gym Management** (`http://localhost:5173/gyms`) in the navigation bar.
4. Click the **Create Gym** button to open the provisioning modal.
5. Fill out the gym creation form:
   - **Gym Name:** `Bole Power Fitness`
   - **Subdomain:** `bole-power` (or click **Suggest**)
   - **Tier:** Select `Starter (12,000 ETB / yr)` or `Growth (30,000 ETB / yr)`
   - **Address (shown to members):** `Bole Atlas, Addis Ababa`
   - **Public Contact Phone:** `+251911223344`
   - **Contact Name:** `Abebe Kebede`
   - **Contact Phone:** `+251911223344`
   - **Owner Name:** `Dawit Haile`
   - **Owner Email:** `owner@bolepower.local`
   - **Confirm Owner Email:** `owner@bolepower.local`
6. Click **Create Gym**.

### The Mock Certificate Gate

Because production uses cPanel AutoSSL which takes 15–30 minutes to issue certificates, newly provisioned gyms start in an `awaiting_certificate` state (status reads _Awaiting TLS / Still Securing_). Until confirmed, accessing the gym subdomain displays a security holding page.

To activate the gym locally:

- In the Super Admin **Gym Management** table, locate the newly created gym row.
- Click the green **Confirm TLS** button.
- Alternatively, run the management command:
  ```powershell
  docker compose exec backend python manage.py check_pending_tls
  ```

### Finding the Owner's Invitation Link

Upon creation, an invitation email containing a secure password setup token is generated. Because the console email backend is active in local development, the email is logged directly to container output.

Run this PowerShell command to extract the invitation link:

```powershell
docker compose logs backend | Select-String "set-password"
```

Look for the link formatted as:

```text
http://bole-power.localhost:5173/set-password?token=<unique-invitation-token>
```

### Setting the Owner's Password in the Browser

1. Copy the full invitation URL from the console log and paste it into your browser.
2. Enter and confirm a strong password (at least 8 characters).
3. Click **Set Password**. You will be redirected to `http://bole-power.localhost:5173/login` where you can sign in as the Gym Owner.

---

## 7. The Faster Path: The Demo Gym

To bypass manual tenant setup and immediately test all role workflows with rich pre-populated data, seed the standardized demo gym:

```powershell
docker compose exec -e ALLOW_DEMO_SEED=True backend python manage.py seed_demo_gym
```

### Command Behavior & Safeguards

- **Production Guard:** The command strictly refuses to execute if `DEBUG=False` or if `ALLOW_DEMO_SEED` is not explicitly `True`.
- **Clean Archive & Recreate:** If a tenant with subdomain `demo` already exists, the command archives the old tenant and cleanly recreates a fresh gym with complete seed data.
- **Default Password:** All seeded accounts use the password specified in `DEMO_PASSWORD` in `.env`, or default to `DemoPass123!`.

### Seeded Demo Accounts Table (`http://demo.localhost:5173`)

| Role              | Email Address                                 | Default Password         | Access Level & Permissions                                                           |
| :---------------- | :-------------------------------------------- | :----------------------- | :----------------------------------------------------------------------------------- |
| **Super Admin**   | `admin@fitgate.localhost`                     | `AdminLocalPassword123!` | Platform apex (`localhost:5173`); manages all gyms, plans, and platform revenue      |
| **Gym Owner**     | `owner@demo.local`                            | `DemoPass123!`           | Complete gym management: branding, staff invitations, banking, revenue, settings     |
| **Manager**       | `manager@demo.local`                          | `DemoPass123!`           | Day-to-day operations: member registrations, plan pricing, attendance logs, receipts |
| **Receptionist**  | `reception@demo.local`                        | `DemoPass123!`           | Front-desk operations: QR attendance scanner, member check-in, cash plan sales       |
| **Trainer 1**     | `trainer1@demo.local`                         | `DemoPass123!`           | Trainer portal: client assignments, workout plan generation, fitness assessments     |
| **Trainer 2**     | `trainer2@demo.local`                         | `DemoPass123!`           | Trainer portal: client workout tracking and group class assignments                  |
| **Active Member** | `member1@demo.local`                          | `DemoPass123!`           | Member portal: dynamic QR check-in pass, active plan status, workout plans           |
| **Batch Members** | `member2@demo.local` to `member90@demo.local` | `DemoPass123!`           | Pre-seeded active, expiring, and lapsed memberships for testing analytics            |

---

## 8. What You Should See Checklist

Verify full end-to-end functionality across all 11 core system checks:

1. **Platform Apex Landing Page**
   - **Screen:** Apex Landing (`http://localhost:5173`)
   - **Role:** Unauthenticated visitor
   - **Verify:** Landing page loads with FitGate branding, feature highlights, and Super Admin Sign In link.
2. **Super Admin Login & Tenant List**
   - **Screen:** Gym Management (`http://localhost:5173/gyms`)
   - **Role:** Super Admin (`admin@fitgate.localhost`)
   - **Verify:** Displays list of all gyms, active tier statuses, renewal dates, export window countdowns, and action buttons.
3. **Gym Landing Page**
   - **Screen:** Gym Public Entry (`http://demo.localhost:5173`)
   - **Role:** Unauthenticated visitor / gym member
   - **Verify:** Custom gym name, logo, public contact phone, address, and Sign In portal button.
4. **Owner Login & Dashboard**
   - **Screen:** Owner Home / Dashboard (`http://demo.localhost:5173/dashboard`)
   - **Role:** Gym Owner (`owner@demo.local`)
   - **Verify:** Metrics cards render Active Members, Today's Check-ins, Monthly Revenue, and full Owner sidebar menu.
5. **Member Check-In with QR Code**
   - **Screen:** Member Pass (`http://demo.localhost:5173/pass`) & Reception Scanner (`http://demo.localhost:5173/attendance`)
   - **Role:** Member (`member1@demo.local`) & Receptionist (`reception@demo.local`)
   - **Verify:** Member displays dynamically rotating QR code; Receptionist scans or enters member code to record successful check-in.
6. **Member Cash Plan Purchase**
   - **Screen:** Payments / Sell Membership (`http://demo.localhost:5173/payments`)
   - **Role:** Receptionist or Manager
   - **Verify:** Record cash payment for a membership plan; receipt dialog appears and member status updates to Active.
7. **Dashboard Revenue Numbers Updated**
   - **Screen:** Financial Overview / Owner Dashboard (`http://demo.localhost:5173/dashboard`)
   - **Role:** Gym Owner
   - **Verify:** Dashboard monthly revenue and payment totals increment by the cash purchase amount. Platform subscription payments remain strictly excluded.
8. **Trainer AI Plan Generation (Mocked)**
   - **Screen:** AI Workout Generator (`http://demo.localhost:5173/trainer/plans`)
   - **Role:** Trainer (`trainer1@demo.local`)
   - **Verify:** Select client, enter goals, click "Generate AI Plan", and verify structured Ethiopian-context workout schedule is rendered.
9. **Gym Notices Board**
   - **Screen:** Gym Notice Board (`http://demo.localhost:5173/notices`)
   - **Role:** Owner / Manager posts notice; Member views notice on Member Home (`http://demo.localhost:5173/member`).
10. **Support Request Round Trip**
    - **Screen:** Contact FitGate (`http://demo.localhost:5173/support`) & Super Admin Support (`http://localhost:5173/support`)
    - **Role:** Owner submits ticket; Super Admin responds; Owner sees response in conversation thread with notification badge.
11. **Starter vs Growth Tier Menus**
    - **Screen:** Navigation Sidebar across Starter and Growth gyms
    - **Role:** Owner / Manager
    - **Verify:** Growth tier gyms show Trainers, Classes, AI Plans, Freezes, Analytics, Notices, and Expenses. Starter tier gyms strictly hide all six modules from menus and navigation.

---

## 9. Project Organization

### Directory Layout Overview

```text
fitgate/
├── backend/                  # Django 5.2 Application (Python 3.11.17)
│   ├── fitgate/              # Project settings (base.py, local.py, staging.py, urls.py)
│   ├── apps/                 # Domain-driven apps (accounts, tenants, memberships, attendance, payments, etc.)
│   └── pyproject.toml        # Ruff, Black, and Pytest configuration
├── frontend/                 # Vite React 18 Single-Page Application (TypeScript)
│   ├── src/api/              # Typed API clients and endpoint helpers
│   ├── src/components/       # Role-scoped UI components (owner, manager, reception, trainer, member, superadmin)
│   ├── src/screens/          # Screen routes mapping to application URLs
│   └── src/types/api.ts      # TypeScript interfaces generated from backend OpenAPI schema
├── deploy/                   # Production cPanel scripts, Passenger WSGI, and staging configurations
├── docs/                     # Architecture, specifications, and project management living docs
├── docker-compose.yml        # Core container definitions (postgres, redis, backend, frontend)
├── docker-compose.override.yml# Local development overrides (pgAdmin 4)
└── .env.example              # Exhaustive environment variable template
```

### Documentation Files Guide

- `docs/SPEC.md`: Authoritative specification of all functional requirements, data models, role matrix, and business rules.
- `docs/SPRINTS.md`: Incremental sprint plans, acceptance criteria, and technical task breakdowns.
- `docs/PROGRESS.md`: Living status log of completed sprints, git commit hashes, open questions, and next tasks.
- `docs/OPEN_QUESTIONS.md`: Architectural log of design decisions, trade-offs, and clarifications.
- `docs/DESIGN.md`: UI design tokens, theme color palette, input validation rules, and error states.
- `docs/MANUAL_STEPS.md`: Production deployment checklist, credentials tracking, and staging instructions.
- `docs/INCREMENT_*_TEST.md`: Manual click-through validation scripts for non-developers at each increment milestone.

### Human Contributor Workflow Rules (from `AGENT.md`)

- **Documentation First:** Update `docs/SPEC.md`, `docs/SPRINTS.md`, and `docs/PROGRESS.md` on your branch before implementing code.
- **Strict Branch Discipline:** Work only on dedicated feature branches from `develop`; never push or merge directly into `main`.
- **Merge Commit Policy:** Always merge into `develop` using non-fast-forward merge commits (`git merge --no-ff`). Never squash.
- **Keep Branch and Tag History:** Never delete branches after merging. Tag each completed sprint or milestone (`sprint-N-done`) and push both the branch and tag to the remote repository.

---

## 10. Run the Tests

All tests, linters, and formatters execute inside the running Docker containers.

### Backend Tests (pytest)

```powershell
# Run the full backend test suite (~200+ tests, runtime ~25-40s)
docker compose exec backend pytest

# Run a specific test file
docker compose exec backend pytest apps/tenants/tests/test_services.py

# Run tests for a single application module
docker compose exec backend pytest apps/memberships/
```

### Frontend Tests (vitest)

```powershell
# Run all frontend unit and component tests (runtime ~8-15s)
docker compose exec frontend npm test

# Run a specific test file
docker compose exec frontend npx vitest run src/__tests__/createGym.test.tsx
```

### Code Formatting and Linting

```powershell
# Backend lint check (Ruff)
docker compose exec backend ruff check .

# Backend format check (Black)
docker compose exec backend black --check .

# Auto-format backend code
docker compose exec backend black .

# Frontend lint check (ESLint)
docker compose exec frontend npm run lint

# Frontend format check (Prettier)
docker compose exec frontend npm run format:check

# Auto-format frontend code
docker compose exec frontend npm run format
```

### Optional PostgreSQL 13 Compatibility Validation

Production cPanel runs PostgreSQL 13. To validate that database queries and migrations pass on PostgreSQL 13 before deploying:

```powershell
# 1. Spin up a temporary PostgreSQL 13 container on the Docker network
docker run -d --name pg13test --network fitgate_default -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fitgate_test -e POSTGRES_USER=postgres postgres:13-alpine

# 2. Run the test suite against the PostgreSQL 13 instance
docker compose exec -e DATABASE_URL="postgres://postgres:postgres@pg13test:5432/fitgate_test" -e ALLOW_POSTGRES_13=1 backend pytest

# 3. Clean up the temporary container
docker stop pg13test
docker rm pg13test
```

---

## 11. Optional Real-Service Setup

To test third-party integrations with real services instead of mocks:

### 1. Chapa Payment Gateway with ngrok

Register a free test merchant account at [dashboard.chapa.co](https://dashboard.chapa.co). Start an ngrok tunnel on port 8000 (`ngrok http 8000`) and set `DEV_TUNNEL_HOST=<subdomain>.ngrok-free.app` in `.env`. Under Gym Owner > Settings > Payment Methods, enter your Chapa test secret and public keys. Webhook callbacks will route directly through your tunnel to the backend. See [MANUAL_STEPS.md](file:///d:/personal%20projects/fitgate/docs/MANUAL_STEPS.md) Step 10.

### 2. Gemini / OpenRouter AI Keys

Generate an API key from [Google AI Studio](https://aistudio.google.com/) or [OpenRouter](https://openrouter.ai/). In `.env`, set `GEMINI_API_KEY=<your-key>` or `OPENROUTER_API_KEY=<your-key>`, and set `AI_PROVIDER_MOCK=False`. The trainer workout generator will call live LLM models for schedule generation. See [MANUAL_STEPS.md](file:///d:/personal%20projects/fitgate/docs/MANUAL_STEPS.md) Step 12.

### 3. Telegram Bot Integration

Create a bot via `@BotFather` on Telegram and obtain an API token. In `.env`, set `TELEGRAM_BOT_TOKEN=<your-token>` and `TELEGRAM_USE_MOCK=False`. Notices published on the gym notice board will automatically broadcast to your linked Telegram channel. See [MANUAL_STEPS.md](file:///d:/personal%20projects/fitgate/docs/MANUAL_STEPS.md) Step 14.

### 4. Bank Transfer Receipt Verification

In `.env`, set `BANK_RECEIPT_VERIFIER_USE_MOCK=False` and `RECEIPT_VERIFICATION_ENABLED=True`. Uploaded bank transfer slips will be processed using multimodal vision models (`GEMINI_API_KEY`) to extract reference numbers, bank names, and transfer amounts. See [MANUAL_STEPS.md](file:///d:/personal%20projects/fitgate/docs/MANUAL_STEPS.md) Step 11.

### 5. Live cPanel UAPI Integration

In your cPanel dashboard (Security > Manage API Tokens), generate a token named `FitGate-UAPI`. In `.env`, set `CPANEL_USE_MOCK=False`, `CPANEL_HOST=<cpanel-host>`, `CPANEL_USERNAME=<user>`, and `CPANEL_API_TOKEN=<token>`. Super Admin gym creation will provision real DNS subdomains and trigger AutoSSL scans. See [MANUAL_STEPS.md](file:///d:/personal%20projects/fitgate/docs/MANUAL_STEPS.md) Step 1 and [DEPLOY_STAGING.md](file:///d:/personal%20projects/fitgate/docs/DEPLOY_STAGING.md).

---

## 12. Troubleshooting

Twelve common local development issues, symptoms, and exact one-line fixes:

1. **Host Port Already in Use**
   - _Symptom:_ `listen tcp 0.0.0.0:<port>: bind: address already in use`
   - _Fix:_ Identify the blocking PID with `Get-NetTCPConnection -LocalPort <port>` and terminate it with `Stop-Process -Id <pid> -Force`, or change the host port in `.env`.
2. **Docker Desktop or WSL2 Not Running**
   - _Symptom:_ `error during connect: open //./pipe/docker_engine: The system cannot find the file specified`
   - _Fix:_ Launch Docker Desktop from the Start menu and verify WSL2 integration is enabled under Docker Settings > Resources > WSL Integration.
3. **Backend Container Restarting Continuously**
   - _Symptom:_ `docker compose ps` reports `fitgate_backend` state as `Restarting (1)`
   - _Fix:_ Inspect startup exceptions with `docker compose logs backend` to identify syntax errors or missing required variables in `.env`.
4. **Migrations Failing or Database Schema Drift**
   - _Symptom:_ `django.db.utils.ProgrammingError: relation "..." does not exist`
   - _Fix:_ Apply pending database migrations with `docker compose exec backend python manage.py migrate`.
5. **Wrong or Missing Environment Variable**
   - _Symptom:_ Backend throws configuration errors or startup validation failures
   - _Fix:_ Run `docker compose exec backend python manage.py check_env` to validate all configuration parameters against `.env.example`.
6. **Gym Subdomain Displays "Still Securing" (503)**
   - _Symptom:_ Visiting `http://<gym>.localhost:5173` displays "This gym is still securing its domain"
   - _Fix:_ In Super Admin Gym Management, click the green "Confirm TLS" button, or run `docker compose exec backend python manage.py check_pending_tls`.
7. **Tenant Subdomain Login Loop or 401 Unauthorized**
   - _Symptom:_ Login form refreshes without entering dashboard or reports 401
   - _Fix:_ Verify you are accessing the frontend on port 5173 (`http://<gym>.localhost:5173`), clear browser cookies/localStorage for `*.localhost`, and ensure user belongs to that tenant.
8. **Emails Not Appearing in Console Output**
   - _Symptom:_ Invitation links or password reset emails cannot be found
   - _Fix:_ Ensure `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` in `.env` and view logs with `docker compose logs -f backend`.
9. **Frontend Hot-Reload Not Updating on File Changes**
   - _Symptom:_ Code edits in `frontend/src` do not reflect in the browser
   - _Fix:_ Restart the frontend container with `docker compose restart frontend`, or add `server: { watch: { usePolling: true } }` in `frontend/vite.config.ts`.
10. **Windows CRLF Line Endings Breaking Container Shell Scripts**
    - _Symptom:_ Container crashes with `/bin/sh: ./entrypoint.sh: /bin/sh^M: bad interpreter`
    - _Fix:_ Run `git config --global core.autocrlf false`, or convert file endings to LF using `((Get-Content <file> -Raw) -replace "`r`n", "`n") | Set-Content -NoNewline <file>`.
11. **WSL2 / Docker Disk or Memory Exhaustion**
    - _Symptom:_ Docker freezes, containers exit with code 137 (OOMKilled), or disk writes fail
    - _Fix:_ Limit WSL2 memory in `%USERPROFILE%\.wslconfig` (e.g. `memory=6GB`) and reclaim Docker disk space with `docker system prune -a --volumes -f`.
12. **Safely Resetting the Local Database from Scratch**
    - _Symptom:_ Local test database is corrupted or needs a completely clean slate
    - _Fix:_ Run `docker compose down -v` followed by `docker compose up -d` and `docker compose exec backend python manage.py migrate` (wipes database volume while keeping all code intact).
