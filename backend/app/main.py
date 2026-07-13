from fastapi import FastAPI

from app.routers import notion_auth, roadmap

app = FastAPI(title="AI Champion Backend")
app.include_router(roadmap.router)
app.include_router(notion_auth.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
