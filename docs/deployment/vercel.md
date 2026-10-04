# Vercel deployment setup

Odal BIBI is deployed as two Vercel projects from the same Git repository. The Next.js app is the browser-facing BFF; FastAPI and all provider credentials stay in the backend project.

## Create the two projects

In Vercel, import the same repository twice:

| Project | Root Directory | Runtime |
| --- | --- | --- |
| Odal BIBI web | repository root `/` | Next.js |
| Odal BIBI backend | `/backend` | FastAPI on Vercel Python Runtime |

Set the root directory before the first deployment. The backend's `pyproject.toml` points Vercel to `app.main:app`. The two projects have separate environment variables and deployments; pushing a branch can create Preview deployments for both.

## Environment variables

Create variables from **Project → Settings → Environment Variables**. Vercel currently labels stored values as **Config** or **Secret**. Use **Secret** for API keys, database credentials, BFF secrets, Google OAuth client secrets, and encryption keys. Secret values cannot be read back after saving. Use **Config** for URLs, model names, environment names, and pool limits.

### Next.js project (`/`)

| Variable | Type | Preview | Production |
| --- | --- | --- | --- |
| `BACKEND_API_URL` | Config | FastAPI Preview URL | FastAPI Production URL |
| `BFF_SHARED_SECRET` | Secret | Same value as backend Preview | Same value as backend Production |

Use a different random BFF secret for Preview and Production. Within each environment, the web and backend projects must use the matching value. Keep it at least 32 bytes. No Groq, Tavily, database, Google client-secret, or token-encryption key belongs in this project.

### FastAPI project (`/backend`)

| Variable | Type | Preview | Production |
| --- | --- | --- | --- |
| `APP_NAME` | Config | `자격증 패스 코치 API` (default) | `자격증 패스 코치 API` (default) |
| `APP_ENV` | Config | `preview` | `production` |
| `DATABASE_URL` | Secret | Preview database pooled URL | Separate Production database pooled URL |
| `BFF_SHARED_SECRET` | Secret | Same value as web Preview | Same value as web Production |
| `CORS_ORIGINS` | Config | Exact web Preview origin(s) | Exact web Production origin(s) |
| `DB_POOL_SIZE` | Config | `1` | `1` |
| `DB_MAX_OVERFLOW` | Config | `0` | `0` |
| `DB_POOL_TIMEOUT` | Config | `5` | `5` |
| `DB_POOL_PRE_PING` | Config | `true` | `true` |
| `SESSION_CREATION_LIMIT_PER_HOUR` | Config | `5` (default) | `5` (default) |
| `PROFILE_UPDATES_PER_HOUR` | Config | `5` (default) | `5` (default) |
| `CHAT_MESSAGES_PER_HOUR` | Config | `30` (default) | `30` (default) |
| `RATE_LIMIT_WINDOW_SECONDS` | Config | `3600` (default) | `3600` (default) |
| `CHAT_HISTORY_LIMIT` | Config | `8` (default) | `8` (default) |
| `GROQ_API_KEY` | Secret | Add to Preview when ready | Add separately after Production approval |
| `GROQ_MODEL` | Config | `openai/gpt-oss-120b` | `openai/gpt-oss-120b` |
| `TAVILY_API_KEY` | Secret | Add to Preview when ready | Add separately after Production approval |
| `GOOGLE_CLIENT_ID` | Config | Preview OAuth client ID | Production OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Secret | Preview OAuth client secret | Production OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Config | Exact Preview web URL + `/api/google/callback` | Exact Production web URL + `/api/google/callback` |
| `GOOGLE_TOKEN_ENCRYPTION_CURRENT_VERSION` | Config | `v1` | `v1` |
| `GOOGLE_TOKEN_ENCRYPTION_KEY_V1` | Secret | Unique Preview key | Separate Production key |
| `GOOGLE_TOKEN_ENCRYPTION_KEY_V2` | Secret | Leave unset until rotation | Leave unset until rotation |

