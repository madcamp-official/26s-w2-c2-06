from fastapi import FastAPI

from app.routers import roadmap

app = FastAPI(title="AI Champion Backend")
app.include_router(roadmap.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
