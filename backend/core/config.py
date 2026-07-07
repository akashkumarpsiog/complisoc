import os

from dotenv import load_dotenv

load_dotenv()


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
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

PROMPT_VERSION = "mvp-v1"
