# Odal BIBI

자격증 준비를 위한 대시보드 UI와 FastAPI 백엔드를 담은 저장소입니다. 현재 Vercel Preview는 추천, 일정, 프로필, 채팅 데이터를 각 브라우저의 저장소에 보관하고, FastAPI는 Groq·Tavily 호출과 근거 검증만 수행합니다.

## 대시보드 UI

Next.js, Tailwind CSS, shadcn/ui 컴포넌트로 구현했습니다. NomadKit 디자인의 색상 토큰을 적용했습니다.

```bash
npm install
npm run dev
```

- 프로필 저장 후 API가 반환한 추천·대화 데이터를 표시하고, 전체 대시보드를 버전이 붙은 `localStorage` 레코드로 저장합니다.
- 새로고침 뒤에도 같은 브라우저와 origin에서 데이터를 복원합니다. 사이트 데이터를 지우거나 다른 기기에서 열면 새 대시보드가 시작됩니다.
- Groq·Tavily 키는 Next.js BFF를 거쳐 FastAPI에서만 사용합니다. 브라우저 저장소에는 provider 키나 인증 정보가 들어가지 않습니다.
- 확인된 공식 일정이 없으면 일정 탭에 확인 대기 상태를 표시합니다.
- Google Calendar 동기화는 서버 저장소가 필요한 OAuth 토큰을 보관할 수 없어 Preview에서 비활성화합니다.

Preview 환경변수와 배포 순서는 [Vercel 배포 설정 안내](docs/deployment/vercel.md)를 따릅니다. 이 문서 아래의 PostgreSQL·세션 token·Google Calendar API 설명은 다음 상태 저장형 배포를 위한 기존 API 문서입니다.

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

관심 분야, 주간 학습 시간, 선호 학습 방식, 월 예산을 저장하고 추천·대화·공식 일정 정보를 대시보드에서 소비할 수 있는 형태로 제공합니다. 이전 버전의 세션 입력 필드는 과거 데이터 호환을 위해 nullable로 유지합니다.

LLM(Groq)과 웹 검색(Tavily)은 교체 가능한 provider 뒤에 분리되어 있습니다. API key가 비어 있으면 추천은 결정론적인 기본 provider를 사용할 수 있고, 채팅은 `GROQ_API_KEY`가 없을 때 503을 반환합니다. 공식 일정 provider는 실제로 검증한 자료가 준비될 때까지 빈 목록을 반환합니다. 날짜를 임의로 만들어 저장하지 않습니다.

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
- 비공개 세션 프로필 수정과 추천 재생성
- 세션별 token 소유권 검사와 세션 삭제
- 공식 사이트 연동용 `OfficialScheduleAdapter` 구조와 미설정 상태의 빈 adapter
- 프론트엔드에서 바로 쓸 수 있는 통합 대시보드 응답

### 백엔드 실행 (Docker 없이)

```bash
cp .env.example .env    # BFF_SHARED_SECRET와 보유한 GROQ_API_KEY, TAVILY_API_KEY 설정
docker compose up --build
```

DB만 Docker로 띄우고 API는 로컬에서 자동 재시작으로 개발할 수도 있습니다. 백엔드 실행에는 Python 3.12가 필요합니다.

