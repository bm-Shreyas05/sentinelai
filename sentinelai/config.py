"""Runtime configuration, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

# Local-only default key. `serve` refuses to bind a non-loopback address while it is in use.
DEV_KEY = "dev-key-change-me"


def _env(key, default=None):
    return os.environ.get(key, default)


@dataclass
class Settings:
    db_path: Path = field(default_factory=lambda: Path(_env("SENTINEL_DB_PATH", "var/sentinel.db")))
    model_dir: Path = field(default_factory=lambda: Path(_env("SENTINEL_MODEL_DIR", "var/models")))
    policy_dir: Path = field(default_factory=lambda: Path(_env("SENTINEL_POLICY_DIR",
                                   str(Path(__file__).resolve().parent.parent / "policies"))))
    api_keys: tuple = field(default_factory=lambda: tuple(
        k.strip() for k in _env("SENTINEL_API_KEYS", DEV_KEY).split(",") if k.strip()))
    rate_limit_per_min: int = field(default_factory=lambda: int(_env("SENTINEL_RATE_LIMIT_PER_MIN", "600")))
    # Cost-sensitive decision layer: below this amount a BLOCK is downgraded to REVIEW, because the
    # customer friction of a hard block outweighs the money at risk. Card testing is still caught:
    # the burst is reviewed and the large follow-up payment is blocked on its own score.
    min_block_amount: float = field(default_factory=lambda: float(_env("SENTINEL_MIN_BLOCK_AMOUNT", "500")))
    # Alert channels (all optional; console logging is always on)
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD", ""))
    alert_email_to: str = field(default_factory=lambda: _env("ALERT_EMAIL_TO", ""))
    alert_webhook_url: str = field(default_factory=lambda: _env("ALERT_WEBHOOK_URL", ""))
    # Optional LLM narrative for investigations (deterministic summary is used when unset)
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: _env("SENTINEL_LLM_MODEL", "claude-opus-5-5"))


def get_settings() -> Settings:
    return Settings()
