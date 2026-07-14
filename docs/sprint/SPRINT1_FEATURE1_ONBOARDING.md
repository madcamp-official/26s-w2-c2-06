# 스프린트 1 — 기능 1 상세 구현 (온보딩 인터뷰)

> `SPEC.md` 4.1(온보딩 인터뷰)의 세부 구현 문서. 공통 계약은 `SPRINT1_CONTRACT.md` 참고.
> 이 기능의 **출력**(`OnboardingData`)은 기능 2(진단·목표)와 기능 4(로드맵)의 입력이다.

- 최종 수정일: 2026-07-14
- 상태: v1.0 (기능 1 최초 구현. 계약 §1.1의 임시 `OnboardingData` 스키마를 §8 절차로 정식화)

---

## 1. 목적과 경계

- **하는 것**: 인터뷰 답변 → 팀 프로필 + 반복 업무 리스트 + (선택) 팀원 태깅(`OnboardingData`) 조립.
- **안 하는 것**: 성숙도 진단·목표 설정(기능 2), 로드맵 생성(기능 4). 이 기능은 **맥락 수집만** 한다.
- SPEC 4.1 "질문 설계 원칙": 추상적으로("자동화할 업무를 입력하세요") 묻지 않고, 구체적으로 답하기
  쉬운 질문("하루를 시간순으로 알려주세요")으로 유도한다.

## 2. 인터뷰 구조 (4파트 + 선택 1파트)

`app/onboarding/questions.py`의 `INTERVIEW_SCRIPT`가 대본이다. 프론트가 이 정적 데이터로 화면을 그린다.

| 파트 | 수집 항목 | 산출 필드 |
|---|---|---|
| 기본 정보 | 업종 · 팀 규모 · 담당 업무 카테고리 | `industry`, `team_size`, `work_categories` |
| AI 활용 수준 | 4단계 택1 | `ai_adoption_level` |
| 조직 환경 | 가이드라인 유무 · 지정 도구 · 외부 AI 허용 · 편차 | `org_environment` |
| 반복 업무 상세 (핵심) | 하루 시간순 자유서술 → 업무별 후속 5문항 | `repetitive_tasks[]` |
| 팀원 태깅 (선택) | 강점 · AI 편안함 · 업무 부담 (익명 식별자) | `member_tags[]` |

반복 업무 파트의 후속 5문항(`TASK_FOLLOWUP_QUESTIONS`): 빈도 / 정형성 / 평균 소요시간 / 민감정보 여부 /
기존 처리 방식. SPEC 4.1 "언급된 업무마다 추가 확인"을 그대로 코드화했다.

## 3. 처리 흐름

```
[프론트] GET /onboarding/interview  → 대본 렌더링
   │  (반복 업무 파트) 하루 자유서술 입력
   ▼
[POST /onboarding/extract-tasks]  day_narrative → 반복 업무 후보(TaskCandidate[])   ← LLM(Gemini) 유일 사용처
   │  프론트가 후보를 후속 5문항으로 사용자에게 확인·수정
   ▼
[POST /onboarding/submit]  InterviewAnswers → OnboardingData   ← 규칙 기반(결정론적)
```

- **LLM은 자유서술 → 업무 후보 추출(`extract.py`)에만 쓴다.** 뽑힌 후보의 빈도/정형성/소요시간은
  best-guess이며 `needs_confirmation=true`로 표시된다 — 사용자가 후속 질문으로 확정한다.
- `build_onboarding()`은 **확정값이 있으면(`task_details`) 그걸 우선**하고, 없고 자유서술만 있으면
  후보 추출로 채운다. 확정값 우선이므로 LLM 없이도(키 없이도) 확정 답변만으로 동작한다.

## 4. 정책 연계 (SPEC 2장)

- **회사 기밀/개인정보 미저장 (2.6)**: 팀원 태깅은 실명 대신 익명 식별자(`member_id`, 예: `M1`)만 받는다.
  질문 문구·`help_text`에도 "이름 대신 익명 식별자"를 명시.
- **민감정보 → 게이트 연결 (2.6·4.4)**: 업무별 `contains_sensitive_info`를 반드시 수집한다.
  이 값이 기능 4의 게이트("민감정보 + 가이드라인 없음 → 보류·경고")로 이어진다. (AX 리포트 예시
  워크스루 §7에서 지적된 "온보딩에서 민감정보를 안 물으면 게이트가 안 걸린다" 리스크를 방지.)
- **조직 환경 수집 → 목표 정의서 조직 제약으로 승계**: `org_environment`(가이드라인·지정 도구·외부 AI)는
  기능 2가 `GoalDefinition.org_constraints`로 매핑한다 (FEATURE2 문서 §3 참고).

## 5. 파일

| 파일 | 역할 |
|---|---|
| `contracts/onboarding.py` | 산출물 스키마(`OnboardingData` 외). **공동 소유** — 계약 §1.1 정식화 |
| `onboarding/questions.py` | 인터뷰 대본(정적) |
| `onboarding/answers.py` | 인터뷰 제출 원본 입력(`InterviewAnswers`) — 기능 1 내부 |
| `onboarding/extract.py` | 자유서술 → 반복 업무 후보 추출 (Gemini) |
| `onboarding/prompts.py` | 추출 프롬프트 |
| `onboarding/service.py` | `build_onboarding()` — 규칙 기반 조립 |
| `routers/onboarding.py` | HTTP 엔드포인트 3개 |
| `fixtures/interview_answers_marketing.json` | AX 리포트 예시(마케팅 8인팀) 기반 표준 입력 픽스처 |

## 6. 계약 정식화 (SPEC.md 4.1 / 계약 §1.1)

계약 §1.1이 임시로 정의했던 `OnboardingData`를 §8 절차로 확정하면서, SPEC 4.1의 "AI 활용 수준"·
"조직 환경"을 담도록 **기본값과 함께 필드를 추가**했다(`ai_adoption_level`, `org_environment`,
`work_categories`). 전부 기본값이 있어 기능 4의 기존 입력을 깨지 않는다(계약 §8 "필드 추가는 기본값으로").
회귀: `tests/test_contracts.py::test_onboarding_new_fields_are_backward_compatible`.

## 7. 해소된 SPEC 오픈 이슈

- SPEC 4.1 "인터뷰 형식(대화형 vs 설문형)" → **설문형 4파트 + 반복 업무 파트만 자유서술**로 확정.
  자유서술은 LLM이 후보로 구조화하고 후속 질문으로 확인받는 하이브리드.
- "정확한 질문 문구" → `questions.py`에 고정.
