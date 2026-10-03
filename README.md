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

### 백엔드 실행

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

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

### 테스트

```bash
pytest
```

### 다음 단계 제안

운영 환경에서는 사용자 인증 및 세션 소유권, 일정 캐시/만료 정책, provider 호출 실패 상태(`pending`, `failed`), 비동기 작업 큐, 실제 자격증 master data 관리를 추가할 수 있습니다.
