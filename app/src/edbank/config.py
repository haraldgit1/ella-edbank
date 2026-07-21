from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    edbank_env: str = "development"
    edbank_log_level: str = "INFO"

    llm_base_url: str = "http://host.docker.internal:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "mistral-7b-instruct-v0.3"
    llm_context_tokens: int = 4096
    llm_max_output_tokens: int = 1024
    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 120

    app_database_url: str
    mcp_server_url: str = "http://mcp-server:8001/mcp"
    mcp_timeout_seconds: int = 10
    mcp_max_tool_rounds: int = 3

    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimension: int = 384
    rag_top_k: int = 4
    rag_min_score: float = 0.70
    rag_max_context_tokens: int = 1500
    max_csv_size_mb: int = 5


settings = Settings()
