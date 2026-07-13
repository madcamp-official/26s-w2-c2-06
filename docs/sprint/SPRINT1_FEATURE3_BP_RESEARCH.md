# 스프린트 1 — 기능 3: BP 리서치 엔진

> 공통 계약은 `SPRINT1_CONTRACT.md` 참고 (특히 2절 아키텍처 확정, 4절 ResearchContext 스키마, 7절 병렬 작업 프로토콜). 이 문서는 기능 3 담당자가 계약을 확인하고, 세부 구현 계획을 채워나가는 문서다. 스펙 근거는 `SPEC.md` 4.3.

- 최종 수정일: 2026-07-13
- 상태: 계약 v0.3 반영 (리서치 캐싱 정책 확정. 구현 계획 골격 확정, 세부는 담당자가 채움)

---

## 1. 이 기능이 하는 일 (계약 요약)

- **입력**: 목표 정의서 `GoalDefinition` (goal_text + org_constraints + candidate_tasks) — 계약 1절
- **하는 일**: 목표 텍스트 + 조직 제약을 바탕으로 AX 트렌드/논문/frontier 개인 AI 활용법을 웹서치 → 요약·구조화. **RAG의 "R"만 담당.**
- **하지 않는 일**: 로드맵/task 생성, 적합성 판정, 사용자에게 결과 직접 노출 (전부 4번의 역할)
- **출력**: `ResearchContext` — 계약 4절 스키마. 코드 경계는 `run_research(goal: GoalDefinition) -> ResearchContext` 함수 하나 (계약 2.3절)

## 2. 확정 사항 (계약 v0.2에서 결정됨)

- [x] 웹서치 구현 방식: **Gemini API + Google Search grounding** — 별도 검색 API 없이 검색+요약을 한 호출로. `source_url`은 grounding metadata에서 추출
- [x] 요약 생성 모델: **Gemini API** (무료 티어 우선)
- [x] 통합 형태: 같은 repo `research/` 패키지, 별도 서비스 아님
- [x] 실패 계약: 검색 실패 시 예외 대신 `status="failed"` + 빈 `findings` 반환 (계약 4절)
- [x] 픽스처 책임: `fixtures/research_context_goal_001.json` 작성은 3번 담당자, 검수는 4번 담당자 (계약 7절) — **스프린트 첫 작업으로 우선 처리**

## 3. 담당자 확인·결정 사항 (남은 체크리스트)

- [ ] `ResearchContext` 스키마 최종 검토 — 필드 추가/변경 필요 시 계약 8절 절차 (CONTRACT 먼저 갱신 → 4번 담당자 확인)
- [x] 리서치 실행 시점: **실시간 웹서치 유지 + 동일 `goal_id` 재요청은 캐싱** (계약 v0.3 2.4절 확정). 캐시 키=`goal_id`, `status="failed"`는 캐싱하지 않음. 저장 방식은 담당자 재량(§4-6)
- [ ] 소스 신뢰도 기준: grounding이 반환한 소스 중 무엇을 버릴지 (예: 개인 블로그 스팸, 광고성 페이지) — SPEC.md 2.6 "출처 있는 경우만 인용" 준수
- [ ] `metric_snippet` 수치의 출처 검증 방식: grounding 인용 구간과 수치가 실제로 일치하는지 확인 로직
- [ ] `source_type`(trend/research/practice) 분류 기준
- [ ] findings 3~8건을 못 채웠을 때 `partial` 판정 기준 (예: 2건 이하면 partial)

## 4. 구현 계획 (골격 — 담당자가 세부 채움)

1. **쿼리 빌드**: `goal_text` + `org_constraints`(허용 도구, 보안 수준)로 검색 관점 2~4개 생성 (예: 도구 특화 사례 / 방법론·연구 / 실패 요인). 사용한 쿼리는 `search_queries`에 기록
2. **grounding 호출**: 관점별 Gemini + google_search 호출 → 응답의 grounding metadata에서 소스 URL·제목 수집
3. **findings 구조화**: 소스별 2~3문장 요약, `relevant_method`, `metric_snippet`(수치+출처 확인된 것만) 채워 `finding_id` 부여
4. **필터링·검증**: 소스 신뢰도 필터 → pydantic 스키마 검증 → `status` 판정(ok/partial/failed)
5. **테스트**: `tests/test_contracts.py`에 스키마 검증 테스트, `failed` 경로 테스트 포함

## 5. 오픈 이슈 (SPEC.md 4.3에서 이관)

- ~~리서치 갱신 주기 (캐싱 정책과 함께 결정)~~ → 계약 v0.3 2.4절에서 확정: 실시간 웹서치 + `goal_id` 단위 캐싱(스프린트1은 갱신 주기 없이 1회 조사 후 재사용). 갱신 주기 자동화는 이후 스프린트로 이관
- 소스 신뢰도 기준
- 캐시 저장 방식: 스프린트1은 프로세스 인메모리 캐시(`goal_id → ResearchContext`)로 시작, 필요 시 이후 파일/DB로 승격 (구현 시 확정)

## 6. 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-07-13 | 계약 v0.3 반영 — 리서치 캐싱 정책 확정(실시간 웹서치 + `goal_id` 단위 캐싱, `status="failed"` 미캐싱). 3절 캐싱 체크리스트 확정 처리, 5절 오픈 이슈에서 갱신 주기 이슈 종료 |
| 2026-07-11 | 계약 v0.2 반영 — 웹서치 방식(Gemini grounding)·통합 형태(모듈)·실패 계약 확정, 구현 계획 골격 추가 |
