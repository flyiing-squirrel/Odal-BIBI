# Vercel Preview deployment

Odal BIBI runs as two Vercel projects from one repository. The dashboard keeps its profile,
recommendations, and recent chat history in the visitor's `localStorage`. FastAPI is stateless and
only calls Groq and Tavily, so no managed database is required for this Preview release.

## Project layout

| Project | Root Directory | Purpose |
| --- | --- | --- |
| `odal-bibi-web` | repository root | Next.js dashboard and same-origin BFF |
| `odal-bibi-backend` | `backend` | FastAPI, Groq, Tavily, answer verification |

Both projects use the GitHub repository `flyiing-squirrel/Odal-BIBI`. The branch
`fix/vercel-full-stack-hardening` is the Preview deployment source. Production remains disabled
while the Preview is reviewed.

## Preview variables

Add these values in **Settings → Environment Variables**. Mark secrets as **Secret** and select
the **Preview** environment only.

### `odal-bibi-backend`

| Variable | Type | Value |
| --- | --- | --- |
| `APP_ENV` | Config | `preview` |
| `BFF_SHARED_SECRET` | Secret | At least 32 random bytes; matches the web project Preview value |
| `GROQ_API_KEY` | Secret | Existing Groq API key |
| `TAVILY_API_KEY` | Secret | Existing Tavily API key |
| `GROQ_MODEL` | Config | Optional; defaults to `openai/gpt-oss-120b` |
| `CHAT_HISTORY_LIMIT` | Config | Optional; defaults to `8` |

### `odal-bibi-web`

| Variable | Type | Value |
| --- | --- | --- |
| `BACKEND_API_URL` | Config | The deployed backend Preview URL, without a trailing path |
| `BFF_SHARED_SECRET` | Secret | Exactly the backend Preview value |

`GROQ_API_KEY` and `TAVILY_API_KEY` belong only in the backend project. Do not create
`NEXT_PUBLIC_` versions of them. The Next.js BFF adds the shared secret before forwarding a
browser request to FastAPI.

## Deployment order

1. Push the Preview branch. Vercel builds both projects from their configured root directories.
2. Open the backend Preview deployment and copy its `https://…vercel.app` URL.
3. Store that URL as `BACKEND_API_URL` in the web project and redeploy the web Preview.
4. Visit the web Preview, save a profile, then send a chat message. Check that a refresh retains
   the dashboard in the same browser.
5. Open `<backend-preview-url>/health` and confirm `{"status":"ok"}`.

Vercel environment-variable changes take effect only on new deployments. Redeploy the affected
Preview project after changing a value.

## Preview limitations

- Clearing site data or moving to another browser/device resets the dashboard.
- Google Calendar is intentionally unavailable because OAuth refresh tokens require durable
  server-side storage.
- Stateless functions have no shared rate-limit store. Request payloads are bounded; platform
  limits remain the Preview protection.
- The old PostgreSQL, session-token, and Google Calendar endpoints remain in source for a future
  stateful release, but the dashboard and BFF do not call them.

## Official references

- [Deploy FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel monorepos](https://vercel.com/docs/monorepos)
- [Vercel environment variables](https://vercel.com/docs/environment-variables)
