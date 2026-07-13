from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    database_url: str = ""
    redis_url: str = ""
    notion_api_token: str = ""
    notion_database_id: str = ""
    ml_server_host: str = ""


settings = Settings()
