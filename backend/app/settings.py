from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    frontend_origins: str = "http://localhost:5173"
    enable_dev_endpoints: bool = False

    # --- AI agent (OpenRouter + MCP) -----------------------------------------
    # No default key/model/base URL is hardcoded — the app must run (health,
    # import, export, Gantt) with none of this set. Only /chat degrades, with
    # AI_NOT_CONFIGURED.
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = 60.0

    agent_max_steps: int = 6
    agent_max_read_tool_calls: int = 8
    agent_history_turns: int = 8
    agent_max_user_message_chars: int = 4000

    enable_mcp: bool = True

    @property
    def frontend_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.openrouter_api_key) and bool(self.openrouter_model)


def get_settings() -> Settings:
    return Settings()