The `.env.example` file lists the same variable names for local development. Do not put values in the repository or in any `NEXT_PUBLIC_` variable. Preview and Production must use different databases. The backend uses a provider's pooled PostgreSQL URL; DBeaver should use the provider's direct connection URL.

## Add your Groq and Tavily keys to Preview

Your Groq and Tavily keys are used by FastAPI only:

1. Open the **Odal BIBI backend** project (root directory `/backend`).
2. Open **Settings → Environment Variables**.
3. Add `GROQ_API_KEY`, paste the Groq key in Vercel's value field, choose **Preview**, and select **Secret**.
4. Repeat for `TAVILY_API_KEY` with the Tavily key.
5. Add the other required Preview values from the table, especially `DATABASE_URL` and the matching `BFF_SHARED_SECRET`.
6. Save, then create a new Preview deployment or redeploy the backend Preview. Environment-variable changes apply to new deployments, not deployments already built.
7. In the Preview app, confirm chat responses and web search work. If a key needs rotation, update it in the provider first, replace the Vercel Secret, redeploy, verify, then retire the old key.

Do not add these keys to the Next.js project. Keep them Preview-only until the Preview flow is accepted; then add Production values to the backend project and use a separate Production database. If your Vercel team requires distinct Production Secret values, use separate provider keys for Production.

## Dependency advisory

As of 2026-10-04, `npm audit` reports 9 high-severity dependency-path findings that trace to the single GitHub advisory [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) for `braces@3.0.3`, reached through development tools such as `shadcn` and `eslint-config-next`. The advisory has no patched `braces` release; `npm audit fix` made no compatible changes, and its suggested fixes require breaking dependency changes. `npm audit --omit=dev --audit-level=high` reports no production dependency vulnerabilities. Recheck after the upstream package publishes a fix.

## PostgreSQL and migrations

Choose a managed PostgreSQL provider before creating Preview and Production databases. Keep them separate. Set the application's `DATABASE_URL` to the provider's pooled endpoint using the SQLAlchemy psycopg driver form:

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

Use the provider's **direct** endpoint from DBeaver. Before the first deployment, apply Alembic migrations to the Preview database from a trusted development environment. Temporarily provide its direct URL as `DATABASE_URL`, then run:

```powershell
Set-Location backend
uv run alembic upgrade head
```

Do not commit the database URL. Apply the same migration process to Production only after the Preview release is accepted and the Production database is ready.

## Google Calendar callback and encryption keys

Register the exact `GOOGLE_REDIRECT_URI` shown in the backend project for that environment in Google Cloud OAuth credentials. It must point to the corresponding Next.js project's `/api/google/callback`; Google compares the redirect URI exactly. Keep the OAuth client secret and encryption keys in the backend project only.

Generate a URL-safe 32-byte key locally; do not paste it into this repository:

```powershell
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='))"
```

Set the result as `GOOGLE_TOKEN_ENCRYPTION_KEY_V1` in the backend project's Secret variable. For key rotation, deploy the new key alongside the old key, switch `GOOGLE_TOKEN_ENCRYPTION_CURRENT_VERSION`, allow stored tokens to be re-encrypted, and retain the old key until every retained connection has been rotated or reconnected.

## Deployment checks

- Check `/health` on the FastAPI Preview deployment.
- Confirm the Next.js Preview's `BACKEND_API_URL` points to the backend Preview URL.
- Confirm the same-environment BFF secrets match across projects.
- Confirm Groq chat and Tavily search work without exposing keys in the browser.
- Confirm the Preview app uses the Preview database and that migrations are current.
- Confirm Google OAuth's registered callback exactly matches the Preview web URL.
- Add Production secrets and deploy only after Preview has been reviewed.

## Official Vercel references

- [Deploy a FastAPI app on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Using monorepos on Vercel](https://vercel.com/docs/monorepos)
- [Environment variables](https://vercel.com/docs/environment-variables)
- [Config and Secret environment variable types](https://vercel.com/docs/environment-variables/sensitive-environment-variables)
