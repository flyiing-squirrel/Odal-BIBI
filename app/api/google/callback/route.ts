import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "odal_session";

function returnToDashboard(result: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: {
      Location: `/?calendar=${encodeURIComponent(result)}`,
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
    },
  });
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const callback = request.nextUrl.searchParams;
  const state = callback.get("state");
  const code = callback.get("code");
  const error = callback.get("error");
  const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;
  const backendApiUrl = process.env.BACKEND_API_URL;
  const bffSharedSecret = process.env.BFF_SHARED_SECRET;

  if (!state || !sessionToken || !backendApiUrl || !bffSharedSecret) {
    return returnToDashboard("failed");
  }

  let target: URL;
  try {
    const backend = new URL(backendApiUrl);
    if (!["http:", "https:"].includes(backend.protocol) || backend.username || backend.password) {
      return returnToDashboard("failed");
    }
    target = new URL("/api/v1/calendar/callback", backend.origin);
  } catch {
    return returnToDashboard("failed");
  }

  try {
    const upstream = await fetch(target, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        "Content-Type": "application/json",
        "X-BFF-Secret": bffSharedSecret,
      },
      body: JSON.stringify({
        state,
        ...(code ? { code } : {}),
        ...(error ? { error } : {}),
      }),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(15_000),
    });
    if (!upstream.ok) return returnToDashboard("failed");
    const payload: unknown = await upstream.json().catch(() => null);
    if (
      typeof payload !== "object" ||
      payload === null ||
      !("status" in payload) ||
      (payload.status !== "connected" && payload.status !== "cancelled")
    ) {
      return returnToDashboard("failed");
    }
    return returnToDashboard(payload.status);
  } catch {
    return returnToDashboard("failed");
  }
}
