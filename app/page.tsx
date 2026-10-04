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
  MessageCircle,
  Send,
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
import {
  type ConversationMessageResponse,
  type RecommendationSummary,
  type ScheduleResponse,
} from "@/lib/api";
import { useCoachingSession, type Profile } from "@/lib/use-coaching-session";

type Section = "recommend" | "schedule" | "profile" | "chat";

const sections: { id: Section; label: string; icon: typeof Compass }[] = [
  { id: "recommend", label: "추천", icon: Compass },
  { id: "schedule", label: "일정", icon: CalendarDays },
  { id: "profile", label: "프로필", icon: UserRound },
  { id: "chat", label: "채팅", icon: MessageCircle },
];

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", { dateStyle: "long" }).format(new Date(value));
}

function formatDateRange(start: string | null, end: string | null): string {
  if (start && end) return `${formatDate(start)} ~ ${formatDate(end)}`;
  if (start) return `${formatDate(start)}부터`;
  if (end) return `${formatDate(end)}까지`;
  return "미확인";
}

function safeHttpUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export default function Home() {
  const [activeSection, setActiveSection] = useState<Section>("recommend");
  const {
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
  } = useCoachingSession();
  const messagesEndRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [dashboard?.conversation]);

  const nextExamDate = dashboard?.schedules[0]?.exam_date;

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
        <Badge variant="outline" className="session-badge">
          {sessionId ? "비공개 세션" : "새 코칭 세션"}
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
          onClick={() => setActiveSection(sessionId && dashboard ? "chat" : "profile")}
        >
          {sessionId && dashboard ? "코치에게 질문하기" : "프로필 설정 시작"}
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
          value={nextExamDate ? formatDate(nextExamDate) : "공식 일정 확인 대기"}
          tone="ocean"
        />
        <SummaryCard
          icon={Clock3}
          label="나의 학습 시간"
          value={profile.hours || "프로필을 입력해 주세요"}
          tone="forest"
        />
      </section>

      {error ? (
        <Alert className="dashboard-alert" role="alert">
          <AlertTitle>요청을 처리하지 못했어요.</AlertTitle>
          <AlertDescription className="dashboard-alert-content">
            <span>{error}</span>
            {sessionId && !dashboard ? (
              <Button variant="outline" size="sm" onClick={retryLoad}>
                다시 불러오기
              </Button>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

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
              recommendations={dashboard?.recommendations ?? []}
              isLoading={!isHydrated}
              onShowSchedule={() => setActiveSection("schedule")}
              onEditProfile={() => setActiveSection("profile")}
            />
          </TabsContent>
          <TabsContent value="schedule">
            <SchedulePanel schedules={dashboard?.schedules ?? []} isLoading={!isHydrated} />
          </TabsContent>
          <TabsContent value="profile">
            <ProfilePanel
              profile={profile}
              isHydrated={isHydrated}
              isSaved={profileSaved}
              isSaving={isSavingProfile}
              onChange={updateProfile}
              onSubmit={saveProfile}
            />
          </TabsContent>
          <TabsContent value="chat">
            <ChatPanel
              draft={draft}
              messages={dashboard?.conversation ?? []}
              messagesEndRef={messagesEndRef}
              hasSession={Boolean(sessionId && dashboard)}
              isSending={isSendingMessage}
              notices={chatNotices}
              onDraftChange={setDraft}
              onSend={sendMessage}
            />
          </TabsContent>
        </div>
      </Tabs>

      <footer className="page-footer">
        <span>Odal BIBI</span>
        <span>공식 출처로 확인된 일정과 세션별 코칭 결과를 표시합니다.</span>
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
  recommendations,
  isLoading,
  onShowSchedule,
  onEditProfile,
}: {
  profile: Profile;
  recommendations: RecommendationSummary[];
  isLoading: boolean;
  onShowSchedule: () => void;
  onEditProfile: () => void;
}) {
  const [featured, ...alternatives] = recommendations;
  const officialUrl = featured ? safeHttpUrl(featured.certification.official_url) : null;
  const completion = [profile.career, profile.hours, profile.learningStyle, profile.budget].filter(
    (value) => value.trim(),
  ).length;
  const completionPercent = Math.round((completion / 4) * 100);

  return (
    <div className="panel-grid">
      <section className="main-column" aria-labelledby="recommend-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">YOUR NEXT STEP</p>
            <h2 id="recommend-title">나에게 맞는 자격증 추천</h2>
          </div>
          <Badge className="recommendation-count-badge" variant="secondary">
            {recommendations.length ? `${recommendations.length}개 추천` : "프로필 기반 추천"}
          </Badge>
        </div>

        {isLoading ? (
          <Card className="featured-card" aria-busy="true" aria-label="추천을 불러오는 중">
            <CardContent className="featured-card-content">
              <Skeleton className="skeleton-field" />
              <Skeleton className="skeleton-field" />
              <Skeleton className="skeleton-field" />
            </CardContent>
          </Card>
        ) : featured ? (
          <Card className="featured-card">
            <CardContent className="featured-card-content">
              <div className="featured-topline">
                <Badge className="rank-badge">{featured.rank}순위 추천</Badge>
                <span className="match-copy">
                  <CheckCircle2 size={16} aria-hidden="true" />
                  적합도 {Math.round(featured.match_score)}점
                </span>
              </div>
              <div className="featured-body">
                <div>
                  <p className="cert-category">{featured.certification.issuer}</p>
                  <h3>{featured.certification.name}</h3>
                  <p className="featured-description">{featured.reason}</p>
                </div>
                <span className="featured-emblem" aria-hidden="true">
                  <BookOpenCheck size={30} strokeWidth={1.5} />
                </span>
              </div>
              <p className="featured-description">{featured.study_plan_hint}</p>
              <div className="profile-context">
                <div>
                  <span>관심 분야</span>
                  <strong>{profile.career || "미입력"}</strong>
                </div>
                <div>
                  <span>학습 시간</span>
                  <strong>{profile.hours || "미입력"}</strong>
                </div>
                <div>
                  <span>학습 방식</span>
                  <strong>{profile.learningStyle || "미입력"}</strong>
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
                {officialUrl ? (
                  <a href={officialUrl} target="_blank" rel="noopener noreferrer">공식 정보</a>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Alert className="recommend-empty" role="status">
            <Compass aria-hidden="true" />
            <AlertTitle>{profile.career ? "추천 결과가 없습니다." : "먼저 관심 분야를 알려주세요."}</AlertTitle>
            <AlertDescription>
              {profile.career
                ? "프로필을 다시 저장해 추천을 새로 받아보세요."
                : "프로필을 저장하면 그 정보를 바탕으로 추천을 만들어요."}
            </AlertDescription>
            <Button variant="outline" onClick={onEditProfile}>프로필 입력하기</Button>
          </Alert>
        )}

        <Card className="alternatives-card">
          <CardHeader className="compact-card-header">
            <div>
              <CardTitle>함께 살펴볼 후보</CardTitle>
              <CardDescription>관심 분야에 따라 비교해 볼 수 있어요.</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="alternative-list">
            {alternatives.length ? alternatives.map((item, index) => (
              <AlternativeRow
                key={item.id}
                initials={item.certification.name.slice(0, 3)}
                title={item.certification.name}
                detail={item.reason}
                tint={index % 2 === 0 ? "ocean" : "forest"}
              />
            )) : <p className="empty-copy">다른 추천 후보는 프로필 저장 후 확인할 수 있어요.</p>}
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
            <SettingRow label="월 예산" value={profile.budget || "미입력"} />
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
            <Progress value={completionPercent} aria-label={`프로필 입력 ${completionPercent}% 완료`} />
            <p className="progress-caption">
              관심 분야와 학습 여건을 입력하면 추천을 더 구체적으로 만들 수 있어요.
            </p>
            <Button variant="outline" className="full-button" onClick={onEditProfile}>
              프로필 완성하기
            </Button>
          </CardContent>
        </Card>

        <p className="source-note">
          추천은 저장된 프로필을 기준으로 갱신됩니다. 확인되지 않은 일정은 표시하지 않습니다.
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

function SchedulePanel({
  schedules,
  isLoading,
}: {
  schedules: ScheduleResponse[];
  isLoading: boolean;
}) {
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
          {isLoading ? "일정 불러오는 중" : schedules.length ? `${schedules.length}개 공식 일정` : "공식 일정 확인 대기"}
        </Badge>
      </div>

      {isLoading ? (
        <div className="schedule-grid" aria-busy="true" aria-label="일정 불러오는 중">
          <Skeleton className="skeleton-field" />
          <Skeleton className="skeleton-field" />
        </div>
      ) : schedules.length ? (
        <div className="schedule-grid">
          {schedules.map((schedule) => {
            const sourceUrl = safeHttpUrl(schedule.source_url);
            return <Card className="schedule-step" key={schedule.id}>
              <CardContent className="schedule-step-content">
                <div className="schedule-step-top">
                  <span className="step-number">{formatDate(schedule.exam_date)}</span>
                  <CalendarDays className="muted-icon" aria-hidden="true" />
                </div>
                <h3>{schedule.exam_name}</h3>
                <p>{schedule.certification.name}</p>
                <div className="schedule-dates">
                  <span>접수 {formatDateRange(schedule.registration_start, schedule.registration_end)}</span>
                  <span>발표 {schedule.result_date ? formatDate(schedule.result_date) : "미확인"}</span>
                </div>
                {schedule.details ? <p>{schedule.details}</p> : null}
                <span className="schedule-checked-at">확인 {formatDate(schedule.fetched_at)}</span>
                {sourceUrl ? (
                  <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                    {schedule.source_name}에서 확인
                  </a>
                ) : <span>출처 링크를 확인할 수 없습니다.</span>}
              </CardContent>
            </Card>;
          })}
        </div>
      ) : (
        <Alert className="schedule-alert" role="status">
          <CalendarDays aria-hidden="true" />
          <AlertTitle>확인된 공식 일정이 없습니다.</AlertTitle>
          <AlertDescription>
            주관 기관에서 확인된 일정이 들어오면 접수 기간과 시험일을 표시합니다. 확인 전인 날짜는 예상값으로 채우지 않습니다.
          </AlertDescription>
        </Alert>
      )}

      <Card className="schedule-source-card">
        <CardContent className="schedule-source-content">
          <span className="source-icon" aria-hidden="true">
            <Clock3 size={19} />
          </span>
          <div>
            <strong>일정은 공식 원문으로 확인해요.</strong>
            <p>출처와 확인 시점이 있는 일정만 표시합니다.</p>
          </div>
          <Badge variant="secondary" className="source-status">
            {schedules.length ? "출처 연결됨" : "확인 대기"}
          </Badge>
        </CardContent>
      </Card>
    </section>
  );
}

function ProfilePanel({
  profile,
  isHydrated,
  isSaved,
  isSaving,
  onChange,
  onSubmit,
}: {
  profile: Profile;
  isHydrated: boolean;
  isSaved: boolean;
  isSaving: boolean;
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
            입력 내용은 비공개 코칭 세션에 저장됩니다.
          </p>
        </div>
        <Badge variant="secondary" className="session-status-badge">
          <Check size={14} aria-hidden="true" /> {isSaved ? "세션 저장됨" : "저장 전"}
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
                    required
                    maxLength={200}
                  />
                </label>
                <label className="field-group" htmlFor="hours">
                  <span>일주일에 공부할 수 있는 시간</span>
                  <Input
                    id="hours"
                    value={profile.hours}
                    onChange={(event) => onChange("hours", event.target.value)}
                    placeholder="예: 주 6시간"
                    maxLength={100}
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
                    <option value="">선택 안 함</option>
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
                    maxLength={100}
                  />
                </label>
                <div className="profile-form-footer">
                  {isSaved ? (
                    <p className="saved-status" role="status">
                      <CheckCircle2 size={16} aria-hidden="true" /> 저장된 프로필입니다.
                    </p>
                  ) : (
                    <p className="privacy-note">세션 토큰은 보호된 쿠키로 보관됩니다.</p>
                  )}
                  <Button type="submit" disabled={isSaving}>
                    {isSaving ? "저장 중..." : isSaved ? "변경사항 저장" : "프로필 저장 및 추천 보기"}
                    {isSaving ? <Clock3 aria-hidden="true" /> : <Check aria-hidden="true" />}
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
            <p className="eyebrow">YOUR SETTINGS</p>
            <h3>이 정보로 추천을 정리해요.</h3>
            <p className="profile-preview-copy">
              관심 분야와 학습 여건에 따라 저장된 추천을 다시 계산합니다.
            </p>
            <div className="preview-values">
              <SettingRow label="관심 분야" value={profile.career || "아직 입력 전"} />
              <SettingRow label="공부 시간" value={profile.hours || "아직 입력 전"} />
              <SettingRow label="학습 방식" value={profile.learningStyle || "아직 입력 전"} />
              <SettingRow label="월 예산" value={profile.budget || "아직 입력 전"} />
            </div>
            <div className="local-data-note">
              <WalletCards size={16} aria-hidden="true" />
              <span>브라우저에는 세션 ID만 저장하고, 프로필은 서버에 보관합니다.</span>
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
  hasSession,
  isSending,
  notices,
  onDraftChange,
  onSend,
}: {
  draft: string;
  messages: ConversationMessageResponse[];
  messagesEndRef: RefObject<HTMLLIElement | null>;
  hasSession: boolean;
  isSending: boolean;
  notices: string[];
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
        <Badge variant="outline" className="chat-session-badge">
          {hasSession ? "비공개 대화" : "세션 시작 필요"}
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
            <span aria-hidden="true" /> {hasSession ? "세션 연결됨" : "프로필 저장 후 시작"}
          </span>
        </div>

        <ol className="chat-thread" aria-label="대화 내역" aria-live="polite">
          {messages.length ? messages.map((message) => (
              <li
                key={message.id}
                className={`chat-message ${message.role === "user" ? "user-message" : "coach-message"}`}
              >
                <span className="message-author">
                  {message.role === "user" ? "나" : message.role === "system" ? "안내" : "코치"}
                </span>
                <p>{message.content}</p>
                {message.sources.length ? (
                  <ul className="message-sources" aria-label="답변 출처">
                    {message.sources.map((source) => {
                      const href = safeHttpUrl(source.url);
                      return href ? (
                        <li key={`${message.id}-${href}`}>
                          <a href={href} target="_blank" rel="noopener noreferrer">{source.title}</a>
                        </li>
                      ) : null;
                    })}
                  </ul>
                ) : null}
              </li>
            )) : (
              <li className="chat-empty" role="status">
                {hasSession ? "첫 질문을 보내면 여기에서 대화를 이어갈 수 있어요." : "프로필을 저장하면 코치와 대화할 수 있어요."}
              </li>
            )}
          {isSending ? <li className="chat-message coach-message" role="status">답변을 준비하고 있어요...</li> : null}
          <li ref={messagesEndRef} className="message-end" aria-hidden="true" />
        </ol>

        {notices.length ? (
          <Alert className="chat-notices" role="status">
            <AlertDescription>{notices.join(" ")}</AlertDescription>
          </Alert>
        ) : null}

        <div className="prompt-chips" aria-label="추천 질문">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasSession || isSending}
            onClick={() => onSend("IT 분야 자격증을 추천해줘")}
          >
            IT 분야 자격증 추천
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasSession || isSending}
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
            disabled={!hasSession || isSending}
            maxLength={2000}
          />
          <Button
            type="submit"
            size="icon"
            aria-label="메시지 보내기"
            disabled={!draft.trim() || !hasSession || isSending}
          >
            <Send aria-hidden="true" />
          </Button>
        </form>
        <p className="chat-disclaimer">
          날짜·비용 등 사실 정보는 출처를 확인하고, 근거가 없으면 미확인으로 안내합니다.
        </p>
      </Card>
    </section>
  );
}
