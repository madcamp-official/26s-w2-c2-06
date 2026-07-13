# Gemini API 키 발급 & 설정 가이드

> 스프린트1(기능 3·4)은 Gemini API를 사용한다. **키는 담당자별로 각자 발급**받아 **자기 로컬 `.env`에만** 넣는다. 키는 커밋하지 않는다(계약 v0.3 §6, `.env`는 `.gitignore` 유지).
>
> - 최종 수정일: 2026-07-13
> - 관련 계약: `docs/sprint/SPRINT1_CONTRACT.md` §6 (API 키 정책), §2.4 (리서치 캐싱)

---

## 0. 키를 왜 2개로 나누나

계약 v0.3에서 Gemini 키를 **환경변수 2개로 분리**했다.

| 환경변수 | 사용 모듈 | 담당 |
|---|---|---|
| `GEMINI_API_KEY_RESEARCH` | `app/research/` (BP 리서치 엔진) | 기능 3 담당자 |
| `GEMINI_API_KEY_ROADMAP` | `app/roadmap/` (맞춤 로드맵 생성) | 기능 4 담당자 |

- **각 모듈은 자기 키만 읽는다** (교차 참조 금지). 이유: 모듈 소유권 분리, 과금·사용량 추적 분리, rate limit 격리(한 모듈이 한도를 다 써도 다른 모듈이 안 막힘).
- 키는 **하드코딩하지 않는다.** 오직 `.env`(환경변수)에서만 읽는다.
- 두 담당자가 **각자 다른 Google 계정/프로젝트로 별도 키를 발급**받는 것을 권장한다(무료 티어 한도가 프로젝트 단위이므로 서로 간섭하지 않음, 4절 참고).

---

## 1. Google AI Studio에서 Gemini API 키 발급

