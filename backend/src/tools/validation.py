"""Blindspot — Citation Validation Utility

Ensures all agent outputs cite only corpus entries (hard constraint #1).
"""

import re
from typing import List, Dict, Any, Tuple


class CitationValidator:
    """Validates that citations in agent outputs resolve to real corpus entries."""

    @staticmethod
    def validate_legal_verdict(
        verdict: Dict[str, Any],
        valid_citation_ids: List[str]
    ) -> Tuple[bool, List[str]]:
        """Validate a LegalVerdict's citations.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        if "citations" not in verdict:
            return True, []  # No citations is ok

        for citation in verdict.get("citations", []):
            if citation not in valid_citation_ids:
                errors.append(f"Invalid citation ID: {citation}")

        return len(errors) == 0, errors

    @staticmethod
    def extract_citation_ids_from_corpus(corpus_entries: List[Dict]) -> List[str]:
        """Extract all valid citation IDs from a corpus."""
        return [entry.get("id", "") for entry in corpus_entries if "id" in entry]

    @staticmethod
    def validate_and_repair(
        verdict: Dict[str, Any],
        valid_citation_ids: List[str]
    ) -> Dict[str, Any]:
        """Remove invalid citations and return repaired verdict."""
        if "citations" not in verdict:
            return verdict

        valid_citations = [
            c for c in verdict["citations"] if c in valid_citation_ids
        ]

        if len(valid_citations) != len(verdict["citations"]):
            verdict["citations"] = valid_citations
            if "reasons" in verdict:
                verdict["reasons"].append(
                    "Some citations were removed as they were not found in the corpus"
                )

        return verdict
