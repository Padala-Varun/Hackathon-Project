from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """All tunables. Override any of them with an env var, the project .env or backend/.env (backend/.env wins)."""

    model_config = SettingsConfigDict(env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"), extra="ignore")

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
    candidates: int = 20
    match_threshold: int = 50  # confidence (0-100) below which a match is not "verified"
    duplicate_similarity: float = 0.88

    # LLM: any OpenAI-compatible endpoint. Default = Mistral 7B via local Ollama (no key needed).
    llm_enabled: bool = True
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "mistral"
    llm_api_key: str = "ollama"
    llm_timeout_s: float = 180
    llm_max_tokens: int = 260
    # Shortcut: MISTRAL_API_KEY in .env switches the LLM to Mistral's hosted API (OpenAI-compatible).
    mistral_api_key: str = ""
    mistral_model: str = "ministral-8b-latest"  # works on the free tier (mistral-small has 0 quota there)

    # Notifications: "local://mock" stores cards for the UI; or a Teams incoming-webhook URL.
    webhook_url: str = "local://mock"
    high_risk_threshold: int = 70

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @model_validator(mode="after")
    def _use_mistral_api(self) -> "Settings":
        if self.mistral_api_key and "localhost:11434" in self.llm_base_url:  # explicit LLM_* settings still win
            self.llm_base_url = "https://api.mistral.ai/v1"
            self.llm_model = self.mistral_model
            self.llm_api_key = self.mistral_api_key
            self.llm_timeout_s = min(self.llm_timeout_s, 60)
        return self


settings = Settings()
