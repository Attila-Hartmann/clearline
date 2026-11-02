from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # repo root (api/clearline/config.py → repo)


class Tier(BaseModel):
    """One model tier. Any OpenAI-compatible endpoint; region is declared, not guessed."""

    base_url: str
    model: str
    api_key: str
    region: Literal["eu", "non-eu"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    database_url: str  # from .env (see .env.example)
    data_mode: Literal["synthetic", "live"] = "synthetic"

    worker_base_url: str = "https://api.deepseek.com/v1"
    worker_model: str = "deepseek-chat"
    worker_api_key: str = ""
    worker_region: Literal["eu", "non-eu"] = "non-eu"

    drafter_base_url: str = "https://api.deepseek.com/v1"
    drafter_model: str = "deepseek-chat"
    drafter_api_key: str = ""
    drafter_region: Literal["eu", "non-eu"] = "non-eu"

    core_banking_mcp_url: str = ""  # e.g. http://core-banking:8100/mcp; empty → in-process MCP server
    daily_live_case_limit: int = 50
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def tier(self, name: Literal["worker", "drafter"]) -> Tier:
        t = Tier(
            base_url=getattr(self, f"{name}_base_url"),
            model=getattr(self, f"{name}_model"),
            api_key=getattr(self, f"{name}_api_key"),
            region=getattr(self, f"{name}_region"),
        )
        if not t.api_key and t.base_url == self.worker_base_url:  # same endpoint → reuse the worker key
            t.api_key = self.worker_api_key
        # ADR-003: customer-entered data never leaves EU endpoints.
        if self.data_mode == "live" and t.region != "eu":
            raise RuntimeError(f"DATA_MODE=live forbids non-EU endpoint for tier '{name}' ({t.base_url})")
        return t


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields come from env/.env
