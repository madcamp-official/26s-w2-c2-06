# 스프린트 1 — 기능 4: 맞춤 로드맵 + 평가 지표 생성

> 공통 계약은 `SPRINT1_CONTRACT.md` 참고 (특히 2절 아키텍처 확정, 4~5절 인터페이스 스키마, 7절 병렬 작업 프로토콜). 이 문서는 기능 4 담당자가 계약을 확인하고, 세부 구현 계획을 채워나가는 문서다. 스펙 근거는 `SPEC.md` 4.4.

- 최종 수정일: 2026-07-11
- 상태: 계약 v0.2 반영 (구현 계획 골격 확정, 세부는 담당자가 채움)

---

## 1. 이 기능이 하는 일 (계약 요약)

- **입력**: 목표 정의서 + 3번의 `ResearchContext` + 온보딩의 반복업무·팀원 태깅(4.1) + (2회차 이후) 5번 자산화 저장소 — 코드 경계는 `generate_roadmap()` 함수 하나 (계약 2.3절). 스프린트1에서 자산화 저장소 인자는 `None`
- **하는 일**: Gemini API 호출로 아래를 순서대로 생성·판단. **RAG의 "G"만 담당 — 웹서치하지 않는다**
  1. AI 적합성 판정 (빈도×정형성 매트릭스 + 게이트 → Pivot 카드)
  2. Layer 1/2/3 분류
  3. 목표 → task breakdown (주 단위 타임라인, `week` 필드)
  4. 팀 내 역할 재분배 제안 (경량 스코프 — 팀 내부만, 실행권한 없음)
  5. 평가 지표 설계
- **하지 않는 일**: 웹서치/외부 조사 (3번의 역할), 실제 트래킹·코칭 (5번의 역할)
- **출력**: `RoadmapResult` (계약 5절 스키마) → Frontend + 5번

## 2. 확정 사항 (계약 v0.2에서 결정됨)

- [x] **"ML 서버에서 fine-tuning한 형식" 해석 확정**: 실제 fine-tuning은 스프린트1에서 하지 않는다. 학습 데이터(실행 기록↔정답 로드맵 쌍)가 4.5 자산화 저장소에 쌓이기 전이므로 시기상조. 대신 아래 2단계 구조로 설계해 Stage B를 **fine-tuned 모델 교체 슬롯**으로 남긴다 — 교체하더라도 3↔4 계약은 불변 (계약 2.2절)
- [x] foundation 모델: **Gemini API** + structured output(responseSchema로 JSON 스키마 강제), 두 단계 모두
- [x] 내부 2단계 파이프라인:
  - **Stage A — 판정·초안 생성**: 목표 정의서 + `ResearchContext` + 온보딩 데이터 → AI 적합성 판정(매트릭스+게이트, Pivot 카드) + 실행 전략 초안 (`DraftPlan`, 아래 3절)
  - **Stage B — 구조 변환**: `DraftPlan` → `RoadmapResult` (task 필드 상세화, 역할 재분배 카드, 평가 지표 산출)
- [x] `ResearchContext.status`가 `partial`/`failed`여도 동작: 로드맵은 생성하되 `source_refs` 없이, `research_status`로 신뢰도 전달 (계약 4절 실패 계약)
- [x] 통합 형태: 같은 repo `roadmap/` 패키지
- [x] 픽스처 검수 책임: `fixtures/research_context_goal_001.json` 검수는 4번 담당자 (계약 7절) — 3번 완성을 기다리지 않고 이 픽스처로 개발 시작

## 3. 내부 인터페이스 — DraftPlan (기능 4 내부 전용, 계약 아님)

Stage A → Stage B 사이의 스키마. **기능 4 담당자가 단독으로 변경 가능** (3번 담당자 합의 불필요 — 계약 대상은 바깥 입출력뿐). 초안:

```json
{
  "goal_id": "goal_001",
  "fitness_judgments": [ "…RoadmapResult.fitness_assessment와 동일 구조…" ],
  "strategy_draft": "적합 판정된 업무들에 대한 서술형 실행 전략. 근거는 [F1] 형태로 finding_id 인용",
  "task_outline": [
    { "title": "string", "layer": 2, "week": 1, "approach": "string", "source_refs": ["F1"] }
  ],
  "metric_ideas": ["string"],
  "reassignment_notes": ["string"]
}
```

- Stage A가 판정과 Layer·주차 배치까지 결정하고, Stage B는 구조·필드 완성(난이도/소요시간/실패요인/지표 baseline·target)을 담당하는 것을 1차 기준으로 한다. 경계 조정은 담당자 재량, 조정 시 이 절 갱신
- fine-tuned 모델로 Stage B를 교체할 때의 학습 입출력 쌍이 곧 (`DraftPlan`, `RoadmapResult`)가 되므로, 이 스키마를 안정적으로 유지할수록 나중 fine-tuning 데이터 수집이 쉬워진다