1. 브라우저에서 **<https://aistudio.google.com>** 접속.
2. **Google 계정으로 로그인** (개인 Google 계정이면 충분. 별도 결제 등록 없이 무료 티어 사용 가능).
3. 최초 접속 시 약관 동의 창이 뜨면 동의한다.
4. 좌측 메뉴(또는 우측 상단)에서 **`Get API key`** 클릭 → API 키 관리 화면(<https://aistudio.google.com/apikey>)으로 이동.
5. **`Create API key`(API 키 만들기)** 클릭.
6. 프로젝트 선택 창이 뜨면:
   - 기존 Google Cloud 프로젝트가 있으면 선택하거나,
   - **`Create API key in new project`**(새 프로젝트에 만들기)를 선택한다. 잘 모르면 새 프로젝트로 만드는 것을 권장.
7. 생성된 키(`AIza...`로 시작하는 문자열)를 **복사**한다.
   - ⚠️ 키는 비밀번호와 같다. 채팅/이슈/커밋/스크린샷에 노출하지 말 것. 노출되면 즉시 같은 화면에서 삭제 후 재발급.

> 화면 문구는 AI Studio UI 업데이트에 따라 조금씩 다를 수 있다. 핵심 흐름은 **로그인 → Get API key → Create API key → (프로젝트 선택) → 키 복사**.

---

## 2. 발급받은 키를 로컬 `.env`에 넣기

키는 저장소에 커밋하지 않는다. 각자 **로컬**에만 둔다.

1. `backend/` 디렉토리에 `.env` 파일이 없으면 템플릿에서 복사한다:

   ```bash
   cd backend
   cp .env.example .env
   ```

2. `.env`를 열어 **자기 담당 키만** 채운다. 예: 기능 3 담당자는 `GEMINI_API_KEY_RESEARCH`에만 자기 키를 넣으면 된다.

   ```dotenv
   # 기능 3 담당자 로컬 .env 예시
   GEMINI_API_KEY_RESEARCH=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   GEMINI_API_KEY_ROADMAP=          # 기능 4 담당자만 채움 (비워둬도 됨)
   ```

   ```dotenv
   # 기능 4 담당자 로컬 .env 예시
   GEMINI_API_KEY_RESEARCH=         # 기능 3 담당자만 채움
   GEMINI_API_KEY_ROADMAP=AIzaSyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
   ```

   > 통합 테스트(한 사람이 3·4를 같이 돌려볼 때)는 두 값 모두 채우면 된다. 같은 키를 두 변수에 넣어도 동작은 하지만, 무료 티어 한도를 공유하게 되니 권장하지 않는다.

3. **커밋 금지 확인**: `.env`는 이미 `.gitignore`에 포함되어 있다. `git status`에 `.env`가 안 보이는 게 정상이다. 보인다면 커밋하지 말고 `.gitignore`를 확인할 것.

---

## 3. 설정이 됐는지 확인

```bash
cd backend
# .env 가 git에 안 잡히는지 (아무것도 출력 안 되면 정상)
git status --porcelain | grep '\.env$' || echo "OK: .env is not tracked"

# 파이썬에서 키가 로드되는지 (값 전체를 절대 출력하지 말 것 — 길이만 확인)
python -c "from dotenv import load_dotenv; load_dotenv(); import os; k=os.getenv('GEMINI_API_KEY_RESEARCH',''); print('RESEARCH key set:', bool(k), 'len', len(k))"
```

`app/core/config.py`의 `Settings`가 `.env`를 읽으므로, 애플리케이션 코드에서는 `settings.gemini_api_key_research`(기능 3) / `settings.gemini_api_key_roadmap`(기능 4)로 접근한다. (설정 필드 추가는 기능 3 구현 단계에서 반영.)

---

## 4. 무료 티어 rate limit 주의사항

Gemini API 무료 티어는 **프로젝트 단위**로 한도가 적용된다(키 개수를 늘려도 같은 프로젝트면 한도는 안 늘어난다). 모델별로 대략 아래 수준이며, **정확한 수치·티어는 시간에 따라 바뀌므로 반드시 본인 계정에서 확인**해야 한다.

| 모델(예) | RPM(분당 요청) | RPD(일당 요청) | 비고 |
|---|---|---|---|
| Gemini 2.5 Flash | ~10–15 | ~수백~1,500 | 무료 티어 주력 |
| Gemini 2.5 Flash-Lite | ~15–30 | 더 넉넉 | 가벼운 호출용 |
| Gemini 2.5 Pro | ~5 | ~50 | 무료 티어 매우 빡빡 |

- 위 표는 2026년 7월 기준 **대략치**이며, Google이 언제든 변경한다. **본인 실제 한도는 아래에서 확인**:
  - 활성 rate limit: <https://aistudio.google.com/rate-limit>
  - 프로젝트/티어: <https://aistudio.google.com/projects>
- 무료 티어 초과 시 `429 RESOURCE_EXHAUSTED` 에러가 난다. 개발 중 자주 마주치면:
  - 호출 사이 간격을 두거나(백오프 재시도),
  - **동일 `goal_id` 재요청 캐싱**(계약 §2.4)으로 불필요한 재검색을 없앤다. ← 기능 3은 이 정책상 캐시가 필수.
- 무료 티어에서 보낸 데이터는 Google이 모델 개선에 사용할 수 있다. **회사 기밀/개인정보를 프롬프트에 넣지 말 것**(SPEC 2.6). 스프린트1은 공개 목표 텍스트 + 픽스처만 사용.

---

## 5. Google Search grounding 사용 가능 여부 확인

기능 3(BP 리서치 엔진)은 **Gemini 내장 Google Search grounding**으로 실시간 웹서치를 한다(별도 검색 API 키 불필요, 계약 §6).

### 활성화 방법 (google-genai SDK)

요청에 `google_search` 툴을 붙이면 된다. 응답의 **grounding metadata**에서 `source_url`·제목을 추출한다(계약 §4, 기능 3 구현).

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY_RESEARCH"])
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="...검색 관점 쿼리...",
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
    ),
)
# resp.candidates[0].grounding_metadata 에서 출처 URL/제목 추출
```

### ⚠️ 무료 사용 가능 여부 — 반드시 본인 계정에서 확인

**중요:** grounding은 요금 체계가 일반 텍스트 호출과 다르다. 2026년 기준 확인된 사실:

- **Google AI Studio(웹 UI)에서는 grounding이 무료로 제공**된다.
- **API를 통한 grounding**은 모델·티어에 따라 별도 과금/무료 할당이 다르다:
  - Gemini 2.5 계열: 무료 할당(일 단위) 있음, 초과 시 grounded prompt당 과금 — 그러나 **API 무료 티어에서 grounding 자체가 막혀 있거나 유료 티어 전환이 필요할 수 있다.**
  - Gemini 3 계열: 월 단위 무료 할당(예: 5,000 prompts/월) 있고, 초과 시 검색 쿼리당 과금.
- 즉 **"내 API 키로 grounding이 실제로 되는지"는 계정마다 다를 수 있으니 직접 확인**해야 한다.

**확인 절차:**

1. **공식 문서에서 현재 정책 확인**:
   - Grounding 문서: <https://ai.google.dev/gemini-api/docs/google-search>
   - 요금 페이지: <https://ai.google.dev/gemini-api/docs/pricing>
2. **작은 호출로 실제 테스트** (위 코드로 1회 호출):
   - 정상 응답 + `grounding_metadata`에 소스가 채워지면 → 사용 가능.
   - `PERMISSION_DENIED`/결제 요구/`grounding not available` 류 에러가 나면 → 해당 계정/티어에서는 API grounding이 막힌 것. 결제 등록(유료 티어) 필요 여부를 요금 페이지에서 확인.
3. **본인 사용량/한도**: <https://aistudio.google.com/rate-limit>
4. 만약 무료 API grounding이 불가하면 기능 3 담당자에게 공유할 것 — 캐싱 정책(§2.4)이 있어도 호출 자체가 막히면 실검증이 안 되므로, 결제 등록 여부를 팀에서 결정해야 한다.

> **📌 2026-07-13 실제 관측(기능 3 스모크 시도):** 발급한 신규 키에서
> `gemini-2.5-flash` / `gemini-2.5-flash-lite`는 `404 (no longer available to new users)`,
> 그 외 모델(`gemini-2.0-flash`, `gemini-flash-latest`)은 **plain 호출조차 `429 RESOURCE_EXHAUSTED`**(계정 쿼터 소진) 상태였다.
> 즉 이 키로는 아직 성공 호출 자체가 안 된다. 실제 사용 전 **본인 쿼터/티어를 <https://ai.dev/rate-limit>에서 확인**하고,
> 필요 시 결제(유료 티어) 등록 또는 쿼터 회복을 기다려야 한다. 모델은 코드 수정 없이 `.env`의
> `GEMINI_RESEARCH_MODEL`로 교체할 수 있다(기본값 `gemini-flash-latest`).

---

## 참고 출처

- Rate limits — Gemini API 공식: <https://ai.google.dev/gemini-api/docs/rate-limits> (실제 한도는 AI Studio에서 확인하라고 명시)
- Grounding with Google Search — Gemini API 공식: <https://ai.google.dev/gemini-api/docs/google-search>
- Gemini API pricing — 공식: <https://ai.google.dev/gemini-api/docs/pricing>
- AI Studio 활성 rate limit 확인: <https://aistudio.google.com/rate-limit>
- AI Studio 프로젝트/티어 확인: <https://aistudio.google.com/projects>

> 무료 티어 한도·grounding 과금은 Google이 수시로 바꾼다. 이 문서의 수치는 2026-07-13 기준 대략치이며, **최종 판단은 위 공식 페이지와 본인 계정 대시보드**를 따른다.
