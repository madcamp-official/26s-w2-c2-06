# 26s-w2-c2-06

## 공통과제 II : 협업형 실전 산출물 제작 (2인 1팀)

**목적:** 실시간 인터랙션, LLM Wrapper, Cross-Platform 중 하나의 옵션을 선택해 구현하며, 선택한 기술을 실제로 동작하는 형태의 산출물로 완성한다.

**선택 옵션:**

| 옵션 | 설명 |
|---|---|
| 실시간 인터랙션 | 사용자 간 상태 변화, 실시간 데이터 흐름, 스트리밍 응답 등 실시간성이 드러나는 기능을 구현 |
| LLM Wrapper | LLM API를 활용하여 AI 기능이 포함된 산출물을 구현 |
| Cross-Platform | 하나의 산출물을 여러 실행 환경에서 사용할 수 있도록 구현* |

> *데스크톱 앱 ↔ 모바일 앱; 혹은 다른 폼팩터에서의 앱; 웹만/웹 기반 프레임워크(Electron, Tauri 등) 대신 다른 프레임워크를 시도해보는 것을 적극 권장

**결과물:** 선택한 옵션이 적용된 작동 가능한 산출물, 실행 가능한 코드, 시연 자료 및 관련 문서

---

## 팀원

| 이름 | 학교 | GitHub | 역할 |
|---|---|---|---|
| 임유빈 | 서울대학교 | [@lunar-yoobin](https://github.com/lunar-yoobin) | FE |
| 김경원 | 한양대학교 | [@kkw610](https://github.com/kkw610) | BE |

---

## 선택 옵션

- [ ] 실시간 인터랙션
- [x] LLM Wrapper
- [ ] Cross-Platform

---

## 기획안

- **산출물 주제:** AI Champion - 중간관리자 대상 AX(AI 전환) 맞춤 로드맵 생성 서비스
- **제작 목적:** 기존 AX 지원 서비스가 B2B 엔터프라이즈 중심인 것과 달리, 관리자 개인 단위에서 산업별 Best Practice를 검색해 팀 업무에 바로 적용 가능한 로드맵을 LLM으로 생성해주는 도구를 구현
- **선택 옵션:** LLM Wrapper (Gemini API 사용 예정)
- **핵심 구현 요소:**
  - 온보딩 대화형 인터뷰로 산업/직무/팀 상황 수집
  - RAG 기반 산업별 AX Best Practice 검색 및 요약
  - 협업체계/자동화 포인트/평가지표로 구성된 맞춤형 로드맵(구조화된 JSON) 생성
- **사용 / 시연 시나리오:** 관리자가 온보딩 질문에 답변 → RAG가 관련 리포트에서 유사 사례를 검색 → 사용자 상황에 맞춰 재구성된 로드맵을 카드 형태로 제시
- **팀원별 역할:**

### 개발 일정

| 날짜 | 목표 |
|---|---|
| Day 1 | 환경 세팅, Gemini API·DB 연동 테스트 |
| Day 2 | AX 리포트 수집·청킹·임베딩 (RAG 데이터 구축) |
| Day 3 | 온보딩 대화 플로우 + RAG 검색 API 구현 |
| Day 4 | 로드맵 생성 프롬프트 및 구조화된 출력 설계 |
| Day 5 | 프론트엔드 연동, 로드맵 결과 UI 구현 |
| Day 6 | 레이트리밋·캐싱 안정화, 통합 테스트 |
| Day 7 | 배포 및 시연 자료 준비 |

---

## 구현 명세서

| 구현 요소 | 설명 | 우선순위 |
|---|---|---|
| 온보딩 대화형 인터뷰 | 산업/직무/팀 규모/AX 활용 단계 수집 | 필수 |
| RAG 리서치 검색 | 사용자 프로필 기반 유사 BP 청크 검색·요약 | 필수 |
| 맞춤형 로드맵 생성 | 협업체계·자동화 포인트·평가지표 JSON 생성 | 필수 |
| 프롬프트 예시 제공 | 자동화 포인트별 바로 쓸 수 있는 프롬프트 생성 | 선택 |
| 주간 체크인 코칭 | 로드맵 실행 여부 트래킹 및 코칭 메시지 생성 | 선택 |

---

## 아키텍처

<!-- 실시간 인터랙션: WebSocket/SSE/WebRTC 구조도 / LLM Wrapper: API 연동 흐름도 / Cross-Platform: 플랫폼 구성도 -->

```
사용자 요청
   │
   ▼
프론트엔드 (Next.js)
   │
   ▼
백엔드 API (FastAPI)
   │
   ├─▶ 캐시 확인 (Redis) ── hit ──▶ 응답 반환
   │        │ miss
   │        ▼
   ├─▶ RAG 검색 (PostgreSQL + pgvector)
   │        │
   │        ▼
   ├─▶ 레이트리밋 큐 (15 RPM / 1,500 RPD 준수)
   │        │
   │        ▼
   └─▶ Gemini Flash API (구조화된 JSON 생성)
            │
            ▼
   저장 (PostgreSQL) + 캐시 갱신 → 응답 반환
```
 
- **LLM**: Gemini 3.5 Flash / 3.1 Flash-Lite (무료 티어)
- **RAG 저장소**: PostgreSQL + pgvector (별도 벡터DB 없이 단일 DB로 처리)
- **레이트리밋/캐시**: Redis (분당 요청 수 제한 + 응답 캐싱)

---

## 설계 문서

> 프로젝트 성격에 따라 필요한 항목만 작성

### 화면 / 인터페이스 설계

<!-- Figma 링크, 화면 이미지, CLI 사용 예시, 앱 화면 등 -->
- 온보딩 챗봇 화면: 산업/직무/팀 상황을 대화형으로 수집
- 로드맵 결과 화면: 협업체계 / 자동화 포인트 / 평가지표 3개 섹션 카드 UI
- (Figma 링크 추후 추가)

### 데이터 구조

<!-- DB 스키마, JSON 구조, 파일 저장 방식 등 -->
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    industry VARCHAR(50),
    role VARCHAR(50),
    team_size INT,
    ax_stage VARCHAR(20)  -- 관심/시범/확산/embed
);
 
CREATE TABLE report_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100),
    industry VARCHAR(50),
    content TEXT,
    embedding VECTOR(768)
);
 
