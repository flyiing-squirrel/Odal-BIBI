# Odal BIBI

자격증 준비를 위한 대시보드 UI와 FastAPI 백엔드를 담은 저장소입니다. 현재 웹 UI 시안은 추천, 일정, 프로필, 채팅 네 영역만 제공합니다.

## 대시보드 UI

Next.js, Tailwind CSS, shadcn/ui 컴포넌트로 구현했습니다. NomadKit 디자인의 색상 토큰을 적용했습니다.

```bash
npm install
npm run dev
```

- 추천 카드와 비교 후보는 화면 예시 데이터입니다.
- 공식 시험 일정은 UI에서 연결 전 상태로 표시하며 임의의 날짜를 넣지 않습니다.
- 프로필과 채팅 내역은 현재 브라우저의 `localStorage`에 저장됩니다.
- 채팅은 시연용 응답을 사용하며, 현재 UI는 외부 AI/API를 호출하지 않습니다.

## 폴더 구조

```
Odal-BIBI/
├─ app/, components/, lib/, package.json ...   대시보드 UI (Next.js)
├─ backend/                                     FastAPI 백엔드
│  ├─ app/        API·서비스·provider
│  ├─ tests/
│  ├─ requirements.txt, requirements-dev.txt, pyproject.toml
│  ├─ vercel.json   Vercel 함수 설정 (Root Directory = backend)
│  └─ Dockerfile    (선택) 컨테이너 실행용
├─ docker-compose.yml                           (선택) db(PostgreSQL) + api
└─ .env.example                                 프론트·백엔드 공용 환경변수 템플릿
```

## FastAPI 백엔드

백엔드 코드는 `backend/`에 있으며, 아래 경로는 모두 `backend/` 기준입니다. `.env`는 저장소 루트에 하나만 둡니다.

희망직무, 전공 관련 경험, 보유 자격증, 목표 취득 시기를 입력받아 자격증 추천 결과·대화 내용·공식 자격증 일정을 대시보드에서 소비할 수 있는 형태로 제공합니다.

LLM(Groq)과 웹 검색(Tavily)은 교체 가능한 provider 뒤에 분리되어 있습니다. API key가 비어 있으면 결정론적인 mock 추천으로 동작하므로 key 없이도 로컬 개발이 가능합니다. 공식 일정은 아직 mock adapter입니다.

### 주요 기능

- FastAPI REST API와 자동 OpenAPI 문서 (`/docs`)
- Pydantic 입력/응답 스키마
- 서비스 계층과 provider 계층 분리
- 세션·추천·대화·일정 저장: 로컬은 SQLite(설정 없이 바로), 배포는 PostgreSQL(Neon)
- 세션별 접근 토큰(`X-Session-Token`)으로 소유자만 조회·대화 가능
- LLM 비용 보호용 요청 제한: 세션당 메시지 수, IP당 세션 생성 수
- Groq LLM 추천 + 세션 대화 이어가기 (요청 파악 → 웹 검색 → 근거 기반 응답)
- 추천 자격증 목록 및 항목별 상세 조회
- 대화 목록 및 메시지별 상세 조회
- 공식 일정 목록 및 일정별 상세 조회
- 공식 사이트 연동용 `OfficialScheduleAdapter` 구조와 예시 mock adapter
- 프론트엔드에서 바로 쓸 수 있는 통합 대시보드 응답

### 백엔드 실행 (Docker 없이)

Python 3.11 이상만 있으면 됩니다. `DATABASE_URL`을 비워 두면 `backend/odal.db`(SQLite)가 자동으로 만들어집니다.

