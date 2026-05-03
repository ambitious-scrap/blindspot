"""Blindspot — Seed Corpora Script

Loads and embeds curated corpora into ChromaDB.
"""

import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from src.retrieval.retriever import CorpusRetriever
from src.config import settings


def seed():
    retriever = CorpusRetriever(settings.chroma_persist_directory)
    print("Seeding legal rules...")
    retriever.seed_all(
        rules_path=settings.legal_rules_path,
        benchmarks_path=settings.benchmark_clauses_path,
        statutes_path=settings.indian_statutes_path,
    )
    print("✅ Corpora seeded successfully!")
    print(f"   Legal rules: {retriever.legal_rules.count()} entries")
    print(f"   Benchmark clauses: {retriever.benchmark_clauses.count()} entries")
    print(f"   Indian statutes: {retriever.indian_statutes.count()} entries")


if __name__ == "__main__":
    seed()
