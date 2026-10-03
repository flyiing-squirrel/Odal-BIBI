# Odal BIBI

자격증 준비를 위한 대시보드 UI와 FastAPI 백엔드를 담은 저장소입니다. 웹 화면은 추천, 일정, 프로필, 채팅 네 영역을 제공합니다.

## 대시보드 UI

Next.js, Tailwind CSS, shadcn/ui 컴포넌트로 구현했습니다. NomadKit 디자인의 색상 토큰을 적용했습니다.

```bash
npm install
npm run dev
```

- 추천 카드와 비교 후보는 화면 예시 데이터입니다.
- 공식 시험 일정은 공식 출처 확인 전까지 UI와 Google Calendar에 기록하지 않습니다.
- 프로필과 채팅 내역은 현재 브라우저의 `localStorage`에 저장됩니다.
- 추천과 채팅은 시연용 응답을 사용합니다. Google Calendar 연결은 FastAPI 백엔드와 연동됩니다.

## FastAPI 백엔드

희망직무, 전공 관련 경험, 보유 자격증, 목표 취득 시기를 입력받아 자격증 추천 결과·대화 내용·공식 자격증 일정을 대시보드에서 소비할 수 있는 형태로 제공합니다.

현재 LLM과 공식 사이트 연동은 교체 가능한 provider/adapter 뒤에 분리되어 있으며, 로컬 실행을 위해 결정론적인 mock 구현이 기본으로 연결되어 있습니다.

### 주요 기능

- FastAPI REST API와 자동 OpenAPI 문서 (`/docs`)
- Pydantic 입력/응답 스키마
- 서비스 계층과 provider 계층 분리
- SQLite 기반 세션·추천·대화·일정 저장
- 추천 자격증 목록 및 항목별 상세 조회
- 대화 목록 및 메시지별 상세 조회
- 공식 일정 목록 및 일정별 상세 조회
- 공식 사이트 연동용 `OfficialScheduleAdapter` 구조와 예시 mock adapter
- 프론트엔드에서 바로 쓸 수 있는 통합 대시보드 응답
- Google OAuth 연결, 사용자별 데이터 소유권, 암호화된 refresh token 저장
- 앱 전용 `Odal BIBI` 캘린더 생성 및 공식 확인 일정의 멱등 추가 API

### 백엔드 실행

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
Copy-Item .env.example .env # Windows PowerShell; macOS/Linux: cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Google Calendar 연결을 켜려면 `.env`에 다음 값을 설정하고, Google Cloud Console에서 Calendar API를 활성화한 웹 OAuth 클라이언트를 만드세요.

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`와 동일한 승인된 redirect URI: `http://localhost:8000/api/v1/calendar/google/callback`
- `SESSION_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`로 생성
- `GOOGLE_TOKEN_ENCRYPTION_KEY`: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`로 생성
- 프론트엔드 `.env.local`의 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`

운영 환경에서는 `SESSION_SECRET`과 Fernet 암호화 키를 비밀 저장소에 보관하고 HTTPS를 사용하세요. Fernet 키를 교체하면 저장된 refresh token을 복호화할 수 없으므로 기존 키를 백업하고 키 회전 절차를 마련해야 합니다. OAuth 테스트 모드와 사용자 승인 대상도 Google Cloud Console에서 확인해야 합니다.

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

SQLite 파일은 실행 위치에 `coach.db`로 생성됩니다. 다른 위치를 쓰려면 `.env`에 `DATABASE_URL`을 설정하면 됩니다.

### API 흐름

#### 1. 코칭 세션 생성

`POST /api/v1/coaching/sessions`

요청 예시:

```json
{
  "desired_job": "백엔드 개발자",
  "major_experience": "학교 프로젝트에서 REST API를 구현했습니다.",
  "owned_certifications": ["컴퓨터활용능력 1급"],
  "target_acquisition_period": "2026년 하반기"
}
```

응답은 대시보드 첫 화면에 필요한 데이터를 한 번에 포함합니다. 각 항목의 `id`로 상세 화면을 요청할 수 있습니다.

#### 2. 대시보드 재조회

`GET /api/v1/coaching/sessions/{session_id}`

#### 3. 카드 클릭용 상세 조회

