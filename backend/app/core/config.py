from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini API 키는 기능별로 분리 (계약 v0.3 §6). 각 모듈은 자기 키만 읽는다.
    gemini_api_key_research: str = ""  # 기능 3 (research/)
    gemini_api_key_roadmap: str = ""  # 기능 4 (roadmap/)
    # 기능 3 리서치용 모델. 계정/티어에 따라 사용 가능 모델이 다르므로 env로 오버라이드 가능.
    # (2026-07 기준 gemini-2.5-flash 계열은 신규 키에서 404 → 별칭 latest 기본값 사용)
    gemini_research_model: str = "gemini-flash-latest"
    database_url: str = ""
    redis_url: str = ""
    notion_api_token: str = ""
    notion_database_id: str = ""
    ml_server_host: str = ""


settings = Settings()