```bash
cp .env.example .env
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

`.env`의 `GROQ_API_KEY`, `TAVILY_API_KEY`는 비워도 실행됩니다. 이 경우 추천은 mock 규칙으로 동작하고 대화 API는 503을 반환합니다.

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

테이블은 앱 시작 시 `create_all`로 생성됩니다. 마이그레이션 도구가 없어 기존 테이블에 컬럼을 추가하지 못하므로, 모델 컬럼이 바뀌면 `backend/odal.db`를 지우고 다시 실행합니다.

#### (선택) Docker Compose로 PostgreSQL과 함께 실행

```bash
docker compose up --build
```

`.env`에 `POSTGRES_PASSWORD`를 직접 정해야 실행됩니다. PostgreSQL은 `127.0.0.1:5432`에서만 열리며 데이터는 `pgdata` 볼륨에 유지됩니다. 모델 컬럼이 바뀌면 `docker compose down -v`로 볼륨을 지우고 다시 띄웁니다.

### Vercel 배포 (백엔드)

FastAPI 앱(`backend/app/main.py`의 `app`)을 Vercel이 자동으로 인식해 하나의 함수로 배포합니다.

1. Vercel에서 **Add New → Project**로 이 GitHub 저장소를 가져옵니다.
2. **Root Directory**를 `backend`로 지정합니다. Framework Preset은 FastAPI로 자동 인식됩니다.
3. 프로젝트의 **Storage → Neon(Postgres)** 을 연결합니다. `DATABASE_URL`이 자동으로 들어갑니다. Vercel에서는 SQLite 파일이 유지되지 않으므로 Postgres가 필요합니다.
4. **Settings → Environment Variables**에 추가합니다.
   - `GROQ_API_KEY`, `TAVILY_API_KEY`
   - `CORS_ORIGINS`: 프론트엔드 도메인 (예: `https://odal-bibi.vercel.app`). 여러 개는 쉼표로 구분
   - `APP_ENV=production`
   - (선택) `RATE_LIMIT_WINDOW_MINUTES`, `MAX_MESSAGES_PER_WINDOW`, `MAX_SESSIONS_PER_WINDOW`
5. Deploy 후 `https://<배포 주소>/health`가 `{"status":"ok"}`를 반환하는지, `/docs`가 열리는지 확인합니다.

대화 요청은 LLM·검색을 여러 번 호출하므로 `vercel.json`에서 함수 최대 실행 시간을 60초로 늘려 두었습니다. 테이블은 첫 요청 시(lifespan) 자동 생성됩니다.

### API 키 관리

| 파일 | git | 내용 |
| --- | --- | --- |
| `.env.example` | 커밋함 | 키 **이름**만 있는 템플릿 (값은 `""`) |
| `.env` | 커밋 안 함 (`.gitignore`) | 실제 키 **값**, 각자 PC에만 둠 |

- Groq·Tavily 키는 각자 발급받아 자신의 `.env`에 넣습니다. 공용 키가 필요하면 비밀번호 관리자(1Password, Bitwarden 등) 공유 금고로 전달하고 채팅에 붙여넣지 않습니다.
- 새 환경변수가 생기면 `.env.example`에 이름만 추가합니다.
- 배포 시에는 Vercel 프로젝트의 Environment Variables를 사용합니다. `.env`는 저장소 루트에 있어 `backend/`만 올라가는 Vercel·Docker 빌드에 포함되지 않습니다.
- 키가 커밋·push 되었다면 커밋 삭제만으로는 부족합니다. 즉시 해당 콘솔에서 키를 폐기하고 재발급합니다.

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

응답의 `access_token`은 **이 응답에서만 한 번** 내려옵니다. 프론트엔드는 이를 저장해 두고, 이후 `/coaching/sessions/{session_id}/...` 요청마다 헤더로 보내야 합니다. 서버에는 토큰의 해시만 저장됩니다.

```
X-Session-Token: <access_token>
```

토큰이 없으면 401, 틀리거나 다른 세션의 토큰이면 404를 반환합니다. 같은 IP에서 짧은 시간에 세션을 너무 많이 만들면 429를 반환합니다.

#### 2. 대시보드 재조회

`GET /api/v1/coaching/sessions/{session_id}`

#### 3. 카드 클릭용 상세 조회

- 추천 목록: `GET /api/v1/coaching/sessions/{session_id}/recommendations`
- 추천 상세: `GET /api/v1/coaching/sessions/{session_id}/recommendations/{recommendation_id}`
- 대화 목록: `GET /api/v1/coaching/sessions/{session_id}/conversation`
- 대화 상세: `GET /api/v1/coaching/sessions/{session_id}/conversation/{message_id}`
- 일정 목록: `GET /api/v1/coaching/sessions/{session_id}/schedules`
- 일정 상세: `GET /api/v1/coaching/sessions/{session_id}/schedules/{schedule_id}`

