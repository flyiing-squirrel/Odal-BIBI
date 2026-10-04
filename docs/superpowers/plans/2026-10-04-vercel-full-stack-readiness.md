# Odal BIBI Vercel 풀스택 준비 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 브라우저별 비공개 세션, 출처 검증 채팅, 실제 API를 사용하는 대시보드, Google Calendar 연동, PostgreSQL migration을 갖춘 Odal BIBI를 Vercel 프리뷰 배포까지 준비한다.

**Architecture:** 저장소 루트의 Next.js와 `backend/`의 FastAPI를 서로 다른 Vercel 프로젝트로 배포한다. Next.js same-origin API 프록시가 HttpOnly 쿠키를 세션 Bearer 토큰으로 변환하고, FastAPI는 PostgreSQL에서 토큰 해시와 세션 소유권을 검증한다. DB 스키마는 Alembic으로 변경하고, API 키와 DB 비밀값은 각 Vercel 프로젝트의 서버 환경변수에만 둔다.

**Tech Stack:** Next.js 16, React 19, FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL, Alembic, Groq, Tavily, Google Calendar OAuth, Vercel Python Runtime.

**Spec:** [2026-10-04 Vercel 풀스택 배포 준비 설계](../specs/2026-10-04-vercel-full-stack-readiness-design.md)

## Global Constraints

- 사용자가 승인한 범위는 추천·일정·프로필·채팅 대시보드와 이전에 승인한 Google Calendar 연동이다.
- LLM은 Groq를 사용한다. Solar Pro 4는 사용하지 않는다.
- 브라우저에 세션 비밀 토큰이나 API 키를 노출하지 않는다. 브라우저에는 HttpOnly 세션 쿠키만 두며 `NEXT_PUBLIC_` 접두어로 비밀값을 만들지 않는다.
- `GROQ_API_KEY`와 `TAVILY_API_KEY`는 FastAPI Vercel 프로젝트(`/backend`)의 서버 환경변수로만 설정한다. 우선 Preview에 추가해 프리뷰 배포에서 확인하고, 프로덕션 준비가 된 뒤 Production 환경에 별도로 추가한다. 환경변수 변경은 새 배포부터 적용된다.
- 검색 결과에 출처가 있더라도 날짜·응시료·응시자격 등 핵심 사실은 출처 및 verifier 검사를 통과해야 한다. 불확실하면 `미확인`으로 처리한다.
- 공식 확인 자료가 없는 mock 일정은 실제 일정처럼 표시하거나 Google Calendar에 동기화하지 않는다.
- 프로덕션 PostgreSQL 공급자·접속정보와 Vercel 프로젝트 접근 권한이 마련되기 전에는 프로덕션 배포하지 않는다. Preview와 Production DB는 분리한다.
- 사용자가 구현을 검토하며 단계별로 진행할 수 있도록 각 작업은 별도 커밋으로 끝낸다. 이번 계획 승인 전에는 코드를 구현하지 않는다.
- 사용자 요청 전에는 테스트 파일을 추가하거나 테스트 스위트를 실행하지 않는다. 변경 후 `git diff --check`, 린트, 빌드, Python 컴파일 같은 비테스트 검사는 수행한다.

## Review Focus

1. 경로별 세션 소유권 누락, 쿠키·CSRF 오류, Next.js 프록시 우회 가능성
2. 구조화 출력·인용 ID·공식 출처·verifier 실패 시 핵심 사실이 노출되는 경로
3. Alembic migration의 재실행 안전성, 기존 데이터 보존, 시작 시 DDL/seed 제거 여부
4. 프로필 필드와 프런트엔드/API/DB 계약의 일치, mock UI 상태의 오표시
5. Google OAuth state·redirect·토큰 저장, Vercel Preview/Production 비밀값 분리, API 사용량 제한

## Task 1: PostgreSQL 스키마 수명주기를 Alembic으로 옮기기

**Files:** `backend/app/main.py`, `backend/app/db.py`, `backend/app/core/config.py`, `backend/app/services/coaching.py`, `backend/app/models.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/`, `backend/pyproject.toml`, `backend/requirements.txt`, `backend/.python-version`, `backend/uv.lock`, `.env.example`, `README.md`.