CREATE TABLE roadmaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    content JSONB,  -- {collaboration, automation_points, metrics}
    created_at TIMESTAMP DEFAULT now()
);
```

### API / 외부 서비스 연동

| Method / 방식 | Endpoint / 서비스 | 설명 | 요청 | 응답 | 비고 |
|---|---|---|---|---|---|
| POST | `/onboarding` | 사용자 프로필 수집 | 산업, 직무, 팀 규모 등 | user_id | - |
| POST | `/roadmap/generate` | 로드맵 생성 요청 | user_id | roadmap JSON | Gemini Flash 호출 |
| Google Generative AI SDK | Gemini API | LLM 생성 및 임베딩 | 프롬프트/텍스트 | 텍스트 또는 벡터 | 무료 티어(RPM 제한 있음) |

---

## 산출물 및 실행 방법

- **산출물 설명:**
- **실행 환경:**
- **실행 방법:**
- **시연 영상 / 이미지:** (선택)

백엔드 관련 파일은 전부 `backend/` 아래에 있습니다 (프론트엔드가 추가되면 `frontend/`가 별도로 생길 예정).

**방법 A. docker-compose로 전체 스택 실행 (권장 — 팀원 간 동일 환경 보장)**

```bash
cd backend
cp .env.example .env   # 필요한 키(GEMINI_API_KEY 등) 채우기

docker compose up --build
# app: http://localhost:8000  (DB/Redis는 컨테이너 내부에서 자동 연결됨)
# 컨테이너 기동 시 alembic 마이그레이션 자동 적용
```

**방법 B. 로컬(uv)로 백엔드만 직접 실행**

```bash
cd backend

# 의존성 설치 (uv 사용, 또는 pip install -r requirements.txt)
uv sync

cp .env.example .env   # DATABASE_URL/REDIS_URL을 로컬에 맞게 조정

