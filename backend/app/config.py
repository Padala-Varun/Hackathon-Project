from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """All tunables. Override any of them with an env var or backend/.env (e.g. LLM_MODEL=qwen2.5:3b)."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    data_dir: Path = PROJECT_DIR / "data" / "raw"
    store_dir: Path = PROJECT_DIR / "data" / "store"
    models_dir: Path = BACKEND_DIR / "models"
    field_map: Path = BACKEND_DIR / "field_map.yaml"

    # Retrieval (Hugging Face models, run locally)
    embed_backend: str = "fastembed"  # fastembed | sentence-transformers | hash (tests only)
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"  # or BAAI/bge-reranker-base (more precise, ~6x slower on CPU)
    rerank_temperature: float = 0  # 0 = auto (2.5 for ms-marco models, 1.0 otherwise); calibrates confidence
    use_reranker: bool = True
    vector_backend: str = "chroma"  # chroma | numpy
    candidates: int = 30
    match_threshold: int = 50  # confidence (0-100) below which a match is not "verified"
    duplicate_similarity: float = 0.88

    # LLM: any OpenAI-compatible endpoint. Default = Mistral 7B via local Ollama (no key needed).
    llm_enabled: bool = True
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "mistral"
    llm_api_key: str = "ollama"
    llm_timeout_s: float = 180
    llm_max_tokens: int = 260

    # Notifications: "local://mock" stores cards for the UI; or a Teams incoming-webhook URL.
    webhook_url: str = "local://mock"
    high_risk_threshold: int = 70

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
