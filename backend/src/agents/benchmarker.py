"""Blindspot — Benchmarker Agent

Compares each clause against benchmark clauses corpus.
Produces deviation scores and market standard verdicts.
"""

import json
from typing import Dict, Any, List
from src.agents.base import BaseAgent
from src.state.schema import Clause, BenchmarkResult, BlindspotState
from src.retrieval.retriever import get_retriever


class BenchmarkerAgent(BaseAgent):
    """Market comparison — deviation scoring against benchmark clauses."""

    name = "benchmarker"
    description = "Market comparison — deviation scores and market standard verdicts"

    def run(self) -> Dict[str, Any]:
        if not self.state:
            raise ValueError("State not set")

        clauses = self.state.scout_output.clauses if self.state.scout_output else []
        doc_type = self.state.scout_output.doc_type if self.state.scout_output else "freelance_services_agreement"

        retriever = get_retriever()

        scores = {}
        for clause in clauses:
            score = self._benchmark_clause(clause, doc_type, retriever)
            scores[clause.id] = score

        return {"benchmark_scores": scores}

    def _benchmark_clause(
        self,
        clause: Clause,
        doc_type: str,
        retriever
    ) -> BenchmarkResult:
        """Compare clause against benchmark corpus using LLM."""

        # Find similar clauses
        similar = retriever.find_similar_clauses(
            clause.text,
            doc_type_filter=doc_type,
            k=5
        )

        # Compute basic deviation score
        deviation = self._compute_deviation(clause, similar)

        # Extract numerical features
        features = self._extract_numerical_features(clause.text)
        
        # Determine verdict and reasoning via LLM
        system = """You are the Benchmarker, an expert in contract market standards.
Your task is to analyze a clause and compare it against similar benchmark clauses to determine if it is market standard, non-standard, or an outlier.

Output a JSON object with this exact structure:
{
  "verdict": "string (one of: 'market_standard', 'non_standard', 'outlier')",
  "reasoning": "string (brief explanation, <= 30 words, why it deviates or aligns with market)"
}
"""
        prompt = f"""Target Clause ({clause.clause_type}):
{clause.text}

Computed Deviation Score (1.0 = median): {deviation:.2f}

Comparable Market Clauses:
{json.dumps(similar, indent=2)}

Provide your verdict and reasoning as JSON.
"""
        try:
            response_text = self.call_llm(prompt, system=system, temperature=0.1)
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                verdict = result.get("verdict", "market_standard")
                reasoning = result.get("reasoning", "Aligns with market norms.")
            else:
                raise ValueError("No JSON found")
        except Exception as e:
            # Fallback if LLM fails
            if deviation > 2.0:
                verdict = "outlier"
            elif deviation > 1.5:
                verdict = "non_standard"
            else:
                verdict = "market_standard"
            reasoning = f"Automated fallback reasoning. Deviation: {deviation:.2f}"

        return BenchmarkResult(
            deviation_score=deviation,
            comparable_clause_ids=[c.get("id", "") for c in similar if "id" in c],
            numerical_features_extracted=features,
            verdict=verdict,
            reasoning=reasoning,
        )

    def _compute_deviation(self, clause: Clause, neighbors: List[Dict]) -> float:
        """Compute how much this clause deviates from market norms."""
        if not neighbors:
            return 1.0

        clause_type = clause.clause_type

        # For notice periods
        if clause_type == "termination":
            clause_days = self._extract_days(clause.text)
            if clause_days:
                neighbor_days = [
                    n.get("numeric_features", {}).get("notice_days_contractor", 30)
                    for n in neighbors
                    if n.get("numeric_features", {}).get("notice_days_contractor")
                ]
                if neighbor_days:
                    median_days = sorted(neighbor_days)[len(neighbor_days) // 2]
                    return clause_days / median_days if median_days > 0 else 1.0

        # For payment terms
        if clause_type == "payment":
            clause_days = self._extract_days(clause.text)
            if clause_days:
                return clause_days / 30.0  # Market standard is 30 days

        # Default: use text length as proxy for complexity
        return 1.0 + (len(clause.text) - 200) / 1000.0

    def _extract_days(self, text: str) -> int:
        """Extract number of days from text."""
        import re
        patterns = [
            r'(\d+)\s*days?',
            r'(\d+)\s*months?',
            r'(\d+)\s*years?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                num = int(match.group(1))
                if 'month' in pattern:
                    return num * 30
                elif 'year' in pattern:
                    return num * 365
                return num
        return 0

    def _extract_numerical_features(self, text: str) -> Dict[str, Any]:
        """Extract numerical values from clause text."""
        features = {}
        text_lower = text.lower()

        # Notice days
        days = self._extract_days(text)
        if days:
            features["notice_days"] = days

        # Payment amount
        import re
        amount_match = re.search(r'₹?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:lakh|crore)?', text_lower)
        if amount_match:
            features["payment_amount"] = float(amount_match.group(1).replace(",", ""))

        # Percentage
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if pct_match:
            features["percentage"] = float(pct_match.group(1))

        return features
