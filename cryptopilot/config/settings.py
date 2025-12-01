"""Configuration management with hierarchy: CLI args > ENV vars > TOML > Defaults."""

from pathlib import Path
from typing import Any

import toml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIConfig(BaseSettings):
    """API configuration."""

    default_provider: str = "coingecko"
    api_key: str | None = None
    request_timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 2.0


class DataConfig(BaseSettings):
    """Data collection configuration."""

    default_timeframe: str = "1d"
    default_symbols: list[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL"])
    retention_days: int = 730
    gap_fill_check: bool = True
    batch_size: int = 100


class AnalysisConfig(BaseSettings):
    """Analysis configuration."""

    default_strategies: list[str] = Field(
        default_factory=lambda: ["trend_following", "mean_reversion"]
    )
    confidence_threshold: float = 0.6
    risk_tolerance: str = "moderate"

    @field_validator("risk_tolerance")
    @classmethod
    def validate_risk_tolerance(cls, v: str) -> str:
        allowed = ["conservative", "moderate", "aggressive"]
        if v.lower() not in allowed:
            raise ValueError(f"risk_tolerance must be one of {allowed}")
        return v.lower()


class ReportingConfig(BaseSettings):
    """Reporting and LLM configuration."""

    llm_provider: str = "ollama"
    llm_model: str = "gemma2:2b"
    output_format: list[str] = Field(default_factory=lambda: ["console", "json"])
    include_personal_context: bool = True
    llm_api_base: str | None = None
    llm_api_key: str | None = None


class CurrencyConfig(BaseSettings):
    """Currency configuration."""

    base_currency: str = "USD"


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    path: Path = Field(default_factory=lambda: Path.home() / ".cryptopilot" / "cryptopilot.db")
    schema_path: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "database" / "schema.sql"
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="CRYPTOPILOT_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    api: APIConfig = Field(default_factory=APIConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    currency: CurrencyConfig = Field(default_factory=CurrencyConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def load_from_toml(cls, path: Path | None = None) -> "Settings":
        """Load settings from TOML file with environment variable override.

        Priority: ENV vars > TOML file > Defaults
        """
        settings_dict: dict[str, Any] = {}

        if path is None:
            path = Path.home() / ".cryptopilot" / "config.toml"

        if path.exists():
            with open(path) as f:
                settings_dict = toml.load(f)

        return cls(**settings_dict)

    def save_to_toml(self, path: Path | None = None) -> None:
        """Save current settings to TOML file."""
        if path is None:
            path = Path.home() / ".cryptopilot" / "config.toml"

        path.parent.mkdir(parents=True, exist_ok=True)

        settings_dict = {
            "api": self.api.model_dump(exclude_none=True),
            "data": self.data.model_dump(exclude_none=True),
            "analysis": self.analysis.model_dump(exclude_none=True),
            "reporting": self.reporting.model_dump(exclude_none=True),
            "currency": self.currency.model_dump(exclude_none=True),
            "debug": self.debug,
            "log_level": self.log_level,
        }

        with open(path, "w") as f:
            toml.dump(settings_dict, f)

    def update_from_dict(self, updates: dict[str, Any]) -> None:
        """Update settings from nested dictionary (for CLI overrides)."""
        for key, value in updates.items():
            if "." in key:
                section, setting = key.split(".", 1)
                if hasattr(self, section):
                    section_obj = getattr(self, section)
                    if hasattr(section_obj, setting):
                        setattr(section_obj, setting, value)
            else:
                if hasattr(self, key):
                    setattr(self, key, value)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get global settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings.load_from_toml()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from file."""
    global _settings
    _settings = Settings.load_from_toml()
    return _settings