모든 상세 API는 세션 토큰과 부모 `session_id`를 함께 검증하므로 다른 세션의 데이터에 접근할 수 없습니다.

#### 4. 대화 이어가기

`POST /api/v1/coaching/sessions/{session_id}/messages`

```json
{ "message": "1순위 자격증 다음 시험 언제야?" }
```

1. **요청 파악**: Groq가 의도(`recommend`·`schedule`·`study_path`·`general`)와 검색어를 JSON으로 추출합니다. 세션 프로필과 추천 결과를 함께 넘기므로 "1순위" 같은 지시어도 해석합니다.
2. **검색**: Tavily로 검색합니다. 일정 문의는 공식 기관 도메인(q-net, dataq 등)을 먼저 검색하고, 결과가 없으면 일반 검색으로 넘어갑니다.
3. **응답**: 검색 결과에 있는 사실만 `[1]` 형태로 출처를 붙여 답하고, 확인되지 않은 일정·비용은 "미확인"으로 표시합니다.
4. **근거 검사**: 금액·날짜·URL이 들어간 줄에 유효한 출처 번호(`[1]`~`[검색 결과 수]`)가 없거나 범위를 벗어난 번호가 있으면 한 번 다시 쓰게 하고, 그래도 남으면 해당 줄을 지웁니다. 검색 결과가 없으면 이런 표현 자체를 허용하지 않습니다. 출처 번호가 가리키는 검색 결과에 그 사실이 실제로 있는지까지는 확인하지 않습니다.

응답 예시:

```json
{
  "session_id": 1,
  "intent": "schedule",
  "user_message": { "id": 3, "role": "user", "content": "...", "sources": [], "created_at": "..." },
  "assistant_message": {
    "id": 4, "role": "assistant", "content": "... [1]",
    "sources": [{ "title": "큐넷 시험일정", "url": "https://www.q-net.or.kr/..." }],
    "created_at": "..."
  },
  "notices": ["공식 사이트에서 결과를 찾지 못해 일반 검색 결과를 참고했어요."]
}
```

| 상태 코드 | 의미 |
| --- | --- |
| 401 | `X-Session-Token` 헤더 없음 |
| 404 | 세션 없음 또는 토큰 불일치 |
| 422 | 빈 메시지 등 요청 형식 오류 |
| 429 | 요청 제한 초과 (기본: 10분에 세션당 메시지 20회) |
| 502 | Groq 호출 실패 |
| 503 | `GROQ_API_KEY` 미설정 |

`sources`는 대화 목록·상세 API의 메시지에도 포함됩니다. `notices`는 검색 미설정·검색 실패 등 처리 상태입니다.

### LLM·검색 연결 구조

| 파일 | 역할 |
| --- | --- |
| `app/providers/groq_client.py` | Groq 호출 래퍼 (API key는 여기에만) |
| `app/providers/groq_llm.py` | `LLMProvider` 구현. 카탈로그 코드만 허용하고, Groq 실패 시 mock 추천으로 대체하며 요약에 실패 사실을 표시 |
| `app/providers/web_search.py` | Tavily `SearchProvider` 구현, 공식 기관 도메인 목록 |
| `app/services/chat.py` | 대화 이어가기 (요청 파악 → 검색 → 응답, 메시지 저장) |
| `app/api/routes.py` | `.env`의 key 유무에 따라 Groq/mock, Tavily/검색 없음 선택 |

모델은 `.env`의 `GROQ_MODEL`로 바꿀 수 있습니다.

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
- `conversation_messages`: 사용자 입력과 LLM 대화, assistant 답변의 출처(`sources`)
- `certification_schedules`: 추천 자격증별 시험·접수·합격 발표 일정과 원문 링크

### 테스트

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

### 다음 단계 제안

운영 환경에서는 계정 기반 로그인(현재는 세션 토큰 방식), DB 마이그레이션(Alembic), 일정 캐시/만료 정책, provider 호출 실패 상태(`pending`, `failed`), 비동기 작업 큐, 실제 자격증 master data 관리를 추가할 수 있습니다.
