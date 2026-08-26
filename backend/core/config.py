import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (complisoc/.env) by explicit path so the
# keys are resolved regardless of the current working directory.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)


def _read_secret(name: str) -> str | None:
    value = os.getenv(name)
    if not value:
        return None
    value = value.strip()
    if value.lower().startswith("your_") or value.startswith("<"):
        return None
    return value


GEMINI_API_KEY = _read_secret("GEMINI_API_KEY")
GROQ_API_KEY = _read_secret("GROQ_API_KEY")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# Groq retired `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` on 2026-08-16.
# `openai/gpt-oss-20b` is the currently-supported model that works with JSON mode.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_MODEL_FALLBACKS: list[str] = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b"]

PROMPT_VERSION = "mvp-v1"
