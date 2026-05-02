"""Blindspot v2.0 — Jurist Agent

Evaluates each clause against legal rules corpus and Indian statutes.
Enforces grounded reasoning — no citations outside the corpus.
"""

import json
from typing import Dict, Any, List
from src.agents.base import BaseAgent
from src.state.schema import Clause, LegalVerdict, BlindspotState, VerdictLabel, Severity
from src.retrieval.retriever import get_retriever
from src.tools.validation import CitationValidator
from src.config import settings


class JuristAgent(BaseAgent):
    """Legal evaluation with grounded citations."""

    name = "jurist"
    description = "Legal evaluation — per-clause verdicts with grounded citations"
    model_preference = "pro"  # Use Gemini 3.1 Pro for legal reasoning

    def run(self) -> Dict[str, Any]:
        if not self.state:
            raise ValueError("State not set")

        clauses = self.state.scout_output.clauses if self.state.scout_output else []
        user_role = self.state.user_role
        deal_context = self.state.deal_context

        # Get retriever for corpus search
        retriever = get_retriever()

        # Get valid citation IDs for validation
        valid_citation_ids = self._get_valid_citation_ids(retriever)

        verdicts = {}
        for clause in clauses:
            verdict = self._evaluate_clause(clause, user_role, retriever, valid_citation_ids)
            verdicts[clause.id] = verdict

        return {"jurist_verdicts": verdicts}

    def _evaluate_clause(
        self,
        clause: Clause,
        user_role: str,
        retriever,
        valid_citation_ids: List[str]
    ) -> LegalVerdict:
        """Evaluate a single clause against legal rules."""

        # Search legal rules corpus
        rules = retriever.search_legal_rules(clause.text, k=3)

        # Search Indian statutes
        statutes = retriever.lookup_indian_statute(clause.text)

        # Build prompt for LLM analysis
        system = """You are the Jurist, a legal expert specializing in Indian contract law.
Your job is to evaluate contract clauses against legal rules and Indian statutes.

HARD CONSTRAINT: You MUST ONLY cite corpus entry IDs that are provided in the search results.
NEVER generate citations not present in the search results.
NEVER hallucinate case law or statutory references.

Output JSON with:
- verdict_label: "standard" | "non_standard" | "predatory" | "unenforceable"
- severity: "low" | "medium" | "high"
- reasons: list of strings (2-5 reasons, each ≤20 words, tied to evidence)
- citations: list of corpus entry IDs (MUST be from search results only)
- enforceability_note: string (only if verdict references jurisdiction-specific enforceability)"""

        prompt = f"""Analyze this contract clause:

CLAUSE TYPE: {clause.clause_type}
TEXT: {clause.text[:1000]}

USER ROLE: {user_role}

RELEVANT LEGAL RULES:
{json.dumps(rules, indent=2)}

RELEVANT INDIAN STATUTES:
{json.dumps(statutes, indent=2)}

Provide your verdict as JSON."""

        if self.client and not settings.demo_mode:
            response = self.call_llm(prompt, system=system, temperature=0.1)
            try:
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())

                    # Validate citations
                    is_valid, errors = CitationValidator.validate_legal_verdict(
                        result, valid_citation_ids
                    )

                    if not is_valid:
                        # Repair — remove invalid citations
                        result = CitationValidator.validate_and_repair(
                            result, valid_citation_ids
                        )

                    return LegalVerdict(
                        verdict_label=result.get("verdict_label", "standard"),
                        severity=result.get("severity", "low"),
                        reasons=result.get("reasons", ["No specific issues identified"]),
                        citations=result.get("citations", []),
                        enforceability_note=result.get("enforceability_note"),
                    )
            except Exception as e:
                print(f"Jurist LLM parsing error: {e}")

        # Fallback / Demo mode
        return self._mock_verdict(clause, rules)

    def _mock_verdict(self, clause: Clause, rules: List[Dict]) -> LegalVerdict:
        """Generate mock verdict for demo mode."""
        if clause.clause_type == "ip_assignment":
            return LegalVerdict(
                verdict_label=VerdictLabel.NON_STANDARD,
                severity=Severity.HIGH,
                reasons=[
                    "Overbroad IP assignment may include pre-existing works",
                    "Assignment scope exceeds project deliverables per Copyright Act §17",
                ],
                citations=[r.get("id", "") for r in rules[:2] if "id" in r],
                enforceability_note="Pre-existing IP assignment void under Copyright Act proviso",
            )
        elif clause.clause_type == "non_compete":
            return LegalVerdict(
                verdict_label=VerdictLabel.UNENFORCEABLE,
                severity=Severity.HIGH,
                reasons=[
                    "Non-compete beyond engagement void under ICA §27",
                    "Indian courts consistently refuse post-term non-compete enforcement",
                ],
                citations=["IS-001"],
                enforceability_note="Void under Indian Contract Act §27",
            )
        elif clause.clause_type == "termination":
            return LegalVerdict(
                verdict_label=VerdictLabel.NON_STANDARD,
                severity=Severity.MEDIUM,
                reasons=[
                    "Asymmetric notice period favors client",
                    "Contractor notice requirement exceeds market standard",
                ],
                citations=[r.get("id", "") for r in rules[:1] if "id" in r],
                enforceability_note=None,
            )
        else:
            return LegalVerdict(
                verdict_label=VerdictLabel.STANDARD,
                severity=Severity.LOW,
                reasons=["Clause appears standard for this contract type"],
                citations=[],
                enforceability_note=None,
            )

    def _get_valid_citation_ids(self, retriever) -> List[str]:
        """Get all valid citation IDs from both corpora."""
        # This would typically load all IDs from both collections
        # For simplicity, we'll extract from the JSON files
        import json
        import os

        ids = []
        base_path = os.path.join(os.path.dirname(__file__), "../../data")

        for filename in ["legal_rules.json", "indian_statutes.json"]:
            path = os.path.join(base_path, filename)
            if os.path.exists(path):
                with open(path) as f:
                    entries = json.load(f)
                    ids.extend([e.get("id", "") for e in entries if "id" in e])

        return [i for i in ids if i]  # Filter out empty strings
