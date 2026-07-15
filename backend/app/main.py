from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import diagnosis, notion_auth, onboarding, report, roadmap

app = FastAPI(title="AI Champion Backend")
app.include_router(onboarding.router)
app.include_router(diagnosis.router)
app.include_router(report.router)
app.include_router(roadmap.router)
app.include_router(notion_auth.router)

_STATIC_DIR = Path(__file__).parent / "static"

# 파비콘·매니페스트 등 정적 파일을 /static/* 로 서빙 (index.html은 별도 라우트로 이미 서빙 중).
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """데모 프론트엔드 (단일 페이지). 백엔드와 같은 오리진이라 CORS 불필요."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    """일부 브라우저·크롤러는 <link> 태그와 무관하게 루트의 /favicon.ico를 직접 요청한다."""
    return FileResponse(_STATIC_DIR / "favicon.ico")