## 4. 담당자 확인·결정 사항 (남은 체크리스트)

- [x] `RoadmapResult` 스키마 최종 검토 — 계약 문서 스키마 그대로 `app/contracts/roadmap.py`에 코드화. 변경 없음
- [x] AI 적합성 판정 매트릭스의 구체 임계값 — **"자주" = 주 1회 이상 수행, "가끔" = 그보다 드묾**(`app/roadmap/prompts.py`의 `_FITNESS_MATRIX_BLOCK`에 명시해 Stage A 프롬프트에 포함). 정형성은 `OnboardingData.RepetitiveTask.is_standardized` 불리언 값을 그대로 사용
- [~] task granularity 기준 — "이번 주 바로 시도 가능한 수준"이라는 정성적 지시만 프롬프트에 포함(`week` 필드로 주 단위 배치). 정량 기준(예: 최대 소요시간)은 아직 미정 — 실사용 피드백 나오면 재조정
- [ ] 평가 지표 산식 (시간 단축 측정 방법) — 아직 고정 공식 없음. 현재는 Stage B가 baseline/target을 텍스트로 생성(LLM 판단에 위임). 4.5 자산화 저장소에 실행 기록이 쌓이기 전까지는 확정 어려움 — 오픈 이슈로 유지
- [x] `ResearchContext.findings` 프롬프트 주입 방식 — **전체 삽입**으로 결정 (findings 3~8건이라 토큰 부담 적음). `app/roadmap/prompts.py`의 `build_stage_a_prompt`에서 전체 findings를 순회해 인용 가능하도록 주입
- [x] Stage A/B 프롬프트 설계, structured output 스키마 정의 — `app/roadmap/prompts.py`(프롬프트) + `app/roadmap/draft_plan.py`(`DraftPlan`, Stage A↔B 내부 스키마) + `app/contracts/roadmap.py`(`RoadmapResult`, Stage B 출력). Gemini 호출은 `google-genai` SDK의 `client.models.generate_content(config=GenerateContentConfig(response_mime_type="application/json", response_schema=<pydantic model>))` 패턴 사용 (`app/roadmap/gemini_client.py`)
- [x] SPEC.md 2.1(쉬운 언어)·2.2(Layer 원칙 문구)·4.4 고정 disclaimer 보장 위치 — **쉬운 언어·Layer 원칙은 프롬프트 텍스트**(`_POLICY_BLOCK`)로 지시하고, **disclaimer 고정 문구는 LLM 출력에 의존하지 않고 `app/roadmap/stage_b.py`의 후처리 코드에서 강제 덮어쓰기**로 100% 보장 (LLM이 문구를 틀리거나 누락해도 항상 정확한 문구가 나가도록). 같은 이유로 `goal_id`/`research_status`도 코드에서 강제

## 5. 구현 계획 (골격 — 담당자가 세부 채움)

1. [x] **픽스처 기반 개발 착수**: `app/fixtures/goal_001.json`(계약 1절 예시 그대로) + `app/fixtures/research_context_goal_001.json`(계약 4절 예시를 goal_001 시나리오로 구체화, findings 3건) 작성. **주의**: 원래 계약 7절은 이 픽스처의 "작성"을 3번(리서치) 담당자 몫으로 정했는데, 3번 담당자가 아직 착수 전이라 4번 개발을 막지 않기 위해 임시로 초안을 만들었다 — **3번 담당자 확정되면 검수/교체 필요**. `onboarding_001.json`도 같은 이유로 임시 작성(1번 담당자 미정)
2. [x] **Stage A**: `app/roadmap/stage_a.py::run_stage_a()` — 적합성 판정+전략 초안+task outline을 `DraftPlan`으로 생성 (structured output). `goal_id`는 LLM 출력과 무관하게 코드에서 강제
3. [x] **Stage B**: `app/roadmap/stage_b.py::run_stage_b()` — `DraftPlan` → `RoadmapResult` 변환. disclaimer·`goal_id`·`research_status` 후처리, `fitness_assessment` 비어있으면 Stage A 결과로 폴백
4. [x] **검증**: `tests/test_contracts.py`(스키마+픽스처 검증, `failed` 상태 경로 포함), `tests/test_roadmap_stage_a.py`/`test_roadmap_stage_b.py`/`test_roadmap_service.py`/`test_roadmap_router.py` — Gemini는 가짜 클라이언트(`tests/conftest.py::FakeClient`)로 대체해 네트워크 없이 오케스트레이션 검증. `source_refs`가 실제 `finding_id`인지 검사하는 테스트는 아직 없음 — 오픈 이슈로 남김
5. [ ] **통합**: 실제 `run_research()` 출력으로 교체해 DoD 확인 (계약 7절 4항) — 3번 담당자 구현 대기 중. 지금은 임시 픽스처로만 검증했고, **실제 Gemini API 호출 자체도 아직 라이브로 검증 못함**(API 키 대기 중, 6절 참고)

