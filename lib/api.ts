export interface CoachProfileInput {
  interest_area: string;
  weekly_study_hours: string | null;
  learning_style: string | null;
  monthly_budget: string | null;
}

export type ProfileUpdate = Partial<CoachProfileInput>;

export interface SessionResponse extends Omit<CoachProfileInput, "interest_area"> {
  id: number;
  interest_area: string | null;
  desired_job: string | null;
  major_experience: string | null;
  owned_certifications: string[] | null;
  target_acquisition_period: string | null;
  created_at: string;
}

export interface CertificationSummary {
  id: number;
  code: string;
  name: string;
  issuer: string;
  description: string;
  official_url: string;
}

export interface RecommendationSummary {
  id: number;
  rank: number;
  match_score: number;
  priority: string;
  reason: string;
  study_plan_hint: string;
  certification: CertificationSummary;
}

export interface SourceItem {
  title: string;
  url: string;
}

export interface ConversationMessageResponse {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  sources: SourceItem[];
  created_at: string;
}

export interface ScheduleResponse {
  id: number;
  recommendation_id: number | null;
  exam_name: string;
  registration_start: string | null;
  registration_end: string | null;
  exam_date: string;
  result_date: string | null;
  status: string;
  source_name: string;
  source_url: string;
  source_verified: boolean;
  details: string | null;
  fetched_at: string;
  certification: CertificationSummary;
}

export interface GoogleCalendarStatus {
  connected: boolean;
  requires_reauthorization: boolean;
  calendar_name: string | null;
}

interface GoogleCalendarConnectResponse {
  authorization_url: string;
}

interface CalendarEventSyncResponse {
  synced: boolean;
  event_id: string;
}

export interface DashboardResponse {
  session: SessionResponse;
  recommendations: RecommendationSummary[];
  conversation: ConversationMessageResponse[];
  schedules: ScheduleResponse[];
}

export interface ChatReplyResponse {
  session_id: number;
  intent: "recommend" | "schedule" | "study_path" | "general";
  user_message: ConversationMessageResponse;
  assistant_message: ConversationMessageResponse;
  notices: string[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/backend/api/v1/coaching/sessions${path}`, {
    ...init,
    cache: "no-store",
    headers,
  });

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      typeof body === "object" && body !== null && "detail" in body &&
      typeof body.detail === "string"
        ? body.detail
        : `요청을 처리하지 못했습니다. (${response.status})`;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

function sessionPath(sessionId: number): string {
  if (!Number.isSafeInteger(sessionId) || sessionId < 1) {
    throw new Error("유효하지 않은 세션입니다.");
  }
  return `/${sessionId}`;
}

export function createSession(input: CoachProfileInput): Promise<DashboardResponse> {
  return request("", { method: "POST", body: JSON.stringify(input) });
}

export function getDashboard(sessionId: number): Promise<DashboardResponse> {
  return request(sessionPath(sessionId));
}

export function updateProfile(
  sessionId: number,
  patch: ProfileUpdate,
): Promise<DashboardResponse> {
  return request(`${sessionPath(sessionId)}/profile`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function sendMessage(
  sessionId: number,
  message: string,
): Promise<ChatReplyResponse> {
  return request(`${sessionPath(sessionId)}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function getGoogleCalendarStatus(sessionId: number): Promise<GoogleCalendarStatus> {
  return request(`${sessionPath(sessionId)}/calendar`);
}

export function connectGoogleCalendar(sessionId: number): Promise<GoogleCalendarConnectResponse> {
  return request(`${sessionPath(sessionId)}/calendar/connect`, { method: "POST" });
}

export function disconnectGoogleCalendar(sessionId: number): Promise<GoogleCalendarStatus> {
  return request(`${sessionPath(sessionId)}/calendar`, { method: "DELETE" });
}

export function syncScheduleToGoogleCalendar(
  sessionId: number,
  scheduleId: number,
): Promise<CalendarEventSyncResponse> {
  return request(`${sessionPath(sessionId)}/calendar/schedules/${scheduleId}`, {
    method: "POST",
  });
}