- [x] `main.py`의 lifespan에서 `Base.metadata.create_all()`과 `ensure_catalog()` 호출을 제거한다. `CoachingService.create_session()`이 매 요청마다 catalog seed를 수행하지 않게 한다.
- [x] 현재 모델을 생성하는 초기 Alembic revision을 작성하고, 정적 자격증명 catalog를 revision 안에서 안정적인 코드 키로 삽입한다. 향후 catalog 갱신은 별도 revision으로 관리한다.
- [x] `backend/app/db.py`에서 PostgreSQL 엔진의 `pool_size`, `max_overflow`, `pool_timeout`, `pool_pre_ping`을 설정값으로 제한한다. SQLite 로컬 실행 설정은 유지한다.
- [x] Python 버전을 3.12로 고정하고 `uv.lock`을 생성해 배포 의존성을 재현 가능하게 한다.
- [x] README의 로컬 실행 절차에 `alembic upgrade head`를 추가하고, 앱 시작 시 테이블이 자동 생성된다는 기존 설명을 제거한다. 풀 설정 이름은 `.env.example`에 기록한다.
- [x] 변경을 `db: add Alembic migrations and serverless pool limits` 메시지로 커밋한다.

**Interfaces:** `get_settings() -> Settings`; `get_db() -> Generator[Session, None, None]`; migration URL은 `DATABASE_URL` 설정을 읽고 psycopg SQLAlchemy URL을 사용한다.

**Verification:** Python 3.12 환경에서 `python -m compileall -q app`, `ruff check app/db.py app/core/config.py app/main.py app/services/coaching.py alembic`, `alembic upgrade --sql head`, `uv lock --check`, `git diff --check`를 확인한다. 앱 시작·세션 생성 코드에 schema DDL 또는 catalog seed가 남지 않았는지 검색한다. 전체 `ruff check app alembic`은 기존 코드의 lint 항목 29개를 보고하므로, 이 task에서는 변경 범위만 검사한다.

## Task 2: 세션 capability와 Next.js same-origin 프록시 구현

**Files:** `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/core/config.py`, 신규 `backend/app/security.py`, `backend/app/api/routes.py`, 신규 `app/api/backend/[...path]/route.ts`, 신규 `lib/api.ts`, `.env.example`.

- [x] 세션 생성 때 256-bit 이상 난수 토큰을 만들고 SHA-256 해시만 세션 DB 레코드에 저장한다. 생성 응답 타입 `CreateSessionResponse(DashboardResponse)`는 응답 직후 한 번만 원문 `session_token: str`을 포함한다.
- [x] 모든 세션 API에 `require_bff_secret(x_bff_secret: str | None = Header(default=None, alias="X-BFF-Secret")) -> None`을 적용한다. 세션 생성은 BFF 인증만 요구하고, 세션 ID가 있는 읽기·쓰기·삭제 경로에는 추가로 `require_session_owner(session_id: int, credentials: HTTPAuthorizationCredentials, db: Session) -> None`을 적용한다.
  - 토큰은 세션 ID와 함께 확인하고, DB 해시와 비교할 때 상수 시간 비교를 사용한다.
- [x] 소유 세션에 `DELETE /api/v1/coaching/sessions/{session_id}`를 추가해 하위 메시지·추천·일정과 세션을 삭제한다.
- [x] Next.js catch-all 프록시는 `GET`, `POST`, `PATCH`, `DELETE`만 허용하고, 고정된 `BACKEND_API_URL`로 전달한다. `BFF_SHARED_SECRET`를 서버 헤더로 넣고 세션 쿠키가 있을 때만 Bearer 토큰으로 전달한다.
- [x] 생성 응답에서는 `session_token`을 JSON에서 제거하고 `HttpOnly; SameSite=Lax; Secure(운영); Path=/api` 쿠키로 설정한다. `Path=/api`는 BFF와 Google OAuth callback 모두에 쿠키가 전달되도록 한다. 로컬 HTTP 개발에서는 `Secure`를 끈다. 세션 삭제 응답은 쿠키를 만료시킨다.
- [x] 프록시의 변경 요청은 허용된 `Origin`을 검사한다. 세션 생성은 ingress client address의 해시 기준으로, 채팅은 session ID 기준으로 PostgreSQL 공유 상태 요청 제한을 적용하고 임계값은 설정값으로 둔다. 원 IP는 rate-limit 저장소나 로그에 남기지 않는다.
- [x] API 키·BFF 비밀값·세션 토큰을 로그에 쓰지 않는다. 제한되지 않은 임의 URL 프록시가 되지 않도록 경로와 메서드를 제한한다.
- [x] 변경을 `security: isolate browser sessions behind BFF` 메시지로 커밋한다.

