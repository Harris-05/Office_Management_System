from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )
    database_url: PostgresDsn
    environment: str = "development"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_secret: str = Field(default="local-development-only-not-for-production", repr=False)
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    cookie_secure: bool = False
    bcrypt_cost: int = Field(default=12, ge=10, le=16)
    session_idle_seconds: int = Field(default=1800, ge=60)
    session_absolute_seconds: int = Field(default=28800, ge=60)
    anonymous_seconds: int = Field(default=900, ge=60)
    temporary_password_seconds: int = Field(default=172800, ge=60)
    body_limit_bytes: int = Field(default=1048576, ge=1024)
    rate_namespace: str = "branch-office"
    api_limit: int = Field(default=120, ge=1)
    login_ip_limit: int = Field(default=10, ge=1)
    login_account_limit: int = Field(default=5, ge=1)
    csrf_limit: int = Field(default=20, ge=1)

    @property
    def cookie_name(self) -> str:
        return "__Host-branch_session" if self.cookie_secure else "branch_session_dev"

    @model_validator(mode="after")
    def production_safety(self):
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Unknown environment.")
        if any("*" in item for item in self.allowed_hosts + self.allowed_origins):
            raise ValueError("Explicit hosts and origins are required.")
        if self.environment == "production" and (
            not self.cookie_secure
            or len(self.rate_limit_secret) < 32
            or self.rate_limit_secret.startswith("local-development")
            or not self.allowed_hosts
            or not self.allowed_origins
            or any(not origin.startswith("https://") for origin in self.allowed_origins)
            or any(host in {"localhost", "127.0.0.1", "testserver"} for host in self.allowed_hosts)
        ):
            raise ValueError(
                "Production requires secure cookies, HTTPS origins, hosts and a secret."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
