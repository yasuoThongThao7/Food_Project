from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./food_guide.db"
    secret_key: str = Field(
        default="development-only-secret-change-this-before-use", alias="JWT_SECRET"
    )
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-now"
    ai_search_url: str = ""
    ai_search_key: str = ""
    ai_itinerary_url: str = ""
    ai_itinerary_key: str = ""
    ai_timeout_ms: int = 15000
    ai_min_conf: float = 0.4
    mock_ai: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

if settings.secret_key == "development-only-secret-change-this-before-use" and not settings.mock_ai:
    raise RuntimeError(
        "JWT_SECRET must be changed before starting outside MOCK_AI=true mode"
    )
