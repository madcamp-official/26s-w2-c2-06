from fastapi import FastAPI

from app.routers import opportunity

app = FastAPI(title="AI Champion Backend")
app.include_router(opportunity.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
