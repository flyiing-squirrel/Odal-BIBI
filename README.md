# 자격증 패스 코치 백엔드

희망직무, 전공 관련 경험, 보유 자격증, 목표 취득 시기를 입력받아 자격증 추천 결과·대화 내용·공식 자격증 일정을 대시보드에서 소비할 수 있는 형태로 제공하는 FastAPI 백엔드입니다.

LLM(Groq)과 웹 검색(Tavily)은 교체 가능한 provider 뒤에 분리되어 있습니다. API key가 비어 있으면 결정론적인 mock 추천으로 동작하므로 key 없이도 로컬 개발이 가능합니다. 공식 일정은 아직 mock adapter입니다.

## 주요 기능

- FastAPI REST API와 자동 OpenAPI 문서 (`/docs`)
- Pydantic 입력/응답 스키마
- 서비스 계층과 provider 계층 분리
- PostgreSQL 기반 세션·추천·대화·일정 저장 (Docker Compose)
- Groq LLM 추천 + 세션 대화 이어가기 (요청 파악 → 웹 검색 → 근거 기반 응답)
- 추천 자격증 목록 및 항목별 상세 조회
- 대화 목록 및 메시지별 상세 조회
- 공식 일정 목록 및 일정별 상세 조회
- 공식 사이트 연동용 `OfficialScheduleAdapter` 구조와 예시 mock adapter
- 프론트엔드에서 바로 쓸 수 있는 통합 대시보드 응답

## 실행 방법

```bash
cp .env.example .env    # GROQ_API_KEY, TAVILY_API_KEY 채우기 (비워둬도 실행됨)
docker compose up --build
```

DB만 Docker로 띄우고 API는 로컬에서 자동 재시작으로 개발할 수도 있습니다. Python 3.11 이상을 권장합니다.