**Interfaces:** 프런트엔드 브라우저는 `/api/backend/...`만 호출한다. FastAPI는 `X-BFF-Secret`와 소유 세션 경로에 대한 `Authorization: Bearer <session-token>`을 모두 확인한다. 쿠키 토큰 원문은 프런트엔드 JavaScript에서 읽을 수 없어야 한다.

**검증:** `npm run lint`, `npm run build`, `uv run python -m compileall -q app`, `uv run ruff check --ignore B008 app/api/routes.py app/core/config.py app/models.py app/schemas.py app/services/coaching.py app/security.py alembic`(backend/ 기준), `uv lock --check`, `uv run alembic upgrade --sql head`, `git diff --check`를 확인한다. FastAPI의 `Depends()` 기본값 관례 때문에 B008만 제외했고, 저장소 전체의 기존 Ruff 항목은 Task 1에 기록했다. 토큰 제거, HttpOnly/Secure 쿠키, 허용 메서드, Origin 검사도 정적으로 확인했다. 실제 DB 공급자가 설정되지 않아 온라인 migration은 적용하지 않았다.

## Task 3: 프로필/API 계약 정리와 대시보드 데이터 연결

**Files:** `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/core/config.py`, `backend/app/providers/base.py`, `backend/app/providers/groq_llm.py`, `backend/app/providers/mock_llm.py`, `backend/app/providers/official_schedule.py`, `backend/app/services/coaching.py`, `backend/app/services/chat.py`, `backend/app/api/routes.py`, `backend/app/security.py`, 새 migration, `app/page.tsx`, `app/globals.css`, `lib/api.ts`, `lib/use-coaching-session.ts`, `.env.example`, `README.md`.

- [x] UI가 이미 수집하는 `career`, `hours`, `learningStyle`, `budget`에 대응해 `interest_area: str`, `weekly_study_hours: str`, `learning_style: str`, `monthly_budget: str` 백엔드 필드를 추가한다. 이 값을 `desired_job`, 경험, 보유 자격증, 목표 취득 시기로 추정 변환하지 않는다. 기존 열은 과거 데이터 호환을 위해 유지하되 새 요청의 필수값에서 제외하고 nullable로 전환한다. 새 프로필 필드도 기존 행에 임의 값으로 채우지 않는다.
- [x] `CoachInput`과 recommendation prompt에 네 필드를 전달하고 DB에 저장한다. 프로필 갱신 계약은 `PATCH /api/v1/coaching/sessions/{session_id}/profile` 및 부분 갱신 schema `ProfileUpdate`로 정의한다.
- [x] 첫 프로필 저장은 `POST /coaching/sessions`로 세션을 만들고, 이후 저장은 `PATCH .../profile`로 처리한다. 프로필 갱신 후 반환하는 대시보드 데이터는 갱신된 프로필과 추천을 함께 반영한다.
- [x] 프로필 변경은 새 추천을 생성하므로 세션별 고정 구간 요청 제한을 적용하고, 세션 삭제 시 해당 제한 카운터도 정리한다.
- [x] 화면 진입 시 저장된 비밀 아닌 `session_id`만 사용해 dashboard를 재조회한다. 프로필과 대화 내용 전체를 localStorage에서 읽거나 쓰지 않는다. 세션 토큰은 쿠키에만 둔다.
- [x] 추천·일정·채팅 상태를 `lib/api.ts`의 타입 지정된 same-origin 요청 함수로 연결하고, `getDemoReply`, 시연용 추천 데이터와 “화면 예시 데이터” 표시를 제거한다. 빈 상태·로딩·오류 상태를 제공한다.
- [x] 공식 일정 provider가 확인한 레코드가 없으면 일정 목록은 비워 두고 확인 대기 UI를 유지한다.
- [x] 기존 DB에 저장된 `Mock Official Schedule Adapter`의 가짜 일정 행은 migration에서 삭제한다. 모의 일정은 복구하지 않는다.
- [x] 변경을 `feat: connect dashboard to private coaching sessions` 메시지로 커밋한다.

