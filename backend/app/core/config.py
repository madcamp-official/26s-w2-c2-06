from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    database_url: str = ""
    redis_url: str = ""
    notion_api_version: str = "2026-03-11"
    notion_oauth_client_id: str = ""
    notion_oauth_client_secret: str = ""
    notion_oauth_redirect_uri: str = "http://localhost:8000/notion/callback"
    ml_server_host: str = ""

    # 기능 3 리서치 소스 어댑터 (모두 옵션 — 없어도 해당 소스만 빠지고 나머지로 동작)
    github_token: str = ""  # GitHub Search rate limit 10/min -> 30/min 상향용
    tavily_api_key: str = ""  # trend 소스 (무료 월 1000 크레딧)


settings = Settings()
