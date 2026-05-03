"""Blindspot — Retrieval Module.

ChromaDB powers vector search when available. JSON-backed lexical search keeps
the review path alive when the vector store is empty or embeddings fail.
"""

import json
import logging
import os
import re
from threading import Lock
from enum import Enum
from typing import List, Dict, Any, Optional

import chromadb

from src.config import settings


logger = logging.getLogger(__name__)

class CorpusRetriever:
    """Unified retriever for all three corpora."""

    def __init__(self, persist_directory: str | None = None):
        self.persist_directory = persist_directory or settings.chroma_persist_directory
        self.legal_rules_entries = self._load_json(settings.legal_rules_path)
        self.benchmark_entries = self._load_json(settings.benchmark_clauses_path)
        self.statute_entries = self._load_json(settings.indian_statutes_path)

        self.client = None
        self.legal_rules = None
        self.benchmark_clauses = None
        self.indian_statutes = None

        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.legal_rules = self.client.get_or_create_collection("legal_rules")
            self.benchmark_clauses = self.client.get_or_create_collection("benchmark_clauses")
            self.indian_statutes = self.client.get_or_create_collection("indian_statutes")
            self.seed_all(
                settings.legal_rules_path,
                settings.benchmark_clauses_path,
                settings.indian_statutes_path,
            )
        except Exception as exc:
            logger.warning("Chroma unavailable; falling back to JSON lexical retrieval: %s", exc)

    def _load_json(self, path: str) -> List[Dict[str, Any]]:
        """Load corpus entries from disk."""
        if not os.path.exists(path):
            logger.warning("Corpus file not found: %s", path)
            return []
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def seed_all(self, rules_path: str, benchmarks_path: str, statutes_path: str):
        """Seed all collections from JSON files."""
        if self.legal_rules is not None and os.path.exists(rules_path):
            self._seed_collection(self.legal_rules, rules_path, "rule")
        if self.benchmark_clauses is not None and os.path.exists(benchmarks_path):
            self._seed_collection(self.benchmark_clauses, benchmarks_path, "benchmark")
        if self.indian_statutes is not None and os.path.exists(statutes_path):
            self._seed_collection(self.indian_statutes, statutes_path, "statute")

    def _seed_collection(self, collection, json_path: str, doc_type: str):
        """Seed a single collection from JSON."""
        with open(json_path, "r", encoding="utf-8") as f:
            entries = json.load(f)

        if collection.count() > 0:
            return  # Already seeded

        documents = []
        metadatas = []
        ids = []

        for entry in entries:
            documents.append(json.dumps(entry))
            metadatas.append({
                "doc_type": doc_type,
                "id": entry.get("id", ""),
                **{k: str(v) for k, v in entry.items() if k != "text" and isinstance(v, (str, int, float))}
            })
            ids.append(entry.get("id", f"{doc_type}_{len(ids)}"))

        try:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
        except Exception as exc:
            logger.warning("Could not seed %s into Chroma: %s", json_path, exc)

    def search_legal_rules(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Search legal rules corpus."""
        results = self._query_collection(self.legal_rules, query, k)
        return results or self._lexical_search(query, self.legal_rules_entries, k)

    def find_similar_clauses(self, query: str, doc_type_filter: Optional[str] = None, k: int = 10) -> List[Dict[str, Any]]:
        """Search benchmark clauses corpus."""
        normalized_filter = self._enum_value(doc_type_filter)
        where = {"doc_type": normalized_filter} if normalized_filter else None
        results = self._query_collection(self.benchmark_clauses, query, k, where=where)
        if results:
            return results
        entries = self.benchmark_entries
        if normalized_filter:
            entries = [entry for entry in entries if entry.get("doc_type") == normalized_filter]
        return self._lexical_search(query, entries, k)

    def lookup_indian_statute(self, query: str) -> List[Dict[str, Any]]:
        """Search Indian statutes corpus."""
        results = self._query_collection(self.indian_statutes, query, 3)
        return results or self._lexical_search(query, self.statute_entries, 3)

    def all_citation_ids(self) -> List[str]:
        """Return legal-rule and statute IDs valid for Jurist citations."""
        ids = [
            entry.get("id", "")
            for entry in self.legal_rules_entries + self.statute_entries
            if entry.get("id")
        ]
        return ids

    def _query_collection(
        self,
        collection,
        query: str,
        k: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query Chroma if collection has rows; otherwise return empty list."""
        if collection is None:
            return []
        try:
            count = collection.count()
            if count == 0:
                return []
            n_results = min(k, count)
            kwargs: Dict[str, Any] = {"query_texts": [query], "n_results": n_results}
            if where:
                kwargs["where"] = where
            results = collection.query(**kwargs)
            return self._format_results(results)
        except Exception as exc:
            logger.warning("Chroma query failed; using JSON fallback: %s", exc)
            return []

    def _format_results(self, results) -> List[Dict[str, Any]]:
        """Format Chroma results into list of dicts."""
        if not results or not results.get("ids"):
            return []
        formatted = []
        for i, doc_id in enumerate(results["ids"][0]):
            entry = json.loads(results["documents"][0][i])
            entry["distance"] = results["distances"][0][i] if results.get("distances") else None
            formatted.append(entry)
        return formatted

    def _lexical_search(
        self,
        query: str,
        entries: List[Dict[str, Any]],
        k: int,
    ) -> List[Dict[str, Any]]:
        """Deterministic lexical fallback for corpus search."""
        query_lower = query.lower()
        tokens = {
            token for token in re.findall(r"[a-z0-9]+", query_lower)
            if len(token) > 2
        }
        scored = []
        for entry in entries:
            haystack = self._entry_text(entry).lower()
            score = sum(1 for token in tokens if token in haystack)
            for keyword in entry.get("pattern_keywords", []):
                keyword_lower = str(keyword).lower()
                if keyword_lower and keyword_lower in query_lower:
                    score += 8
            for situation in entry.get("applicable_situations", []):
                situation_lower = str(situation).replace("_", " ").lower()
                if situation_lower and situation_lower in query_lower:
                    score += 6
            if entry.get("clause_type") and str(entry["clause_type"]).lower() in query_lower:
                score += 5
            if score:
                scored.append((score, entry))

        scored.sort(key=lambda item: (-item[0], item[1].get("id", "")))
        if not scored:
            return entries[:k]
        return [entry for _, entry in scored[:k]]

    def _entry_text(self, entry: Dict[str, Any]) -> str:
        """Flatten searchable entry fields into text."""
        parts = []
        for value in entry.values():
            if isinstance(value, (str, int, float, bool)):
                parts.append(str(value))
            elif isinstance(value, list):
                parts.extend(str(item) for item in value)
            elif isinstance(value, dict):
                parts.extend(str(item) for item in value.values())
        return " ".join(parts)

    def _enum_value(self, value):
        """Normalize enums before passing filters to Chroma."""
        if isinstance(value, Enum):
            return value.value
        return value


# Global retriever instance
_retriever: Optional[CorpusRetriever] = None
_retriever_lock = Lock()


def get_retriever() -> CorpusRetriever:
    """Get or create the global retriever instance."""
    global _retriever
    with _retriever_lock:
        if _retriever is None:
            _retriever = CorpusRetriever(persist_directory=settings.chroma_persist_directory)
    return _retriever
