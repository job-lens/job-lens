from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JOB_LENS_", env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    public_origin: str = "http://localhost:8080"
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "api"]
    storage_kind: Literal["local", "s3"] = "local"
    storage_root: Path = Path(".data/private")
    s3_bucket: str | None = None
    s3_endpoint: str | None = None
    s3_region: str = "us-east-1"
    job_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    job_lease_seconds: int = Field(default=60, ge=10, le=3600)

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        parsed = urlsplit(self.public_origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("public_origin must be an HTTP(S) origin")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("public_origin must not contain credentials, path, query or fragment")
        self.public_origin = self.public_origin.rstrip("/")
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("database_url must use postgresql+psycopg")
        if not self.trusted_hosts or any("*" in h for h in self.trusted_hosts):
            raise ValueError("trusted_hosts must list explicit hosts")
        if self.storage_kind == "s3" and not self.s3_bucket:
            raise ValueError("s3_bucket is required for s3 storage")
        if self.environment == "production":
            if parsed.scheme != "https" or self.storage_kind != "s3":
                raise ValueError("production requires HTTPS and private S3 storage")
        return self