**Interfaces:** `ProfileUpdate`는 네 UI 프로필 필드의 선택적 부분 갱신을 받는다. `PATCH .../profile`은 업데이트된 `DashboardResponse`를 반환한다. 브라우저 API 모듈은 `createSession(input): Promise<DashboardResponse>`, `getDashboard(sessionId): Promise<DashboardResponse>`, `updateProfile(sessionId, patch): Promise<DashboardResponse>`, `sendMessage(sessionId, message): Promise<ChatReplyResponse>`를 export한다.

**Verification:** `npm run lint`, `npm run build`, `uv run python -m compileall -q app`, `uv run ruff check --ignore B008`를 변경한 백엔드 경로에 실행하고, `uv lock --check`, `uv run alembic upgrade --sql head`, `git diff --check`를 확인한다. 필드 이름·타입을 `CoachInput`→ORM→추천 프롬프트→응답→React 폼 경로로 대조하고, localStorage에는 session ID만 쓰며 구형 프로필·대화 키를 제거하는지 검색한다. FastAPI의 `Depends()` 기본값 관례 때문에 B008만 제외하고 전체 테스트는 실행하지 않는다. DB 접속 설정이 없어 온라인 migration은 적용하지 않는다.

## Task 4: 구조화된 채팅과 fail-closed 근거 검사

**Files:** `backend/app/providers/base.py`, `backend/app/providers/groq_client.py`, `backend/app/providers/web_search.py`, 신규 `backend/app/providers/evidence_verifier.py`, `backend/app/services/chat.py`, `backend/app/api/routes.py`, `README.md`.

- [x] 자유형 문자열 답변 대신 `GeneratedAnswer`와 `EvidenceClaim` 구조를 사용한다. 각 주장은 `text`, `source_ids`, `claim_type`을 갖고, 출처 ID는 해당 검색 결과 배열 인덱스만 참조한다.
- [x] 코드가 출처 ID 중복·범위·미사용 출처를 검사하고, 모델이 만든 URL은 무시한다. URL은 Tavily 검색 결과에 실제 존재하는 항목만 반환한다.
- [x] 날짜·접수일·응시료·응시자격 등의 주장은 인용된 검색 snippet과 함께 별도 `EvidenceVerifier`에 보낸다. 허용 결과는 검증 통과/불확실/불통과의 enum으로 제한한다.
- [x] 핵심 사실은 자격증 주관기관 도메인의 근거와 verifier 승인 모두 필요하다. JSON 파싱 실패, timeout, verifier 호출 오류 시 해당 사실을 답변에서 제거하고 `미확인` notice를 추가한다.
- [x] 검색 결과 및 사용자 메시지를 프롬프트 지시와 분리해 신뢰하지 않는 데이터로 취급한다. 뉴스·블로그 근거는 공식 근거라고 표시하지 않는다.
- [x] 채팅 `sources`는 답변에서 실제 사용된 출처 ID만 저장한다. 검색 결과가 0건일 때만 regex 검사하는 현행 경로는 제거한다.
- [x] 변경을 `security: validate cited facts before returning chat answers` 메시지로 커밋한다.

**Interfaces:** `GeneratedAnswer(claims: list[EvidenceClaim], general_advice: str | None)`; `EvidenceVerifier.verify(claim: EvidenceClaim, sources: list[SearchHit]) -> VerificationResult`; `ChatService.reply(db: Session, session_id: int, message: str) -> ChatResult`. 사용자 API의 `ChatReplyResponse`에는 검증 후 답변과 사용된 `sources`, `notices`만 포함한다.

**Verification:** `uv run python -m compileall -q app`, `uvx ruff check --ignore B008`를 변경한 백엔드 경로에 실행하고, `npm run lint`, `npm run build`, `git diff --check`를 확인한다. 생성 답변의 source ID 중복·범위 검사, 미사용 출처 제거, 공식 도메인 판정, 파싱·timeout·verifier 실패 시 제거 경로를 함수 경계에서 정적으로 검토한다. 전체 테스트는 상위 지침에 따라 추가·실행하지 않는다.

## Task 5: Google Calendar 연동을 현재 백엔드 경계에 이식

**Files:** `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/core/config.py`, `backend/app/api/routes.py`, 신규 `backend/app/services/calendar.py`, 신규 `backend/app/providers/google_calendar.py`, 신규 migration, 신규 `app/api/google/callback/route.ts`, `.env.example`.

