"use client";

import { useEffect, useState, type FormEvent } from "react";

import {
  createBrowserDashboard,
  sendBrowserMessage,
  type CoachProfileInput,
  type DashboardResponse,
} from "@/lib/api";

export type Profile = {
  career: string;
  hours: string;
  learningStyle: string;
  budget: string;
};

const DASHBOARD_STORAGE_KEY = "odal-bibi-browser-dashboard-v1";
const LEGACY_LOCAL_KEYS = [
  "odal-bibi-profile",
  "odal-bibi-chat",
  "odal-bibi-session-id",
];

const emptyProfile: Profile = {
  career: "",
  hours: "",
  learningStyle: "",
  budget: "",
};

function profileFromDashboard(dashboard: DashboardResponse): Profile {
  return {
    career: dashboard.session.interest_area ?? "",
    hours: dashboard.session.weekly_study_hours ?? "",
    learningStyle: dashboard.session.learning_style ?? "",
    budget: dashboard.session.monthly_budget ?? "",
  };
}

function apiProfile(profile: Profile): CoachProfileInput {
  return {
    interest_area: profile.career.trim(),
    weekly_study_hours: profile.hours.trim() || null,
    learning_style: profile.learningStyle.trim() || null,
    monthly_budget: profile.budget.trim() || null,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "잠시 후 다시 시도해 주세요.";
}

function isDashboardResponse(value: unknown): value is DashboardResponse {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.session === "object" &&
    record.session !== null &&
    Array.isArray(record.recommendations) &&
    Array.isArray(record.conversation) &&
    Array.isArray(record.schedules)
  );
}

function readDashboard(): DashboardResponse | null {
  const stored = window.localStorage.getItem(DASHBOARD_STORAGE_KEY);
  if (!stored) return null;
  try {
    const parsed: unknown = JSON.parse(stored);
    return isDashboardResponse(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function persistDashboard(dashboard: DashboardResponse): void {
  window.localStorage.setItem(DASHBOARD_STORAGE_KEY, JSON.stringify(dashboard));
}

export function useCoachingSession() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chatNotices, setChatNotices] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      try {
        for (const key of LEGACY_LOCAL_KEYS) window.localStorage.removeItem(key);
        const savedDashboard = readDashboard();
        if (savedDashboard && !cancelled) {
          setDashboard(savedDashboard);
          setProfile(profileFromDashboard(savedDashboard));
          setProfileSaved(true);
        }
      } catch {
        if (!cancelled) {
          setError("브라우저 저장소에 접근할 수 없어 저장된 대시보드를 불러오지 못했어요.");
        }
      } finally {
        if (!cancelled) setIsHydrated(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadAttempt]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingProfile(true);
    setError(null);
    try {
      const savedDashboard = await createBrowserDashboard(apiProfile(profile));
      setDashboard(savedDashboard);
      setProfile(profileFromDashboard(savedDashboard));
      setProfileSaved(true);
      persistDashboard(savedDashboard);
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || !dashboard || !profileSaved || isSendingMessage) return;

    setIsSendingMessage(true);
    setError(null);
    setChatNotices([]);
    try {
      const reply = await sendBrowserMessage(apiProfile(profile), dashboard.conversation, trimmed);
      const updatedDashboard = {
        ...dashboard,
        conversation: [...dashboard.conversation, reply.user_message, reply.assistant_message],
      };
      setChatNotices(reply.notices);
      setDashboard(updatedDashboard);
      persistDashboard(updatedDashboard);
      setDraft("");
    } catch (sendError) {
      setError(errorMessage(sendError));
    } finally {
      setIsSendingMessage(false);
    }
  }

  function updateProfile(key: keyof Profile, value: string) {
    setProfile((current) => ({ ...current, [key]: value }));
    setProfileSaved(false);
  }

  function retryLoad() {
    setError(null);
    setIsHydrated(false);
    setLoadAttempt((value) => value + 1);
  }

  return {
    profile,
    dashboard,
    sessionId: dashboard?.session.id ?? null,
    isHydrated,
    isSavingProfile,
    isSendingMessage,
    profileSaved,
    error,
    chatNotices,
    draft,
    setDraft,
    saveProfile,
    sendMessage,
    updateProfile,
    retryLoad,
  };
}