```bash
docker compose up -d db
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

실행 후 다음 주소를 확인할 수 있습니다.

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

PostgreSQL은 `localhost:5432`(계정 `odal`/`odal`, DB `odal`)로 열리며 데이터는 `pgdata` 볼륨에 유지됩니다. 테이블은 앱 시작 시 `create_all`로 생성되므로, 모델 컬럼이 바뀌면 `docker compose down -v`로 볼륨을 지우고 다시 띄워야 합니다.

## API 키 관리

| 파일 | git | 내용 |
| --- | --- | --- |
| `.env.example` | 커밋함 | 키 **이름**만 있는 템플릿 (값은 `""`) |
| `.env` | 커밋 안 함 (`.gitignore`) | 실제 키 **값**, 각자 PC에만 둠 |

- Groq·Tavily 키는 각자 발급받아 자신의 `.env`에 넣습니다. 공용 키가 필요하면 비밀번호 관리자(1Password, Bitwarden 등) 공유 금고로 전달하고 채팅에 붙여넣지 않습니다.
- 새 환경변수가 생기면 `.env.example`에 이름만 추가합니다.
- 배포 시에는 배포 서비스의 환경변수 설정이나 GitHub Secrets를 사용합니다. `.env`는 `.dockerignore`로 이미지에서도 제외됩니다.
- 키가 커밋·push 되었다면 커밋 삭제만으로는 부족합니다. 즉시 해당 콘솔에서 키를 폐기하고 재발급합니다.

## API 흐름

### 1. 코칭 세션 생성

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

응답은 대시보드 첫 화면에 필요한 데이터를 한 번에 포함합니다. 각 항목에 있는 `id`를 사용해 상세 화면을 요청할 수 있습니다.

### 2. 대시보드 재조회

`GET /api/v1/coaching/sessions/{session_id}`

### 3. 카드 클릭용 상세 조회

- 추천 목록: `GET /api/v1/coaching/sessions/{session_id}/recommendations`
- 추천 상세: `GET /api/v1/coaching/sessions/{session_id}/recommendations/{recommendation_id}`
- 대화 목록: `GET /api/v1/coaching/sessions/{session_id}/conversation`
- 대화 상세: `GET /api/v1/coaching/sessions/{session_id}/conversation/{message_id}`
- 일정 목록: `GET /api/v1/coaching/sessions/{session_id}/schedules`
- 일정 상세: `GET /api/v1/coaching/sessions/{session_id}/schedules/{schedule_id}`

모든 상세 API는 부모 `session_id`도 함께 검증하므로 다른 세션의 데이터가 섞이지 않습니다.

### 4. 대화 이어가기

`POST /api/v1/coaching/sessions/{session_id}/messages`

```json
{ "message": "1순위 자격증 다음 시험 언제야?" }
```

1. **요청 파악**: Groq가 의도(`recommend`·`schedule`·`study_path`·`general`)와 검색어를 JSON으로 추출합니다. 세션 프로필과 추천 결과를 함께 넘기므로 "1순위" 같은 지시어도 해석합니다.
2. **검색**: Tavily로 검색합니다. 일정 문의는 공식 기관 도메인(q-net, dataq 등)을 먼저 검색하고, 결과가 없으면 일반 검색으로 넘어갑니다.
3. **응답**: 검색 결과에 있는 사실만 `[1]` 형태로 출처를 붙여 답하고, 확인되지 않은 일정·비용은 "미확인"으로 표시합니다.

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
| 404 | 세션 없음 |
| 422 | 빈 메시지 등 요청 형식 오류 |
| 502 | Groq 호출 실패 |
| 503 | `GROQ_API_KEY` 미설정 |

`sources`는 대화 목록·상세 API의 메시지에도 포함됩니다. `notices`는 검색 미설정·검색 실패 등 처리 상태입니다.

## LLM·검색 연결 구조

| 파일 | 역할 |
| --- | --- |
| `app/providers/groq_client.py` | Groq 호출 래퍼 (API key는 여기에만) |
| `app/providers/groq_llm.py` | `LLMProvider` 구현. 카탈로그 코드만 허용하고, Groq 실패 시 mock 추천으로 대체하며 요약에 실패 사실을 표시 |
| `app/providers/web_search.py` | Tavily `SearchProvider` 구현, 공식 기관 도메인 목록 |
| `app/services/chat.py` | 대화 이어가기 (요청 파악 → 검색 → 응답, 메시지 저장) |
| `app/api/routes.py` | `.env`의 key 유무에 따라 Groq/mock, Tavily/검색 없음 선택 |

모델은 `.env`의 `GROQ_MODEL`로 바꿀 수 있습니다.

## 실제 공식 일정 연결 위치

`app/providers/official_schedule.py`의 `OfficialScheduleAdapter`를 구현하세요.

1. 공식 사이트 API 또는 허용된 공개 페이지를 조회합니다.
2. 페이지별 날짜 형식을 `ScheduleRecord`로 정규화합니다.
3. `source_name`, `source_url`을 원문 기준으로 기록합니다.
4. 필요하면 캐시·재시도·rate limit을 adapter 내부에 추가합니다.
5. `OfficialSiteScheduleProvider(YourOfficialAdapter())`로 교체합니다.

기관별 사이트 구조가 달라 공통 provider에는 크롤링 코드를 넣지 않았습니다. 현재 mock 일정도 실제 연동과 동일한 응답 형태를 사용합니다.

## 데이터 구조

- `certifications`: 자격증 master/catalog
- `coaching_sessions`: 사용자 입력과 생성 시각
- `certification_recommendations`: 세션별 추천 결과와 매칭 점수
- `conversation_messages`: 사용자 입력과 LLM 대화, assistant 답변의 출처(`sources`)
- `certification_schedules`: 추천 자격증별 시험·접수·합격 발표 일정과 원문 링크

## 테스트

```bash
pytest
```

## 다음 단계 제안

운영 환경에서는 사용자 인증 및 세션 소유권, 일정 캐시/만료 정책, provider 호출 실패 상태(`pending`, `failed`), 비동기 작업 큐, 실제 자격증 master data 관리 기능을 추가하면 됩니다.

