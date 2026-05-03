"""Blindspot — Scout Agent"""

import json
from typing import List, Dict, Any
from src.agents.base import BaseAgent
from src.state.schema import Clause, ScoutOutput, DocType, BlindspotState
from src.config import settings


class ScoutAgent(BaseAgent):
    """Parses contract and produces structured clause map."""

    name = "scout"
    description = "Document mapping — clause segmentation and classification"
    model_preference = "flash"  # Flash is fast and good enough for parsing

    def run(self) -> Dict[str, Any]:
        if not self.state:
            raise ValueError("State not set")

        text = self.state.contract_text

        # Use LLM to classify and segment clauses in one pass
        output_data = self._analyze_document_llm(text)

        doc_type_str = output_data.get("doc_type", "unknown")
        try:
            doc_type = DocType(doc_type_str)
        except ValueError:
            doc_type = DocType.UNKNOWN

        clauses_data = output_data.get("clauses", [])
        
        # Build Clause objects
        clauses = []
        for i, c in enumerate(clauses_data):
            clauses.append(Clause(
                id=c.get("id", f"clause_{i+1}"),
                section_header=c.get("section_header"),
                text=c.get("text", ""),
                position={"start": 0, "end": 0},  # Approximation since LLM doesn't easily return byte offsets
                clause_type=c.get("clause_type", "other")
            ))

        return {
            "scout_output": ScoutOutput(
                doc_type=doc_type,
                doc_type_confidence=output_data.get("doc_type_confidence", 0.5),
                clauses=clauses,
            )
        }

    def _analyze_document_llm(self, text: str) -> Dict[str, Any]:
        """Use LLM to classify doc and extract clauses."""
        
        system = """You are Scout, an expert legal document parser.
Your task is to analyze a legal document, classify its type, and segment it into logical clauses.

Document Types: 'freelance_services_agreement', 'nda', 'employment_agreement', 'vendor_msa', 'rental_agreement', 'unknown'
Clause Types: 'ip_assignment', 'termination', 'non_compete', 'payment', 'confidentiality', 'governing_law', 'indemnification', 'dispute_resolution', 'force_majeure', 'other'

Output a JSON object with this exact structure:
{
  "doc_type": "string (one of Document Types)",
  "doc_type_confidence": 0.0 to 1.0,
  "clauses": [
    {
      "id": "clause_1",
      "section_header": "string or null",
      "text": "exact text of the clause",
      "clause_type": "string (one of Clause Types)"
    }
  ]
}

Make sure to extract EVERY substantive clause from the document. Do not summarize the text, provide the EXACT text of the clause.
"""

        prompt = f"Analyze the following contract document and extract all clauses:\n\n{text[:15000]}" # Limit to fit in context

        response_text = self.call_llm(prompt, system=system, temperature=0.1)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if parsed.get("clauses") and len(parsed["clauses"]) > 0:
                    return parsed
        except Exception:
            pass

        # Fallback to prevent the UI from showing empty clauses if LLM JSON is malformed
        return {
            "doc_type": "unknown", 
            "doc_type_confidence": 0.5, 
            "clauses": [
                {
                    "id": "clause_1",
                    "section_header": "Main Clause",
                    "text": text[:200] + "...",
                    "clause_type": "other"
                }
            ]
        }

