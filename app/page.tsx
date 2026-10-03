"use client";

import { useEffect, useRef, useState, type FormEvent, type RefObject } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  Compass,
  FileCheck2,
  Link2,
  MessageCircle,
  Send,
  Unplug,
  UserRound,
  WalletCards,
} from "lucide-react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type Section = "recommend" | "schedule" | "profile" | "chat";

type Profile = {
  career: string;
  hours: string;
  learningStyle: string;
  budget: string;
};

type Message = {
  id: string;
  role: "coach" | "user";
  text: string;
};

type CalendarConnection = {
  configured: boolean;
  connected: boolean;
  status: string;
  email: string | null;
  calendar_name: string | null;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const PROFILE_KEY = "odal-bibi-profile";
const CHAT_KEY = "odal-bibi-chat";

const defaultProfile: Profile = {
  career: "IT·데이터 분야",
  hours: "주 6시간",
  learningStyle: "문제 풀이 중심",
  budget: "월 5만 원 이내",
};

const firstMessage: Message = {
  id: "welcome",
  role: "coach",
  text: "안녕하세요. 자격증 준비를 한곳에서 정리해 볼게요. 추천이나 일정에 관해 궁금한 내용을 입력해 보세요.",
};

const sections: { id: Section; label: string; icon: typeof Compass }[] = [
  { id: "recommend", label: "추천", icon: Compass },
  { id: "schedule", label: "일정", icon: CalendarDays },
  { id: "profile", label: "프로필", icon: UserRound },
  { id: "chat", label: "채팅", icon: MessageCircle },
];

export default function Home() {
  const [activeSection, setActiveSection] = useState<Section>("recommend");
  const [profile, setProfile] = useState<Profile>(defaultProfile);
  const [messages, setMessages] = useState<Message[]>([firstMessage]);
  const [isHydrated, setIsHydrated] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [draft, setDraft] = useState("");
  const messagesEndRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    try {
      const savedProfile = localStorage.getItem(PROFILE_KEY);
      const savedChat = localStorage.getItem(CHAT_KEY);

      if (savedProfile) {
        const parsedProfile = JSON.parse(savedProfile) as Partial<Profile>;
        // Browser storage must be read after SSR to keep the first render consistent.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setProfile({ ...defaultProfile, ...parsedProfile });
        setProfileSaved(true);
      }

      if (savedChat) {
        const parsedChat = JSON.parse(savedChat) as Message[];
        if (Array.isArray(parsedChat) && parsedChat.length > 0) {
          setMessages(parsedChat);
        }
      }
    } catch {
      // Ignore invalid local data and keep the sample profile.
    } finally {
      setIsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("section") === "schedule") {
      // OAuth returns to the schedule area after the account flow.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveSection("schedule");
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    setProfileSaved(true);
  }

  function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    const answer = getDemoReply(trimmed, profile);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: trimmed },
      { id: crypto.randomUUID(), role: "coach", text: answer },
    ]);
    setDraft("");
  }

  function updateProfile(key: keyof Profile, value: string) {
    setProfile((current) => ({ ...current, [key]: value }));
    setProfileSaved(false);
  }

  useEffect(() => {
    if (isHydrated) localStorage.setItem(CHAT_KEY, JSON.stringify(messages));
  }, [isHydrated, messages]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Odal BIBI 홈">
          <span className="brand-mark" aria-hidden="true">
            <Compass size={21} strokeWidth={1.8} />
          </span>
          <span className="brand-copy">
            <span className="brand-name">Odal BIBI</span>
            <span className="brand-caption">자격증 준비 대시보드</span>
          </span>
        </a>
        <Badge variant="outline" className="demo-badge">
          화면 데모
        </Badge>
      </header>

      <section className="welcome-row" id="top">
        <div>
          <p className="eyebrow">CERTIFICATE PATH COACH</p>
          <h1>준비의 다음 한 걸음을 찾아요.</h1>
          <p className="welcome-copy">
            나에게 맞는 자격증을 살펴보고, 준비할 정보를 한곳에 모아보세요.
          </p>
        </div>
        <Button
          className="welcome-action"
          onClick={() => setActiveSection("chat")}
        >
          코치에게 질문하기
          <ArrowRight aria-hidden="true" />
        </Button>
      </section>

      <section className="summary-row" aria-label="준비 현황 요약">
        <SummaryCard
          icon={Compass}
          label="관심 분야"
          value={profile.career || "프로필을 입력해 주세요"}
          tone="sand"
        />
        <SummaryCard
          icon={CalendarDays}
          label="시험 일정"
          value="공식 일정 연결 전"
          tone="ocean"
        />
        <SummaryCard
          icon={Clock3}
          label="나의 학습 시간"
          value={profile.hours || "프로필을 입력해 주세요"}
          tone="forest"
        />
      </section>

      <Tabs
        value={activeSection}
        onValueChange={(value) => {
          if (value) setActiveSection(value as Section);
        }}
        className="dashboard-tabs-root"
      >
        <TabsList variant="line" className="dashboard-tabs" aria-label="대시보드 메뉴">
          {sections.map(({ id, label, icon: Icon }) => (
            <TabsTrigger key={id} value={id} className="dashboard-tab">
              <Icon aria-hidden="true" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <div className="section-content">
          <TabsContent value="recommend">
            <RecommendationPanel
              profile={profile}
              onShowSchedule={() => setActiveSection("schedule")}
              onEditProfile={() => setActiveSection("profile")}
            />
          </TabsContent>
          <TabsContent value="schedule">
            <SchedulePanel />
          </TabsContent>
          <TabsContent value="profile">
            <ProfilePanel
              profile={profile}
              isHydrated={isHydrated}
              isSaved={profileSaved}
              onChange={updateProfile}
              onSubmit={saveProfile}
            />
          </TabsContent>
          <TabsContent value="chat">
            <ChatPanel
              draft={draft}
              messages={messages}
              messagesEndRef={messagesEndRef}
              onDraftChange={setDraft}
              onSend={sendMessage}
            />
          </TabsContent>
        </div>
      </Tabs>

      <footer className="page-footer">
        <span>Odal BIBI</span>
        <span>화면 예시 데이터 · 실제 추천 및 일정 연동 전</span>
      </footer>
    </main>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Compass;
  label: string;
  value: string;
  tone: "sand" | "ocean" | "forest";
}) {
  return (
    <Card className="summary-card">
      <CardContent className="summary-card-content">
        <span className={`summary-icon ${tone}`} aria-hidden="true">
          <Icon size={19} strokeWidth={1.8} />
        </span>
        <span className="summary-copy">
          <span className="summary-label">{label}</span>
          <span className="summary-value">{value}</span>
        </span>
      </CardContent>
    </Card>
  );
}

function RecommendationPanel({
  profile,
  onShowSchedule,
  onEditProfile,
}: {
  profile: Profile;
  onShowSchedule: () => void;
  onEditProfile: () => void;
}) {
  return (
    <div className="panel-grid">
      <section className="main-column" aria-labelledby="recommend-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">YOUR NEXT STEP</p>
            <h2 id="recommend-title">나에게 맞는 자격증 추천</h2>
          </div>
          <Badge className="sample-badge" variant="secondary">
            예시 프로필 기준
          </Badge>
        </div>

        <Card className="featured-card">
          <CardContent className="featured-card-content">
            <div className="featured-topline">
              <Badge className="rank-badge">1순위 추천</Badge>
              <span className="match-copy">
                <CheckCircle2 size={16} aria-hidden="true" />
                조건을 바탕으로 살펴볼 후보
              </span>
            </div>
            <div className="featured-body">
              <div>
                <p className="cert-category">IT · 데이터</p>
                <h3>정보처리기사</h3>
                <p className="featured-description">
                  {profile.career || "관심 분야"} 준비를 시작할 때 기초 역량을
                  정리하기 좋은 자격증 예시입니다.
                </p>
              </div>
              <span className="featured-emblem" aria-hidden="true">
                <BookOpenCheck size={30} strokeWidth={1.5} />
              </span>
            </div>
            <div className="profile-context">
              <div>
                <span>학습 시간</span>
                <strong>{profile.hours || "미입력"}</strong>
              </div>
              <div>
                <span>학습 방식</span>
                <strong>{profile.learningStyle || "미입력"}</strong>
              </div>
              <div>
                <span>비용 기준</span>
                <strong>{profile.budget || "미입력"}</strong>
              </div>
            </div>
            <div className="featured-actions">
              <Button onClick={onShowSchedule}>
                시험 일정 보기
                <ArrowRight aria-hidden="true" />
              </Button>
              <Button variant="outline" onClick={onEditProfile}>
                프로필 조정
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="alternatives-card">
          <CardHeader className="compact-card-header">
            <div>
              <CardTitle>함께 살펴볼 후보</CardTitle>
              <CardDescription>관심 분야에 따라 비교해 볼 수 있어요.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="alternative-list">
            <AlternativeRow
              initials="SQL"
              title="SQLD"
              detail="데이터베이스 기초를 다지고 싶다면"
              tint="ocean"
            />
            <AlternativeRow
              initials="AD"
              title="ADsP"
              detail="데이터 분석의 전체 흐름을 익히고 싶다면"
              tint="forest"
            />
          </CardContent>
        </Card>
      </section>

      <aside className="side-column" aria-label="준비 관련 안내">
        <Card className="profile-summary-card">
          <CardHeader>
            <div className="card-heading-line">
              <div>
                <CardTitle>현재 설정</CardTitle>
                <CardDescription>프로필에 맞춰 추천을 정리해요.</CardDescription>
              </div>
              <UserRound className="muted-icon" aria-hidden="true" />
            </div>
          </CardHeader>
          <CardContent className="setting-list">
            <SettingRow label="관심 분야" value={profile.career || "미입력"} />
            <SettingRow label="학습 가능 시간" value={profile.hours || "미입력"} />
            <SettingRow label="학습 방식" value={profile.learningStyle || "미입력"} />
          </CardContent>
          <div className="side-card-action">
            <Button variant="ghost" size="sm" onClick={onEditProfile}>
              프로필 수정
              <ArrowRight aria-hidden="true" />
            </Button>
          </div>
        </Card>

        <Card className="progress-card">
          <CardContent className="progress-card-content">
            <span className="progress-icon" aria-hidden="true">
              <FileCheck2 size={20} />
            </span>
            <div className="progress-heading">
              <div>
                <p className="eyebrow">START SMALL</p>
                <h3>첫 준비 단계</h3>
              </div>
              <span className="progress-value">1 / 3</span>
            </div>
            <Progress value={33} aria-label="첫 준비 단계 진행률 33%" />
            <p className="progress-caption">
              관심 분야와 공부 시간을 입력하면 다음 단계로 넘어갈 수 있어요.
            </p>
            <Button variant="outline" className="full-button" onClick={onEditProfile}>
              프로필 완성하기
            </Button>
          </CardContent>
        </Card>

        <p className="source-note">
          추천과 시험 일정은 실제 데이터 연결 전의 화면 예시입니다.
        </p>
      </aside>
    </div>
  );
}

function AlternativeRow({
  initials,
  title,
  detail,
  tint,
}: {
  initials: string;
  title: string;
  detail: string;
  tint: "ocean" | "forest";
}) {
  return (
    <div className="alternative-row">
      <span className={`alternative-icon ${tint}`} aria-hidden="true">
        {initials}
      </span>
      <div className="alternative-copy">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
      <span className="alternative-arrow" aria-hidden="true">
        <ArrowRight size={17} />
      </span>
    </div>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="setting-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SchedulePanel() {
  const [connection, setConnection] = useState<CalendarConnection | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [calendarNotice, setCalendarNotice] = useState("");
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  useEffect(() => {
    let isCurrent = true;
    const notice = new URLSearchParams(window.location.search).get("calendar");
    const notices: Record<string, string> = {
      connected: "Google Calendar 연결을 완료했어요.",
      cancelled: "Google Calendar 연결을 취소했어요.",
      reauthorize: "Google 재연결이 필요해요. 연결 버튼을 눌러 다시 동의해 주세요.",
      setup_error: "Google 계정은 확인했지만 전용 캘린더를 만들지 못했어요. 다시 연결해 주세요.",
    };

    async function loadConnection() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calendar/google/connection`, {
          credentials: "include",
        });
        if (!response.ok) throw new Error("연결 상태를 불러오지 못했어요.");
        const data = (await response.json()) as CalendarConnection;
        if (isCurrent) setConnection(data);
      } catch {
        if (isCurrent) setConnectionError("캘린더 서버에 연결할 수 없어요. 백엔드 실행 상태를 확인해 주세요.");
      }
      if (isCurrent && notice && notices[notice]) setCalendarNotice(notices[notice]);
    }

    void loadConnection();
    return () => {
      isCurrent = false;
    };
  }, []);

  function connectCalendar() {
    // Google OAuth is hosted by the API origin, outside this Next.js route tree.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = `${API_BASE_URL}/api/v1/calendar/google/connect`;
  }

  async function disconnectCalendar() {
    setIsDisconnecting(true);
    setConnectionError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/calendar/google/connection`, {
        method: "DELETE",
        credentials: "include",
      });
      const data = (await response.json()) as CalendarConnection & { detail?: string };
      if (!response.ok) throw new Error(data.detail || "연결을 해제하지 못했어요.");
      setConnection(data);
      setCalendarNotice("Google Calendar 연결을 해제했어요. 기존 캘린더 일정은 유지됩니다.");
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "연결을 해제하지 못했어요.");
    } finally {
      setIsDisconnecting(false);
    }
  }

  return (
    <section className="schedule-panel" aria-labelledby="schedule-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">EXAM SCHEDULE</p>
          <h2 id="schedule-title">시험 일정을 한눈에</h2>
          <p className="panel-subtitle">
            접수부터 발표까지, 확인해야 할 일정을 모아둘 공간입니다.
          </p>
        </div>
        <Badge className="schedule-badge" variant="outline">
          일정 데이터 연결 전
        </Badge>
      </div>

      <Alert className="schedule-alert">
        <CalendarDays aria-hidden="true" />
        <AlertTitle>공식 시험 일정은 아직 표시하지 않습니다.</AlertTitle>
        <AlertDescription>
          현재 화면은 디자인 데모이며, 실제 일정은 주관 기관의 공식 정보 연동 후
          확인 날짜와 함께 제공할 예정입니다.
        </AlertDescription>
      </Alert>

      <Card className="google-calendar-card">
        <CardContent className="google-calendar-content">
          <span className="source-icon" aria-hidden="true">
            <CalendarDays size={19} />
          </span>
          <div className="google-calendar-copy">
            <strong>Google Calendar</strong>
            <p>
              {connection?.connected
                ? `${connection.email} · ${connection.calendar_name}에 공식 시험일을 저장합니다.`
                : "개인 일정은 읽지 않고, 공식 확인이 끝난 시험일만 Odal BIBI 캘린더에 추가합니다."}
            </p>
            {calendarNotice && <span className="calendar-feedback" role="status">{calendarNotice}</span>}
            {connectionError && <span className="calendar-feedback error" role="alert">{connectionError}</span>}
            {connection && !connection.configured && (
              <span className="calendar-feedback">Google OAuth 설정 후 연결할 수 있어요.</span>
            )}
          </div>
          {connection?.connected ? (
            <Button variant="outline" onClick={disconnectCalendar} disabled={isDisconnecting}>
              <Unplug aria-hidden="true" />
              {isDisconnecting ? "해제 중…" : "연결 해제"}
            </Button>
          ) : (
            <Button onClick={connectCalendar} disabled={!connection?.configured}>
              <Link2 aria-hidden="true" />
              Google 연결
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="schedule-grid">
        <ScheduleStep
          number="01"
          title="원서 접수"
          detail="공식 일정 확인 후 표시"
          icon={FileCheck2}
        />
        <ScheduleStep
          number="02"
          title="시험일"
          detail="공식 일정 확인 후 표시"
          icon={CalendarDays}
        />
        <ScheduleStep
          number="03"
          title="합격자 발표"
          detail="공식 일정 확인 후 표시"
          icon={CheckCircle2}
        />
      </div>

      <Card className="schedule-source-card">
        <CardContent className="schedule-source-content">
          <span className="source-icon" aria-hidden="true">
            <Clock3 size={19} />
          </span>
          <div>
            <strong>일정은 공식 원문으로 확인해요.</strong>
            <p>확정되지 않은 날짜는 표시하지 않고, 출처와 확인 시점을 함께 보여줍니다.</p>
          </div>
          <Badge variant="secondary" className="source-status">
            준비 중
          </Badge>
        </CardContent>
      </Card>
    </section>
  );
}

function ScheduleStep({
  number,
  title,
  detail,
  icon: Icon,
}: {
  number: string;
  title: string;
  detail: string;
  icon: typeof CalendarDays;
}) {
  return (
    <Card className="schedule-step">
      <CardContent className="schedule-step-content">
        <div className="schedule-step-top">
          <span className="step-number">{number}</span>
          <Icon className="muted-icon" aria-hidden="true" />
        </div>
        <h3>{title}</h3>
        <p>{detail}</p>
        <span className="pending-label">
          <span aria-hidden="true" /> 확인 대기
        </span>
      </CardContent>
    </Card>
  );
}

function ProfilePanel({
  profile,
  isHydrated,
  isSaved,
  onChange,
  onSubmit,
}: {
  profile: Profile;
  isHydrated: boolean;
  isSaved: boolean;
  onChange: (key: keyof Profile, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="profile-panel" aria-labelledby="profile-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">YOUR PROFILE</p>
          <h2 id="profile-title">나에게 맞게 설정하기</h2>
          <p className="panel-subtitle">
            입력한 내용은 이 브라우저에만 저장됩니다.
          </p>
        </div>
        <Badge variant="secondary" className="local-badge">
          <Check size={14} aria-hidden="true" /> 브라우저 저장
        </Badge>
      </div>

      <div className="profile-layout">
        <Card className="profile-form-card">
          <CardHeader>
            <CardTitle>준비 조건</CardTitle>
            <CardDescription>
              아직 모르는 항목은 비워두고 시작해도 괜찮아요.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!isHydrated ? (
              <div className="profile-skeleton" aria-busy="true" aria-label="프로필 불러오는 중">
                <Skeleton className="skeleton-field" />
                <Skeleton className="skeleton-field" />
                <Skeleton className="skeleton-field" />
              </div>
            ) : (
              <form className="profile-form" onSubmit={onSubmit}>
                <label className="field-group" htmlFor="career">
                  <span>관심 분야 또는 목표 직무</span>
                  <Input
                    id="career"
                    value={profile.career}
                    onChange={(event) => onChange("career", event.target.value)}
                    placeholder="예: 데이터 분석, 개발"
                  />
                </label>
                <label className="field-group" htmlFor="hours">
                  <span>일주일에 공부할 수 있는 시간</span>
                  <Input
                    id="hours"
                    value={profile.hours}
                    onChange={(event) => onChange("hours", event.target.value)}
                    placeholder="예: 주 6시간"
                  />
                </label>
                <label className="field-group" htmlFor="learning-style">
                  <span>선호하는 학습 방식</span>
                  <select
                    id="learning-style"
                    className="native-select"
                    value={profile.learningStyle}
                    onChange={(event) => onChange("learningStyle", event.target.value)}
                  >
                    <option>문제 풀이 중심</option>
                    <option>개념 강의 중심</option>
                    <option>독학 중심</option>
                    <option>혼합형</option>
                  </select>
                </label>
                <label className="field-group" htmlFor="budget">
                  <span>월 학습 예산</span>
                  <Input
                    id="budget"
                    value={profile.budget}
                    onChange={(event) => onChange("budget", event.target.value)}
                    placeholder="예: 무료 우선, 월 5만 원 이내"
                  />
                </label>
                <div className="profile-form-footer">
                  {isSaved ? (
                    <p className="saved-status" role="status">
                      <CheckCircle2 size={16} aria-hidden="true" /> 저장했어요.
                    </p>
                  ) : (
                    <p className="privacy-note">저장하기 전에는 브라우저에 기록되지 않아요.</p>
                  )}
                  <Button type="submit">
                    프로필 저장
                    <Check aria-hidden="true" />
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>

        <Card className="profile-preview-card">
          <CardContent className="profile-preview-content">
            <span className="profile-preview-icon" aria-hidden="true">
              <UserRound size={22} />
            </span>
            <p className="eyebrow">PREVIEW</p>
            <h3>이 정보로 추천을 정리해요.</h3>
            <p className="profile-preview-copy">
              관심 분야와 공부 시간, 비용 기준을 바탕으로 후보를 비교하는 화면입니다.
            </p>
            <div className="preview-values">
              <SettingRow label="관심 분야" value={profile.career || "아직 입력 전"} />
              <SettingRow label="공부 시간" value={profile.hours || "아직 입력 전"} />
              <SettingRow label="월 예산" value={profile.budget || "아직 입력 전"} />
            </div>
            <div className="local-data-note">
              <WalletCards size={16} aria-hidden="true" />
              <span>계정·서버 동기화는 아직 연결되지 않았습니다.</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function ChatPanel({
  draft,
  messages,
  messagesEndRef,
  onDraftChange,
  onSend,
}: {
  draft: string;
  messages: Message[];
  messagesEndRef: RefObject<HTMLLIElement | null>;
  onDraftChange: (value: string) => void;
  onSend: (text: string) => void;
}) {
  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSend(draft);
  }

  return (
    <section className="chat-panel" aria-labelledby="chat-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">ASK YOUR COACH</p>
          <h2 id="chat-title">무엇이 궁금하세요?</h2>
          <p className="panel-subtitle">추천이나 일정에 관해 질문을 남겨보세요.</p>
        </div>
        <Badge variant="outline" className="chat-demo-badge">
          데모 응답
        </Badge>
      </div>

      <Card className="chat-card">
        <div className="chat-topline">
          <div className="chat-coach-avatar" aria-hidden="true">
            <Compass size={19} />
          </div>
          <div>
            <strong>Odal BIBI 코치</strong>
            <span>자격증 준비 도우미</span>
          </div>
          <span className="online-indicator">
            <span aria-hidden="true" /> 화면 미리보기
          </span>
        </div>

        <ol className="chat-thread" aria-label="대화 내역" aria-live="polite">
          {messages.map((message) => (
            <li
              key={message.id}
              className={`chat-message ${message.role === "user" ? "user-message" : "coach-message"}`}
            >
              <span className="message-author">
                {message.role === "user" ? "나" : "코치"}
              </span>
              <p>{message.text}</p>
            </li>
          ))}
          <li ref={messagesEndRef} className="message-end" aria-hidden="true" />
        </ol>

        <div className="prompt-chips" aria-label="추천 질문">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSend("IT 분야 자격증을 추천해줘")}
          >
            IT 분야 자격증 추천
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSend("시험 일정은 어디서 확인해?")}
          >
            시험 일정 확인
          </Button>
        </div>

        <form className="chat-composer" onSubmit={submitMessage}>
          <Textarea
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="궁금한 내용을 입력해 주세요."
            aria-label="코치에게 보낼 메시지"
            rows={1}
            className="chat-input"
          />
          <Button
            type="submit"
            size="icon"
            aria-label="메시지 보내기"
            disabled={!draft.trim()}
          >
            <Send aria-hidden="true" />
          </Button>
        </form>
        <p className="chat-disclaimer">
          현재 채팅은 화면 시연용 답변을 사용하며 외부 AI와 연결되지 않습니다.
        </p>
      </Card>
    </section>
  );
}

function getDemoReply(text: string, profile: Profile) {
  if (/일정|시험|접수/.test(text)) {
    return "공식 시험 일정은 아직 연결되지 않았어요. 일정 탭에서 어떤 정보가 표시될지 미리 확인할 수 있습니다.";
  }
  if (/프로필|시간|예산|비용/.test(text)) {
    return `현재 예시 프로필은 ${profile.career || "관심 분야 미입력"}, ${profile.hours || "공부 시간 미입력"} 기준이에요. 프로필 탭에서 조건을 바꾸고 저장할 수 있습니다.`;
  }
  return `현재 화면은 ${profile.career || "관심 분야"} 기준의 추천 예시를 보여줍니다. 실제 추천 기능은 다음 단계에서 연결할 수 있어요.`;
}
