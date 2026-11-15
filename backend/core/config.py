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
# Groq deprecated qwen/qwen3.6-27b on 2026-09-14, removed 2026-09-22.
# qwen/qwen3.8-27b is the replacement with 250K TPM (vs 8K for gpt-oss models).
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_MODEL_FALLBACKS: list[str] = ["qwen/qwen3.8-27b"]

PROMPT_VERSION = "mvp-v2"