## 6. 오픈 이슈 (SPEC.md 4.4에서 이관)

- 지표 산식 (시간 단축 측정 방법) — 미확정, 4.5 실행 기록 축적 후 재검토
- task granularity 정량 기준 — 정성적 지시만 적용, 정량화는 추후
- 3번 담당자의 실제 `research_context_goal_001.json`으로 교체 후 통합 테스트 (DoD)
- `source_refs`가 실제 존재하는 `finding_id`를 참조하는지 검증하는 테스트 추가
- Notion 페이지 발행이 새 시도인지 기존 로드맵 페이지 갱신인지 정책 미정 (지금은 매번 새 페이지 생성)

## 8. 사용자 노출 톤 + Notion 발행 (SPRINT1_CONTRACT.md 5절 "Frontend — 쉬운 언어로 표시" 담당)

계약 문서 5절은 이 정책(SPEC.md 2.1 쉬운 언어)의 실행 주체를 "4번 또는 프론트 레이어"로 열어뒀는데,
프론트가 아직 없어 4번(이 문서)이 맡는다. 원래 README 설계("Team Capability Builder — Notion으로 위임,
자체 UI 구현 안 함")와도 일치한다.

- **톤 원칙**: 토스의 8가지 라이팅 원칙(해요체·능동태·긍정형·쉬운 용어) + SPEC.md 2장 정책을 결합.
  구체 규칙은 `app/notion/blocks.py` 상단 docstring 참고. Pivot 판정도 "실패"가 아니라
  "지금은 다른 방법이 나음"으로 긍정 프레이밍
- **멀티테넌시 결정 (2026-07-13)**: 처음엔 Internal Integration(토큰 1개, 우리 워크스페이스 전용)으로
  만들었다가, "서로 다른 사용자가 각자 자기 Notion으로 결과를 받아야 한다"는 요구사항 확인 후
  **Public Integration + OAuth**로 전환. Internal 토큰 방식은 워크스페이스 1개에만 묶이므로
  멀티유저 서비스에 안 맞음 (예전 CLAUDE.md의 "OAuth + REST" 메모와도 일치하는 원래 의도였음)
- **구현** (2026-07-13 토글 기반 단일 페이지로 재설계 — 아래 9절 최신 변경이력 참고):
  - `app/notion/blocks.py` — RoadmapResult → **하나의 페이지** 블록. task는 각각 토글(접었다 펼침)로
    만들어 페이지 이동 없이 한 페이지 안에서 다 보이게 함
  - `app/notion/guide_parser.py` — `task.detailed_guide` 자유 텍스트를 번호 단계/인용구 블록으로 파싱
  - `app/notion/rich_text.py` — 블록 빌더 공통 모듈 (`labeled_paragraph`/`divider`/`table_of_contents`/`toggle` 등)
  - `app/notion/client.py` — 페이지 생성 REST 호출 (헤더를 인자로 받음, 계정을 모름 — 100블록 초과 시 자동 분할)
  - `app/notion/oauth.py` — authorize URL 생성, code→token 교환, 토큰으로 접근 가능한 페이지 검색(v1: 첫 페이지를 기본 발행 대상으로)
  - `app/notion/models.py`/`repository.py` — `notion_connections` 테이블 (account_id 당 1개 연결)
  - `app/notion/publish.py` — account_id로 연결 조회 → 그 계정의 토큰/기본 페이지로 발행
  - `app/core/db.py` — SQLAlchemy 세션 (지금은 이 용도로만 사용)
- **엔드포인트**:
  - `GET /notion/connect?account_id=...` — Notion 인증 화면으로 리다이렉트
  - `GET /notion/callback?code=...&state=...` — 토큰 교환 + 연결 저장 (state에 account_id를 실어보냄)
  - `POST /roadmap/publish`, `POST /roadmap/generate-and-publish` — 둘 다 `account_id` 필수 인자로 받음
- **`account_id`에 대한 미결정 사항**: 1번(온보딩)/사용자 계정 체계가 아직 없어서, 지금은 호출하는 쪽이
  임의의 문자열을 account_id로 넘기는 구조다. 실제 사용자/팀 계정 시스템이 생기면 그 식별자로 교체 필요
  (지금 구조는 "어떤 계정이 어떤 Notion 워크스페이스에 연결됐는지"만 안다)
- **설정**: `.env`의 `NOTION_OAUTH_CLIENT_ID`/`NOTION_OAUTH_CLIENT_SECRET`(Public Integration 발급값),
  `NOTION_OAUTH_REDIRECT_URI`(Notion 대시보드에 등록한 값과 정확히 일치해야 함)
- **검증 상태**: 마이그레이션(docker postgres) 검증 완료, 테스트 33개 전부 통과. **실제 Notion 워크스페이스로 라이브 OAuth 연결·발행까지 완료 확인 (2026-07-13)** — `/notion/connect` → 실제 계정으로 인가 → `/roadmap/generate-and-publish`로 실제 Gemini 로드맵을 실제 Notion 페이지로 발행 성공
- **주의(설치 범위)**: Notion Public Integration은 생성 시 "설치 범위"(Any workspace / Selected workspaces only)를 한 번 정하면 나중에 못 바꾼다. 처음 만든 게 특정 워크스페이스로 제한돼 있어서 재생성함 — 새로 만들 땐 반드시 **Any workspace**로 선택할 것

## 9. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-11 | 계약 v0.2 반영 — fine-tuning 해석 확정(스프린트1 미실시, Stage B 교체 슬롯로 설계), 내부 2단계 파이프라인·DraftPlan 스키마 초안·구현 계획 골격 추가 |
| 2026-07-13 | Stage A/B 구현 완료: `app/contracts/`(goal·research·roadmap·onboarding·assets), `app/roadmap/`(gemini_client·draft_plan·prompts·stage_a·stage_b·service), `app/routers/roadmap.py`, 픽스처 3종, 테스트 5개 파일(가짜 Gemini 클라이언트로 오케스트레이션만 검증, 실제 API 호출은 미검증). 적합성 매트릭스 임계값·findings 주입 방식·disclaimer 보장 위치 확정. SDK는 `google-generativeai`가 아닌 신규 `google-genai` 사용 |
| 2026-07-13 | 실제 Gemini API 라이브 호출로 e2e 검증 완료. 사용자 노출 톤 정립(토스 8원칙 참고) + Notion 발행 기능 추가: `notion_blocks.py`/`notion_client.py`, `/roadmap/publish`·`/roadmap/generate-and-publish` 엔드포인트, 테스트 10개 추가(총 21개 통과). Notion 라이브 발행은 자격증명 대기 중 |
| 2026-07-13 | Notion 연동을 Internal Integration(단일 토큰)에서 **Public Integration + OAuth**로 전환 (멀티유저 요구사항 확인 후). `app/notion/`으로 재구성(blocks·client·oauth·models·repository·publish), `app/core/db.py` 신설, `notion_connections` 테이블 마이그레이션 추가·검증, `/notion/connect`·`/notion/callback` 엔드포인트 추가, `/roadmap/publish`·`/roadmap/generate-and-publish`에 `account_id` 필수화. 테스트 10개 추가(총 31개 통과). Public Integration 앱 등록 및 실제 OAuth 라이브 테스트는 대기 중 |
| 2026-07-13 | `/notion/callback`을 JSON에서 안내 톤 HTML 페이지로 교체(연결 거부·공유 페이지 없음 케이스 포함), `account_id` 기본값 `"default"` 추가(단일 팀 데모 시 계정 신경 안 써도 되게). 실제 Notion Public Integration으로 라이브 OAuth 연결 + `generate-and-publish` e2e 발행 성공 확인. 테스트 33개 전부 통과 |
| 2026-07-13 | **1차 task 표현 방식**: flat 체크리스트 대신 **Notion 데이터베이스**로 전환 시도 — task를 열면 상세 페이지, 표에서는 완료 여부/Layer/주차/난이도/담당 제안/평가 지표/실제 결과가 컬럼으로 한눈에 보임. `Task`에 `detailed_guide` 필드 추가(초보자도 따라할 수 있는 번호 매긴 단계별 가이드 + 예시 프롬프트, Stage B 프롬프트에서 생성). `app/notion/task_database.py` 신설, `client.py`에 `create_database`/`create_database_row` 추가. Notion 데이터베이스 생성 API가 최신 버전(2026-03-11)에서 `initial_data_source.properties`로 스키마를 넣어야 하고 행은 `data_source_id`를 parent로 써야 함을 실제 API 호출로 확인. 초보자용 가이드의 단계 구분자가 "1. " 외 "1단계"/"2번째"로도 나올 수 있어 파서를 정규식 기반으로 강화 |
| 2026-07-13 | **데이터베이스 방식 폐기 → 토글 기반 단일 페이지로 재설계**: "표로 나열하니 한눈에 보기 어렵다"는 피드백 반영. `app/notion/task_database.py` 삭제, `client.py`의 `create_database`/`create_database_row` 제거. 대신 `app/notion/blocks.py`에서 task마다 **토글 블록**(접었을 때 "Layer 아이콘 + 제목 + 소요시간 + 난이도" 한 줄 요약, 펼치면 기대효과·필요도구·평가지표·담당제안(disclaimer 포함)·상세가이드·참고자료가 전부 그 자리에 중첩) 하나로 표현 — 페이지 이동 없이 한 페이지 안에서 접었다 펼치며 확인. 가이드 파싱 로직은 `app/notion/guide_parser.py`로 분리, 공통 블록 빌더는 `app/notion/rich_text.py`(`labeled_paragraph`/`divider`/`table_of_contents`/`toggle` 추가)로 정리. 페이지 상단에 목차(table_of_contents)·전체 통계 콜아웃(📊 task 개수·주차 범위) 추가, Layer별 아이콘(🟢🟡🔴)으로 시각적 스캔 용이하게 함. Notion API로 "토글 children을 페이지 생성 1회 호출에 중첩해서 넣을 수 있는지" 실제 검증(가능함 확인). 실제 Gemini(3.5-flash 할당량 소진돼 3.1-flash-lite로 검증) → 실제 Notion 페이지 발행까지 e2e 확인, 토글 중첩 내용 API로 재조회해 렌더링 정확성 확인. 테스트 41개 전부 통과 |
| 2026-07-13 | **"task \| 지표" 좌우 컬럼 레이아웃 추가**: task 토글과 그 지표(baseline→target)를 Notion `column_list`로 나란히 배치 — 지표가 있는 task만 2단 컬럼(왼쪽 토글/오른쪽 📈 지표 콜아웃), 지표 없는 task는 기존처럼 토글 하나만. 지표는 토글 children에서 제거하고 옆 컬럼으로 이동(중복 방지). `rich_text.py`에 `columns()` 헬퍼 추가. Notion API로 "column_list/column 중첩도 페이지 생성 1회 호출로 되는지" 실제 검증(가능함 확인) 후 구현, 실제 발행 후 컬럼 구조 API 재조회로 확인. 테스트 42개 전부 통과 |
| 2026-07-13 | **체크박스 + 진행 현황 새로고침 API 추가**: 토글 → `to_do`(체크박스+중첩 내용, `rich_text.py`의 `checkable()`)로 변경, 대표 라벨은 task 이름만(Layer 아이콘 유지, 소요시간/난이도는 펼친 내용 첫 줄로 이동). **중요 제약**: Notion은 체크박스를 체크해도 다른 블록(지표 요약)을 자동으로 재계산해주지 않는다(그러려면 데이터베이스 rollup/formula 필요 — 이미 폐기한 방식) — 실시간 자동 반영은 불가능함을 사용자에게 설명하고, 대신 **수동 새로고침 API**(`POST /roadmap/{page_id}/refresh-progress`)를 추가해 체크 상태를 다시 읽어와 진행 현황 콜아웃을 갱신하도록 구현. 발행 시 만들어진 체크박스/요약 블록의 실제 ID를 추적해야 해서 `published_roadmaps`/`published_roadmap_tasks` 테이블 신설(마이그레이션 검증 완료), `app/notion/tracking_repository.py`·`app/notion/progress.py` 추가, `client.py`에 `get_block_children`/`get_block`/`update_callout_text` 추가. `publish_roadmap()`이 이제 `{"url","page_id"}` dict를 반환(기존 str 반환에서 변경). Notion 페이지 생성 API가 중첩 블록의 ID를 응답에 안 주는 것 확인 → 발행 후 별도로 `GET .../children`을 조회해 실제 블록 ID를 알아내는 방식으로 구현(빈 상위 배열 인덱스와 컬럼 유무만 알면 실제 ID를 역추적 가능하도록 `RoadmapPageLayout`에 위치 메타데이터 포함). "전체 너비(Full width)" 페이지 설정은 Notion 공식 API에 노출되어 있지 않아(문서 확인 완료) 자동화 불가 — 사용자가 발행 후 페이지 `•••` 메뉴에서 수동으로 켜야 함. 실제 체크 → 새로고침 e2e 확인(Notion 요약 텍스트가 "완료 1/2"로 실제 갱신됨). 테스트 51개 전부 통과 |
