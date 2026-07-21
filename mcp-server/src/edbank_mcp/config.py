from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_database_url: str
    edbank_log_level: str = "INFO"
    edbank_env: str = "development"


settings = Settings()