- 추천 목록: `GET /api/v1/coaching/sessions/{session_id}/recommendations`
- 추천 상세: `GET /api/v1/coaching/sessions/{session_id}/recommendations/{recommendation_id}`
- 대화 목록: `GET /api/v1/coaching/sessions/{session_id}/conversation`
- 대화 상세: `GET /api/v1/coaching/sessions/{session_id}/conversation/{message_id}`
- 일정 목록: `GET /api/v1/coaching/sessions/{session_id}/schedules`
- 일정 상세: `GET /api/v1/coaching/sessions/{session_id}/schedules/{schedule_id}`

모든 상세 API는 부모 `session_id`도 함께 검증하므로 다른 세션의 데이터가 섞이지 않습니다.
데이터 API는 Google 계정으로 연결된 사용자 세션을 요구하며, 새 세션은 해당 사용자에게 소유됩니다. 기존 사용자 소유권이 없는 세션은 자동으로 다른 계정에 할당하지 않습니다.

### Google Calendar 연결

- `GET /api/v1/calendar/google/connect`: Google OAuth 동의 화면으로 이동
- `GET /api/v1/calendar/google/connection`: 연결 상태 확인
- `DELETE /api/v1/calendar/google/connection`: refresh token 폐기 및 앱 내 연결 해제
- `POST /api/v1/calendar/google/schedules/{schedule_id}`: 확인된 시험일을 전용 캘린더에 추가 또는 갱신

앱은 `calendar.app.created` 범위로 자체 보조 캘린더만 생성하고 관리합니다. 개인 캘린더의 일정을 읽지 않습니다. 시험 일정은 저장 구조의 `source_verified`가 참이고 HTTPS 출처가 있을 때만 보낼 수 있습니다. 현재 기본 provider는 mock이므로 이 검증 표시가 꺼져 있고, 실제 날짜를 추가하려면 공식 기관 adapter가 출처를 확인한 뒤 검증 표시를 설정해야 합니다.

### 실제 LLM 연결 위치

`app/providers/base.py`의 `LLMProvider` 계약을 구현한 클래스를 만들고, `app/api/routes.py`의 `MockLLMProvider()`를 해당 구현으로 교체합니다.

LLM 구현은 다음 형태를 반환하면 됩니다.

- `CertificationCandidate.certification_code`: `app/services/coaching.py` 카탈로그의 코드
- `rank`, `match_score`, `priority`, `reason`, `study_plan_hint`
- 사용자에게 보여줄 `assistant_summary`

LLM API key와 호출 코드는 서비스 계층에 넣지 않고 provider 안에만 두는 것을 권장합니다.

### 실제 공식 일정 연결 위치

`app/providers/official_schedule.py`의 `OfficialScheduleAdapter`를 구현하세요.

1. 공식 사이트 API 또는 허용된 공개 페이지를 조회합니다.
2. 페이지별 날짜 형식을 `ScheduleRecord`로 정규화합니다.
3. `source_name`, `source_url`을 원문 기준으로 기록합니다.
4. 필요하면 캐시·재시도·rate limit을 adapter 내부에 추가합니다.
5. `OfficialSiteScheduleProvider(YourOfficialAdapter())`로 교체합니다.

기관별 사이트 구조가 달라 공통 provider에는 크롤링 코드를 넣지 않았습니다. 현재 mock 일정도 실제 연동과 동일한 응답 형태를 사용합니다.

### 데이터 구조

- `certifications`: 자격증 master/catalog
- `coaching_sessions`: 사용자 입력과 생성 시각
- `certification_recommendations`: 세션별 추천 결과와 매칭 점수
- `conversation_messages`: 사용자 입력과 LLM 요약 대화
- `certification_schedules`: 추천 자격증별 시험·접수·합격 발표 일정과 원문 링크
- `users`: Google의 안정적인 계정 식별자와 서비스 사용자
- `google_calendar_connections`: 전용 캘린더 ID와 암호화된 refresh token
- `calendar_event_syncs`: 사용자별 일정과 Google 이벤트의 멱등 매핑

### 테스트

```bash
pytest
```

### 다음 단계 제안

일정 provider의 실제 기관 연동, 전체 대시보드 데이터의 API 전환, OAuth 운영 프로젝트의 검증과 배포 설정은 별도 후속 작업입니다.