```bash
cp .env.example .env
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

`.env`의 `GROQ_API_KEY`, `TAVILY_API_KEY`는 비워도 실행됩니다. 이 경우 추천은 mock 규칙으로 동작하고 대화 API는 503을 반환합니다.

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

PostgreSQL은 `localhost:5432`(계정 `odal`/`odal`, DB `odal`)로 열리며 데이터는 `pgdata` 볼륨에 유지됩니다. 스키마와 자격증명 카탈로그는 Alembic migration으로 관리합니다. 모델을 바꿀 때 데이터 볼륨을 지우지 말고 새 migration을 적용하세요. `.env`의 `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_PRE_PING` 값으로 API 프로세스별 연결 풀을 제한할 수 있습니다.

### API 키 관리

| 파일 | git | 내용 |
| --- | --- | --- |
| `.env.example` | 커밋함 | 키 **이름**만 있는 템플릿 (값은 `""`) |
| `.env` | 커밋 안 함 (`.gitignore`) | 실제 키 **값**, 각자 PC에만 둠 |

- Groq·Tavily 키는 자신의 `.env`에만 넣고 프런트엔드 코드나 `NEXT_PUBLIC_` 변수로 노출하지 않습니다. Vercel 배포 시에는 `/backend` 프로젝트의 서버 환경변수로 설정합니다.
- Vercel 프로젝트 분리, Preview 단계 API 키 등록, PostgreSQL 접속 정보 구성은 [Vercel 배포 설정 안내](docs/deployment/vercel.md)를 따릅니다.
- Next.js와 FastAPI는 동일한 `BFF_SHARED_SECRET` 값을 사용해야 합니다. 최소 32바이트의 무작위 값을 사용합니다. 이 값은 두 서버 런타임에서만 보관합니다.
- 새 환경변수가 생기면 `.env.example`에 이름만 추가합니다.
- 배포 시에는 Vercel의 프로젝트 환경변수에 키를 입력합니다. 실제 키는 저장소·GitHub 파일·Next.js 브라우저 코드에 두지 않습니다. `.env`는 루트에 있어 백엔드 Docker 이미지(`backend/` 빌드)에 포함되지 않습니다.
- 키가 커밋·push 되었다면 커밋 삭제만으로는 부족합니다. 즉시 해당 콘솔에서 키를 폐기하고 재발급합니다.

### API 흐름

브라우저는 `/api/backend/...`만 호출합니다. Next.js 프록시는 고정된 `BACKEND_API_URL`로 요청을 보내며 `X-BFF-Secret`과 세션 Bearer token을 서버 간에 전달합니다. 백엔드 직접 호출은 BFF secret이 필요하고, 세션별 읽기·쓰기에는 세션 소유권 token도 필요합니다.

#### 1. 코칭 세션 생성

`POST /api/v1/coaching/sessions`

요청 예시:

```json
{
  "interest_area": "데이터 분석",
  "weekly_study_hours": "주 6시간",
  "learning_style": "문제 풀이 중심",
  "monthly_budget": "월 5만 원 이내"
}
```

응답은 대시보드 첫 화면에 필요한 데이터와 `session_id`를 포함합니다. 백엔드 응답의 원문 `session_token`은 Next.js 프록시가 JSON에서 제거하고 `HttpOnly; SameSite=Lax; Path=/api` 쿠키로 설정합니다.

#### 2. 프로필 수정 및 추천 갱신

`PATCH /api/v1/coaching/sessions/{session_id}/profile`

```json
{ "weekly_study_hours": "주 8시간", "monthly_budget": "무료 자료 우선" }
```

보낸 필드만 변경하고, 업데이트된 프로필·추천·대화·일정 묶음을 반환합니다. 첫 프로필 저장은 세션 생성 API를 사용하고 이후 저장은 이 PATCH API를 사용합니다.

#### 3. 대시보드 재조회

`GET /api/v1/coaching/sessions/{session_id}`

#### 4. 카드 클릭용 상세 조회

- 추천 목록: `GET /api/v1/coaching/sessions/{session_id}/recommendations`
- 추천 상세: `GET /api/v1/coaching/sessions/{session_id}/recommendations/{recommendation_id}`
- 대화 목록: `GET /api/v1/coaching/sessions/{session_id}/conversation`
- 대화 상세: `GET /api/v1/coaching/sessions/{session_id}/conversation/{message_id}`
- 일정 목록: `GET /api/v1/coaching/sessions/{session_id}/schedules`
- 일정 상세: `GET /api/v1/coaching/sessions/{session_id}/schedules/{schedule_id}`
- 세션 삭제: `DELETE /api/v1/coaching/sessions/{session_id}`

모든 상세 API는 세션 토큰과 부모 `session_id`를 함께 검증하므로 다른 세션의 데이터에 접근할 수 없습니다.

#### 5. 대화 이어가기

`POST /api/v1/coaching/sessions/{session_id}/messages`

```json
{ "message": "1순위 자격증 다음 시험 언제야?" }
```

1. **요청 파악**: Groq가 의도(`recommend`·`schedule`·`study_path`·`general`)와 검색어를 JSON으로 추출합니다. 사용자 입력·이전 대화·검색 결과는 지시가 아닌 데이터로 전달합니다.
2. **검색**: Tavily로 검색합니다. 일정 문의는 공식 기관 도메인(q-net, dataq 등)을 먼저 검색하고, 결과가 없으면 일반 검색으로 넘어갑니다.
3. **응답 검증**: Groq는 주장별 출처 ID가 포함된 JSON을 반환합니다. 코드가 중복·범위 밖 인용을 제거하고, 날짜·비용·응시자격 등 핵심 사실은 해당 자격증의 공식 HTTPS 도메인과 별도 근거 검증기의 `supported` 판정이 모두 있어야 표시합니다. 확인 실패·불확실·파싱 오류는 사실 주장과 그 출처를 제외합니다.
4. **저장**: 답변에서 실제 인용한 Tavily 검색 결과만 `[1]` 형식과 `sources`로 저장합니다. 생성 모델이 만든 URL은 사용하지 않습니다.

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

기관별 사이트 구조가 달라 공통 provider에는 크롤링 코드를 넣지 않았습니다. 검증 adapter를 설정하기 전까지 활성 provider는 빈 일정 목록을 반환합니다. `MockOfficialScheduleAdapter`는 예시용이며 실제 앱에는 연결하지 않습니다.

### 데이터 구조

- `certifications`: 자격증 master/catalog
- `coaching_sessions`: 프로필 입력과 생성 시각 (기존 필드는 nullable 호환 필드)
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

추가 운영 작업으로는 계정 간 로그인·기기 동기화, 일정 캐시/만료 정책, provider 호출 실패 상태(`pending`, `failed`), 비동기 작업 큐, 실제 자격증 master data 관리를 고려할 수 있습니다.