# DB/Redis는 직접 띄우거나 docker compose up db redis 로 그 두 개만 기동
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 테스트
uv run pytest
```

### 기술 구성

| 분류 | 사용 기술 |
|---|---|
| 핵심 기술 | FastAPI, Pydantic |
| 실행 환경 | Python 3.11, uv (패키지 매니저), Docker / docker-compose |
| 데이터 저장 | PostgreSQL 16 + pgvector, Redis |
| 마이그레이션 | Alembic |
| 외부 API / 서비스 | Gemini API, Notion API |
| 기타 | 학교 ML 서버(GPU, CAMP-10) — 임베딩/RAG 서빙용, KCloud VPN 필요 |

---

## 회고 문서

> [KPT 방법론 참고](https://velog.io/@habwa/%EB%8B%A8%EA%B8%B0-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8-%ED%9A%8C%EA%B3%A0-KPT-%EB%B0%A9%EB%B2%95%EB%A1%A0)

### Keep — 잘 된 점, 다음에도 유지할 것

-
-
-

### Problem — 아쉬웠던 점, 개선이 필요한 것

-
-
-

### Try — 다음번에 시도해볼 것

-
-
-

### 팀원별 소감

**임유빈:**

> 

**김경원:**

> 

---

## 참고 자료

### 실시간 인터랙션

**WebSocket**
- https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API
- https://techblog.woowahan.com/5268/
- https://tech.kakao.com/posts/391
- https://daleseo.com/websocket/
- https://kakaoentertainment-tech.tistory.com/110

**Socket.IO**
- https://socket.io/docs/v4/
- https://inpa.tistory.com/entry/SOCKET-%F0%9F%93%9A-Namespace-Room-%EA%B8%B0%EB%8A%A5
- https://adjh54.tistory.com/549
- https://fred16157.github.io/node.js/nodejs-socketio-communication-room-and-namespace/

**SSE (Server-Sent Events)**
- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- https://developer.mozilla.org/ko/docs/Web/API/Server-sent_events/Using_server-sent_events
- https://api7.ai/ko/blog/what-is-sse

**TCP / UDP Socket**
- https://docs.python.org/3/library/socket.html
- https://inpa.tistory.com/entry/NW-%F0%9F%8C%90-%EC%95%84%EC%A7%81%EB%8F%84-%EB%AA%A8%ED%98%B8%ED%95%9C-TCP-UDP-%EA%B0%9C%EB%85%90-%E2%9D%93-%EC%89%BD%EA%B2%8C-%EC%9D%B4%ED%95%B4%ED%95%98%EC%9E%90

**gRPC Streaming**
- https://grpc.io/docs/what-is-grpc/core-concepts/
- https://tech.ktcloud.com/entry/gRPC%EC%9D%98-%EB%82%B4%EB%B6%80-%EA%B5%AC%EC%A1%B0-%ED%8C%8C%ED%97%A4%EC%B9%98%EA%B8%B0-HTTP2-Protobuf-%EA%B7%B8%EB%A6%AC%EA%B3%A0-%EC%8A%A4%ED%8A%B8%EB%A6%AC%EB%B0%8D
- https://tech.ktcloud.com/entry/gRPC%EC%9D%98-%EB%82%B4%EB%B6%80-%EA%B5%AC%EC%A1%B0-%ED%8C%8C%ED%97%A4%EC%B9%98%EA%B8%B02-Channel-Stub
- https://inspirit941.tistory.com/371
- https://devocean.sk.com/blog/techBoardDetail.do?ID=167433

**WebRTC**
- https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- https://webrtc.org/getting-started/overview
- https://web.dev/articles/webrtc-basics?hl=ko
- https://devocean.sk.com/blog/techBoardDetail.do?ID=164885
- https://beomkey-nkb.github.io/%EA%B0%9C%EB%85%90%EC%A0%95%EB%A6%AC/webRTC%EC%A0%95%EB%A6%AC/
- https://gh402.tistory.com/45
- https://on.com2us.com/tech/webrtc-coturn-turn-stun-server-setup-guide/

**QUIC / WebTransport**
- https://developer.mozilla.org/en-US/docs/Web/API/WebTransport_API
- https://datatracker.ietf.org/doc/html/rfc9000
- https://news.hada.io/topic?id=13888

#### KCLOUD VM / Cloudflare Tunnel 환경별 주의사항

| 환경 | 사용 가능(권장) 기술 | 포트/조건 | 주의할 기술 |
|---|---|---|---|
| **로컬 / 일반 VM** | HTTP/REST, WebSocket, Socket.IO, SSE, TCP Socket, gRPC Streaming, WebRTC, QUIC/WebTransport 등 대부분 가능 | 직접 포트 개방 가능. 예: 3000, 5000, 8000, 8080, 9000 등. 외부 공개 시 방화벽/보안그룹/공인 IP 설정 필요 | WebRTC는 STUN/TURN 필요 가능. QUIC/WebTransport는 HTTP/3 · UDP 지원 필요 |
| **KCLOUD VM (VPN 내부)** | HTTP/REST, WebSocket, Socket.IO, SSE, WebRTC 시그널링 | 접속 기기 VPN 필요. 기본 허용 포트: **22, 80, 443**. 개발 포트(3000, 8000, 8080 등)는 직접 접근 제한 가능 | TCP Socket은 포트 제한 있음. gRPC는 HTTP/2 설정 필요. WebRTC 미디어·UDP·QUIC/WebTransport 비권장 |
| **KCLOUD VM + Tunnel** | HTTP/REST, WebSocket, Socket.IO, SSE, WebRTC 시그널링 | VM의 `localhost:<port>`를 도메인에 연결. `localPort`는 **1024~65535**. 예: 3000, 8000, 8080 가능 | 순수 TCP Socket, UDP, WebRTC 미디어/DataChannel, QUIC/WebTransport 불가. gRPC 보장 어려움 |
| **외부 서비스 + 우리 도메인** | HTTP/REST, WebSocket, Socket.IO, SSE, WebRTC 시그널링 | Vercel/Netlify/Railway/Render/AWS/GCP 등에 배포 후 CNAME/A 레코드 연결. 보통 외부는 **443** 사용 | WebSocket/gRPC/TCP/UDP는 플랫폼 지원 여부 확인 필요. 서버리스 플랫폼은 장시간 연결 제한 가능 |
| **서버 없이 외부 SaaS 사용** | Supabase Realtime, Firebase, Pusher/Ably, LLM API Streaming | 직접 포트 관리 불필요. 각 서비스 SDK/API 사용 | 커스텀 TCP/UDP 서버 구현 불가. WebRTC는 STUN/TURN 필요할 수 있음 |

### LLM Wrapper

- https://github.com/teddylee777/openai-api-kr
- https://github.com/teddylee777/langchain-kr
- https://devocean.sk.com/blog/techBoardDetail.do?ID=167407
- https://mastra.ai/docs

### Cross-Platform

- https://flutter.dev/
- https://reactnative.dev/
- https://docs.expo.dev/
- https://kotlinlang.org/multiplatform/
