from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000
    
    # CORS Origins (comma-separated string or list)
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o-mini"
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Azure Queue
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    EVALUATION_QUEUE_NAME: str = "evaluation-jobs"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()