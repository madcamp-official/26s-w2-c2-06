from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers import diagnosis, notion_auth, onboarding, report, roadmap

app = FastAPI(title="AI Champion Backend")
app.include_router(onboarding.router)
app.include_router(diagnosis.router)
app.include_router(report.router)
app.include_router(roadmap.router)
app.include_router(notion_auth.router)

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    """데모 프론트엔드 (단일 페이지). 백엔드와 같은 오리진이라 CORS 불필요."""
    return FileResponse(_STATIC_DIR / "index.html")
