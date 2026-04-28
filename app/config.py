from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_uri: str = "http://127.0.0.1:8000/auth/google/callback"
    token_storage_path: Path = Path(".tokens/oauth_token.json")
    log_level: str = "INFO"

    @property
    def token_path_resolved(self) -> Path:
        p = self.token_storage_path
        if not p.is_absolute():
            p = Path.cwd() / p
        return p


settings = Settings()
