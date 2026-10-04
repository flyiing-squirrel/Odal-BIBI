# Browser storage deployment design

## Goal

Deploy the dashboard to Vercel without a managed database. A visitor's profile, recommendations,
and chat history remain in that visitor's browser only while Groq and Tavily are called from the
FastAPI backend so their credentials remain server-side.

## Scope

- Store one versioned dashboard record in `localStorage` under the Odal BIBI origin.
- Replace database-backed dashboard creation and chat calls in the browser flow with stateless
  FastAPI endpoints.
- Keep the existing same-origin Next.js BFF and shared-secret boundary between the web and API
  Vercel projects.
- Generate recommendations and chat replies from the profile and recent browser conversation sent
  in each request. The backend does not retain that payload.
- Keep the schedule panel, but show only source-verified schedules returned with a recommendation.
  No schedule is invented when no official schedule adapter exists.
- Disable Google Calendar connection and syncing for this deployment because OAuth state and refresh
  tokens require durable server-side storage.

## Data flow

1. The dashboard validates and writes its local record after a profile save or chat reply.
2. The browser sends the profile, at most 20 recent messages, and a new message to the BFF.
3. The BFF validates the same-origin request and adds `X-BFF-Secret` before forwarding it.
4. FastAPI validates the request, calls Groq and Tavily, verifies cited factual claims, and returns
   a reply without writing a database record.
5. The browser appends the validated reply to the locally stored dashboard.

## Security and limits

- Groq and Tavily keys are backend Preview Secrets only; no `NEXT_PUBLIC_` value carries a key.
- `localStorage` is used for user-visible dashboard data, never for authentication or provider
  credentials.
- The BFF retains its same-origin check and 32-byte shared secret requirement.
- Browser-provided profile and conversation content is treated as untrusted and constrained by
  Pydantic schemas before it reaches an LLM prompt.
- Stateless Vercel functions cannot enforce a durable distributed rate limit without an external
  store. Request size, message count, and message length are bounded; platform-level limits remain
  the deployment control for the Preview release.

## User-visible behavior

- Data survives refreshes in the same browser and origin.
- Clearing site data or changing browser/device starts a new dashboard.
- Google Calendar controls explain that persistent storage is required and are unavailable in this
  database-free release.
- Production remains disabled. Preview is the verification target.

## Rollback

The release remains on `fix/vercel-full-stack-hardening`. Reverting the browser-storage commit and
redeploying restores the prior database-backed implementation; no migration or remote data rollback
is needed because the browser record is not stored by the service.
