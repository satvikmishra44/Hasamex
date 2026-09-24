import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CHROMA_DIR = DATA_DIR / "chroma"
STATIC_DIR = BASE_DIR / "static"
DATABASE_PATH = DATA_DIR / "app.db"

load_dotenv(PROJECT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    max_query_length: int = int(os.getenv("MAX_QUERY_LENGTH", "1000"))
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    database_path: Path = DATABASE_PATH
    chroma_path: Path = CHROMA_DIR
    raw_path: Path = RAW_DIR


settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)