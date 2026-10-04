"use client";

import { useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  createSession,
  getDashboard,
  sendMessage as sendChatMessage,
  updateProfile as saveRemoteProfile,
  type CoachProfileInput,
  type DashboardResponse,
} from "@/lib/api";

export type Profile = {
  career: string;
  hours: string;
  learningStyle: string;
  budget: string;
};

const SESSION_ID_KEY = "odal-bibi-session-id";
const LEGACY_LOCAL_KEYS = ["odal-bibi-profile", "odal-bibi-chat"];

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

export function useCoachingSession() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
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

    async function loadSavedSession() {
      let rawSessionId: string | null;
      try {
        for (const key of LEGACY_LOCAL_KEYS) window.localStorage.removeItem(key);
        rawSessionId = window.localStorage.getItem(SESSION_ID_KEY);
      } catch {
        await Promise.resolve();
        if (!cancelled) {
          setError("브라우저 저장소에 접근할 수 없어 세션을 자동으로 불러오지 못했어요.");
          setIsHydrated(true);
        }
        return;
      }

      const storedSessionId = rawSessionId ? Number(rawSessionId) : NaN;
      if (!Number.isSafeInteger(storedSessionId) || storedSessionId < 1) {
        if (rawSessionId) {
          try {
            window.localStorage.removeItem(SESSION_ID_KEY);
          } catch {
            // Continue with an empty session if browser storage is unavailable.
          }
        }
        await Promise.resolve();
        if (!cancelled) setIsHydrated(true);
        return;
      }

      try {
        const savedDashboard = await getDashboard(storedSessionId);
        if (cancelled) return;
        setSessionId(storedSessionId);
        setDashboard(savedDashboard);
        setProfile(profileFromDashboard(savedDashboard));
        setProfileSaved(true);
        setError(null);
      } catch (loadError) {
        if (cancelled) return;
        if (loadError instanceof ApiError && loadError.status === 404) {
          try {
            window.localStorage.removeItem(SESSION_ID_KEY);
          } catch {
            // The next session save can overwrite this stale id when storage is available.
          }
          setSessionId(null);
          setDashboard(null);
          setProfile(emptyProfile);
          setProfileSaved(false);
          setError("저장된 세션을 찾지 못했어요. 프로필을 저장해 새 세션을 시작해 주세요.");
        } else {
          setSessionId(storedSessionId);
          setError(errorMessage(loadError));
        }
      } finally {
        if (!cancelled) setIsHydrated(true);
      }
    }

    void loadSavedSession();
    return () => {
      cancelled = true;
    };
  }, [loadAttempt]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingProfile(true);
    setError(null);
    try {
      const input = apiProfile(profile);
      const savedDashboard = sessionId
        ? await saveRemoteProfile(sessionId, input)
        : await createSession(input);
      const savedSessionId = savedDashboard.session.id;
      setSessionId(savedSessionId);
      setDashboard(savedDashboard);
      setProfile(profileFromDashboard(savedDashboard));
      setProfileSaved(true);
      try {
        window.localStorage.setItem(SESSION_ID_KEY, String(savedSessionId));
      } catch {
        setError("프로필은 저장했지만 브라우저에 세션 ID를 저장하지 못했어요. 새로고침하면 다시 연결해야 합니다.");
      }
    } catch (saveError) {
      setError(errorMessage(saveError));
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || !sessionId || isSendingMessage) return;

    setIsSendingMessage(true);
    setError(null);
    setChatNotices([]);
    try {
      const reply = await sendChatMessage(sessionId, trimmed);
      setChatNotices(reply.notices);
      setDashboard((current) =>
        current
          ? {
              ...current,
              conversation: [...current.conversation, reply.user_message, reply.assistant_message],
            }
          : current,
      );
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
    setIsHydrated(false);
    setLoadAttempt((value) => value + 1);
  }

  return {
    profile,
    dashboard,
    sessionId,
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
