"""Blindspot v2.0 — Configuration

All thresholds, weights, and model selection live here.
No magic numbers in source files.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]

    # Gemini API (google.genai package)
    google_api_key: str = "AIzaSyDO7FTAnsTEgajmhIuMVqAAXW8-5Zhkk_g"
    gemini_pro_model: str = "gemini-3.1-pro-preview"   # Works with google.genai
    gemini_flash_model: str = "gemini-2.5-flash"        # Fast model for Adversary

    # Agent-to-model routing
    jurist_model: str = gemini_pro_model      # Legal reasoning
    adversary_model: str = gemini_flash_model  # Fast adversarial generation
    
    temperature: float = 0.1
    max_tokens: int = 2000

    # Retrieval
    chroma_persist_directory: str = "./chroma_db"
    embedding_model: str = "text-embedding-3-small"
    legal_rules_path: str = "../../data/legal_rules.json"
    benchmark_clauses_path: str = "../../data/benchmark_clauses.json"
    indian_statutes_path: str = "../../data/indian_statutes.json"

    # Thresholds
    doc_type_confidence_threshold: float = 0.7
    risk_score_high: int = 70
    risk_score_caution: int = 40
    deviation_score_outlier: float = 2.0
    sse_timeout_ms: int = 60000

    # Cache
    demo_mode: bool = False
    cache_similarity_threshold: float = 0.95
    cache_ttl_seconds: int = 3600

    # Negotiation
    max_negotiation_rounds: int = 10
    escalation_timeout_hours: int = 48

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
