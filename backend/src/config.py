"""Blindspot — Configuration.

All thresholds, weights, and model selection live here.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data" if (BACKEND_DIR / "data").exists() else PROJECT_ROOT / "data"
GENERATED_DIR = BACKEND_DIR / "generated"


class Settings(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8888
    cors_origins: list[str] = ["*"]

    # Gemini API (google.genai package)
    google_api_key: str = ""
    llm_enabled: bool = True
    gemini_pro_model: str = "gemini-2.5-pro"
    gemini_flash_model: str = "gemini-2.5-flash"        # Fast model for Adversary

    # Agent-to-model routing
    jurist_model: str = gemini_pro_model      # Legal reasoning
    adversary_model: str = gemini_flash_model  # Fast adversarial generation
    
    temperature: float = 0.1
    max_tokens: int = 2000

    # Retrieval
    chroma_persist_directory: str = str(BACKEND_DIR / "chroma_db")
    embedding_model: str = "text-embedding-3-small"
    legal_rules_path: str = str(DATA_DIR / "legal_rules.json")
    benchmark_clauses_path: str = str(DATA_DIR / "benchmark_clauses.json")
    indian_statutes_path: str = str(DATA_DIR / "indian_statutes.json")

    # Thresholds
    doc_type_confidence_threshold: float = 0.7
    risk_score_high: int = 70
    risk_score_caution: int = 40
    deviation_score_outlier: float = 2.0
    sse_timeout_ms: int = 60000

    # Cache
    demo_mode: bool = False
    investigator_mock_mode: bool = False
    cache_similarity_threshold: float = 0.95
    cache_ttl_seconds: int = 3600

    # Artifacts
    generated_dir: str = str(GENERATED_DIR)
    redline_output_path: str = str(GENERATED_DIR / "redlined_contract.docx")

    # Negotiation
    max_negotiation_rounds: int = 10
    escalation_timeout_hours: int = 48

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