- [ ] `origin/feat/google-calendar`는 병합하지 않는다. 현재 `backend/app`과 Groq/Tavily·근거 검증 코드를 유지하면서 OAuth·Calendar 동작 중 필요한 부분만 옮긴다.
- [ ] 연결 시작 endpoint는 고정 redirect URI를 사용한 Google authorization URL을 반환하고, 난수 `state`의 해시·세션 ID·만료 시각을 DB에 저장한다. 외부 callback은 same-origin Next.js `/api/google/callback`에서 받아 BFF 비밀값과 세션 쿠키를 붙여 백엔드에 전달한다.
- [ ] OAuth callback은 state를 한 번만 소비하고, state에 묶인 세션과 요청 Bearer 토큰의 소유권을 확인한다. redirect URI·최소 scope를 고정한다. refresh token은 키 버전이 있는 AEAD 방식으로 암호화해 DB에 저장하고, 암호화 키는 서버 환경변수로만 둔다.
- [ ] 연결 해제 시 DB token을 삭제하고 Google revoke를 요청한다. revoke 실패와 token 만료는 안전한 상태로 사용자에게 표시한다.
- [ ] 공식 출처가 확인된 일정만 Google Calendar에 생성/갱신한다. mock/미확인 일정은 동기화하지 않는다. 반복 동기화는 저장된 Google event ID를 기준으로 기존 일정을 갱신해 중복 생성을 막는다.
- [ ] 변경을 `feat: secure Google Calendar session integration` 메시지로 커밋한다.

**Interfaces:** `POST /api/v1/coaching/sessions/{session_id}/calendar/connect`는 authorization URL을 반환한다. `POST /api/v1/calendar/callback`은 `code`와 `state`를 받고 BFF secret을 요구한다. state 해시로 연결된 session ID를 찾은 뒤 해당 ID와 Bearer 토큰의 소유권을 검증하고 state를 원자적으로 한 번만 소비한다. `DELETE /api/v1/coaching/sessions/{session_id}/calendar`는 연결을 끊는다. OAuth callback URI는 Vercel 프런트 프로젝트의 `/api/google/callback` 한 곳으로 고정한다.

**Verification:** `npm run lint`, `npm run build`, `python -m compileall -q backend/app`, `ruff check backend`, `git diff --check`. branch에서 이식한 코드가 루트 `app/`로 백엔드를 옮기거나 현재 LLM/provider 파일을 삭제하지 않았는지 `git diff`로 확인한다.

## Task 6: 배포 의존성·Vercel 환경변수 문서 준비

**Files:** `package.json`, `package-lock.json`, `backend/pyproject.toml`, `backend/uv.lock`, `.env.example`, 신규 `docs/deployment/vercel.md`, `README.md`.

- [ ] `shadcn` CLI를 개발 의존성으로 이동하고 lockfile을 갱신한다. `npm audit`의 기존 취약점은 영향 경로를 검토하고, major 버전 강제 업그레이드 없이 해결 가능한 것만 수정한다.
- [ ] Python 3.12 런타임 pin과 `uv.lock`을 반영한다. Vercel 백엔드 프로젝트의 root directory를 `/backend`로 두고 `backend/pyproject.toml`에 `[tool.vercel] entrypoint = "app.main:app"`을 설정한다.
- [ ] Vercel 프로젝트별 환경변수 표를 작성한다.
  - 루트 Next.js 프로젝트: `BACKEND_API_URL`, `BFF_SHARED_SECRET`, 허용 origin 및 프런트 전용 설정
  - `/backend` FastAPI 프로젝트: `DATABASE_URL`, `BFF_SHARED_SECRET`, `APP_ENV`, `CORS_ORIGINS`, DB pool 설정, `GROQ_API_KEY`, `GROQ_MODEL`, `TAVILY_API_KEY`, Google OAuth·암호화 설정
- [ ] Groq와 Tavily 키 추가 절차를 `/backend` 프로젝트 기준으로 적는다. Dashboard의 **Settings → Environment Variables**에서 우선 **Preview**만 선택해 등록하고, 값 공개가 제한된 Sensitive 옵션을 사용한다. `NEXT_PUBLIC_` 변수로 만들지 않는다. Preview에서 채팅 및 검색이 동작하고 릴리스 승인을 받은 후 Production에 별도 등록한다.
- [ ] Preview/Production의 DB URL은 서로 다른 데이터베이스로 설정한다. 앱은 provider의 pooled URL, DBeaver는 direct URL을 사용하고 두 값을 구분해 기록한다.
- [ ] 변경을 `docs: document Vercel monorepo deployment settings` 메시지로 커밋한다.

