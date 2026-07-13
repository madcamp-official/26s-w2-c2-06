from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini API 키는 기능별로 분리 (계약 §6). 각 모듈은 자기 키만 읽는다.
    # 기능 3은 v0.4에서 검색 백엔드를 소스 API로 전환 → research 키는 옵션(LLM 요약 확장용).
    gemini_api_key_research: str = ""  # 기능 3 (research/) — 옵션
    gemini_api_key_roadmap: str = ""  # 기능 4 (roadmap/)
    gemini_research_model: str = "gemini-flash-latest"  # 옵션 LLM 요약 시 사용할 모델
    database_url: str = ""
    redis_url: str = ""
    notion_api_token: str = ""
    notion_database_id: str = ""
    ml_server_host: str = ""


settings = Settings()
