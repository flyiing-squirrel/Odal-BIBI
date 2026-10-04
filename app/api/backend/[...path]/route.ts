import { createHmac } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "odal_session";
const ALLOWED_METHODS = new Set(["GET", "POST", "PATCH", "DELETE"]);
const SAFE_SEGMENT = /^[A-Za-z0-9_-]+$/;

type RouteContext = { params: Promise<{ path: string[] }> };

function isAllowedPath(path: string[]): boolean {
  if (!path.length || path.some((segment) => !SAFE_SEGMENT.test(segment))) return false;

  const isCoachingRoute =
    path.length >= 4 &&
    path[0] === "api" &&
    path[1] === "v1" &&
    path[2] === "coaching" &&
    path[3] === "sessions";
  const isGoogleCallback = path.join("/") === "api/v1/calendar/callback";
  return isCoachingRoute || isGoogleCallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSessionCreate(path: string[], method: string): boolean {
  return method === "POST" && path.join("/") === "api/v1/coaching/sessions";
}

function isSessionDelete(path: string[], method: string): boolean {
  return (
    method === "DELETE" &&
    path.length === 5 &&
    path.slice(0, 4).join("/") === "api/v1/coaching/sessions" &&
    /^\d+$/.test(path[4])
  );
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return false;

  try {
    return new URL(origin).origin === request.nextUrl.origin;
  } catch {
    return false;
  }
}

function errorResponse(status: number, detail: string): NextResponse {
  return NextResponse.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}

async function proxy(request: NextRequest, context: RouteContext): Promise<Response> {
  if (!ALLOWED_METHODS.has(request.method)) {
    return errorResponse(405, "Method not allowed");
  }

  const { path } = await context.params;
  if (!isAllowedPath(path)) return errorResponse(404, "Not found");
  if (request.method !== "GET" && !sameOrigin(request)) {
    return errorResponse(403, "Cross-origin request blocked");
  }

  const backendApiUrl = process.env.BACKEND_API_URL;
  const bffSharedSecret = process.env.BFF_SHARED_SECRET;
  if (!backendApiUrl || !bffSharedSecret || Buffer.byteLength(bffSharedSecret) < 32) {
    return errorResponse(503, "Backend proxy is not configured");
  }

  let target: URL;
  try {
    const base = new URL(backendApiUrl);
    if (!(["http:", "https:"].includes(base.protocol)) || base.username || base.password) {
      return errorResponse(503, "Backend proxy URL is invalid");
    }
    target = new URL(path.join("/"), `${base.origin}/`);
    target.search = request.nextUrl.search;
  } catch {
    return errorResponse(503, "Backend proxy URL is invalid");
  }

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("X-BFF-Secret", bffSharedSecret);

  const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;
  if (sessionToken) headers.set("Authorization", `Bearer ${sessionToken}`);

  if (isSessionCreate(path, request.method)) {
    const clientIp = request.headers.get("x-forwarded-for")?.split(",", 1)[0]?.trim() || "local";
    const rateKey = createHmac("sha256", bffSharedSecret).update(clientIp).digest("hex");
    headers.set("X-Rate-Limit-Key", rateKey);
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return errorResponse(502, "Backend is unavailable");
  }

  const responseHeaders = new Headers({
    "Cache-Control": "no-store",
    "Content-Type": upstream.headers.get("content-type") || "application/json",
  });
  let response: NextResponse;

  if (isSessionCreate(path, request.method) && upstream.ok) {
    let payload: unknown;
    try {
      payload = await upstream.json();
    } catch {
      return errorResponse(502, "Backend returned an invalid session response");
    }

    if (!isRecord(payload) || typeof payload.session_token !== "string") {
      return errorResponse(502, "Backend returned an invalid session response");
    }

    const token = payload.session_token;
    const publicPayload = { ...payload };
    delete publicPayload.session_token;
    response = NextResponse.json(publicPayload, {
      status: upstream.status,
      headers: responseHeaders,
    });
    response.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/api",
    });
  } else if (upstream.status === 204) {
    response = new NextResponse(null, { status: 204, headers: responseHeaders });
  } else {
    response = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  }

  if (isSessionDelete(path, request.method) && upstream.ok) {
    response.cookies.set(SESSION_COOKIE, "", {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/api",
      maxAge: 0,
    });
  }

  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