**Interfaces:** 현재 `backend/app/core/config.py`가 읽는 `GROQ_API_KEY`와 `TAVILY_API_KEY` 이름을 유지한다. Next.js 클라이언트 bundle에는 이 두 설정이 전혀 참조되지 않는다. Vercel 변수 변경 후 새 배포를 생성해야 적용된다.

**Verification:** `npm run lint`, `npm run build`, `python -m compileall -q backend/app`, `git diff --check`, `npm audit --omit=dev --audit-level=high` 결과를 검토한다. 의존성 취약점 해결이 강제 major 변경을 요구하면 변경하지 않고 남은 위험과 경로를 문서화한다.

## Task 7: 프리뷰 배포 구성 및 운영 준비 점검

**Files:** Vercel 프로젝트 대시보드 설정, `backend/pyproject.toml`, `docs/deployment/vercel.md`.

- [ ] Vercel에서 같은 Git 저장소를 가리키는 두 프로젝트를 연결한다. 첫 프로젝트 root는 `/`, 두 번째 root는 `/backend`로 둔다. Python Runtime 베타의 빌드·요청 한도와 로그를 프리뷰에서 확인한다.
- [ ] 별도 Preview PostgreSQL에 migration을 명시적으로 적용한다. 서버 환경변수를 지정한 뒤 프런트와 백엔드 Preview를 배포한다.
- [ ] `/health`, 프록시 경유 세션 생성, 쿠키 설정, 타 세션 ID 거부, 프로필 수정, 추천 갱신, 채팅 출처·검증, mock 일정 비노출, Calendar 연결·해제, 세션 삭제, DB 연결을 프리뷰에서 확인한다.
- [ ] `GROQ_API_KEY`와 `TAVILY_API_KEY`는 이 단계에서 `/backend` 프로젝트의 Preview 환경으로 등록한다. 프리뷰가 확인되기 전까지 Production 변수/배포에는 넣지 않는다.
- [ ] 프로덕션 DB 공급자·직접/풀링 접속 정보, Google OAuth callback 등록, Vercel Production 환경변수 입력 권한, 세션 만료·보존 정책이 확정된 뒤 사용자에게 운영 배포 준비 상태를 요약한다. 이전 Vercel 배포로 되돌리는 절차도 문서에 적는다.
- [ ] 변경을 `deploy: prepare isolated Vercel preview projects` 메시지로 커밋한다.

**Interfaces:** Next.js 서버는 `BACKEND_API_URL` 및 `BFF_SHARED_SECRET`으로 FastAPI를 호출한다. 백엔드는 `DATABASE_URL`과 Groq/Tavily/Google 비밀값을 서버 런타임에서만 읽는다. `/health` 응답에는 비밀값이나 DB URL을 넣지 않는다.

**Verification:** `npm run lint`, `npm run build`, `python -m compileall -q backend/app`, `ruff check backend`, `git diff --check`. 배포 후 위 프리뷰 흐름을 확인하되, 실제 Production 승격은 프리뷰 결과와 외부 DB 설정이 준비된 뒤 별도로 진행한다.

## Self-Review Checklist

- [x] 승인된 스펙의 세션 보안, LLM 근거 검사, 실제 API 대시보드, Google Calendar, Vercel/DB 수명주기 요구사항이 모두 Task에 매핑됐다.
- [x] API 키 입력 위치와 시점은 Task 6·7 및 Global Constraints에서 `/backend` + Preview 우선으로 일치한다.
- [x] Calendar callback 경로가 `/api` 쿠키 경로와 same-origin BFF를 사용하고 OAuth `state`를 일회성·세션 소유권과 함께 검증한다.
- [x] `DATABASE_URL`, `GROQ_API_KEY`, `TAVILY_API_KEY`, `BACKEND_API_URL`, `BFF_SHARED_SECRET` 이름이 스펙·코드·환경변수 표에서 일치한다.
- [x] 각 task는 파일 범위, 인터페이스, 구체적 비테스트 검증, 단일 커밋 메시지를 가진다.
- [x] 배포 공급자 선택, 비밀값 입력, 프로덕션 승격 등 코드만으로 결정할 수 없는 항목은 배포 게이트로 남아 있다.
